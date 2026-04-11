"""Anomaly detection service over interpretation query snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from math import fabs
from statistics import mean

from ...common.errors import InterpretationError, ValidationError
from ..compare import CompletenessNote
from ..query import EvidenceLink, QueryService, RunListQuery
from ..repositories import ObservationRecord
from ..trend.service import TrendPolicy
from .models import AnomalyResult, MetricBaseline


@dataclass(frozen=True, slots=True)
class AnomalyPolicy:
    z_score_threshold: float = 2.5
    min_baseline_runs: int = 3
    monitored_metrics: tuple[str, ...] = ()
    metric_aggregation: str = "latest"

    def __post_init__(self) -> None:
        if self.z_score_threshold <= 0:
            raise ValidationError(
                "z_score_threshold must be positive.",
                code="anomaly_invalid_z_score_threshold",
                details={"z_score_threshold": self.z_score_threshold},
            )
        if not isinstance(self.min_baseline_runs, int) or self.min_baseline_runs < 1:
            raise ValidationError(
                "min_baseline_runs must be at least 1.",
                code="anomaly_invalid_min_baseline_runs",
                details={"min_baseline_runs": self.min_baseline_runs},
            )
        object.__setattr__(self, "monitored_metrics", tuple(self.monitored_metrics))
        object.__setattr__(
            self,
            "metric_aggregation",
            TrendPolicy(metric_aggregation=self.metric_aggregation).metric_aggregation,
        )


class AnomalyError(InterpretationError):
    """Raised for anomaly-specific failures."""


class AnomalyService:
    """Read-only anomaly service layered on top of QueryService."""

    def __init__(
        self,
        query_service: QueryService,
        *,
        z_score_threshold: float = 2.5,
        min_baseline_runs: int = 3,
        metric_aggregation: str = "latest",
        monitored_metrics: tuple[str, ...] = (),
    ) -> None:
        self.query_service = query_service
        self.config = AnomalyPolicy(
            z_score_threshold=z_score_threshold,
            min_baseline_runs=min_baseline_runs,
            monitored_metrics=monitored_metrics,
            metric_aggregation=metric_aggregation,
        )

    def compute_baseline(
        self,
        metric_key: str,
        *,
        query: RunListQuery | None = None,
        project_name: str | None = None,
        stage_name: str | None = None,
    ) -> MetricBaseline:
        runs = self.query_service.list_runs(project_name, query=query)
        values: list[float] = []
        for run in runs:
            snapshot = self.query_service.get_run_snapshot(run.run_id)
            records = _filter_metric_records(snapshot.records, metric_key=metric_key, stage_name=stage_name)
            value = _representative_metric_value(records, self.config.metric_aggregation)
            if value is None:
                continue
            values.append(value)
        if not values:
            return MetricBaseline(metric_key=metric_key, mean=0.0, std=0.0, p5=0.0, p95=0.0, computed_from_n_runs=0)
        if len(values) == 1:
            value = values[0]
            return MetricBaseline(metric_key=metric_key, mean=value, std=0.0, p5=value, p95=value, computed_from_n_runs=1)
        return MetricBaseline(
            metric_key=metric_key,
            mean=mean(values),
            std=_population_std(values),
            p5=_percentile(values, 0.05),
            p95=_percentile(values, 0.95),
            computed_from_n_runs=len(values),
        )

    def detect_anomalies(
        self,
        run_id: str,
        *,
        baseline: MetricBaseline,
        stage_name: str | None = None,
    ) -> tuple[AnomalyResult, ...]:
        snapshot = self.query_service.get_run_snapshot(run_id)
        records = _filter_metric_records(snapshot.records, metric_key=baseline.metric_key, stage_name=stage_name)
        actual_value = _representative_metric_value(records, self.config.metric_aggregation)
        if actual_value is None:
            return ()
        notes: list[CompletenessNote] = []
        if baseline.computed_from_n_runs < self.config.min_baseline_runs:
            notes.append(
                CompletenessNote(
                    severity="warning",
                    summary=f"baseline_population_small:{baseline.metric_key}",
                    details={"computed_from_n_runs": baseline.computed_from_n_runs},
                )
            )
        if baseline.std == 0.0:
            z_score = 0.0 if actual_value == baseline.mean else float("inf")
            severity = "info"
        else:
            z_score = (actual_value - baseline.mean) / baseline.std
            severity = _severity_for_z_score(fabs(z_score), self.config.z_score_threshold)
        evidence_links = (
            EvidenceLink(kind="run", ref=snapshot.run.run_id, label=snapshot.run.name),
        )
        return (
            AnomalyResult(
                metric_key=baseline.metric_key,
                run_id=snapshot.run.run_id,
                actual_value=actual_value,
                expected_range=(
                    baseline.mean - self.config.z_score_threshold * baseline.std,
                    baseline.mean + self.config.z_score_threshold * baseline.std,
                ),
                z_score=z_score,
                severity=severity,
                evidence_links=evidence_links,
                completeness_notes=tuple(notes),
            ),
        )

    def detect_anomalies_in_run(
        self,
        run_id: str,
        *,
        baseline_query: RunListQuery | None = None,
        metric_keys: tuple[str, ...] | None = None,
        stage_name: str | None = None,
    ) -> tuple[AnomalyResult, ...]:
        snapshot = self.query_service.get_run_snapshot(run_id)
        selected_metric_keys = metric_keys
        if selected_metric_keys is None:
            discovered = []
            for record in snapshot.records:
                if record.record_type != "metric":
                    continue
                if stage_name is not None:
                    if record.stage_id is None or not record.stage_id.endswith(f".{stage_name}"):
                        continue
                discovered.append(record.key)
            if self.config.monitored_metrics:
                selected_metric_keys = tuple(key for key in self.config.monitored_metrics if key in set(discovered))
            else:
                selected_metric_keys = tuple(dict.fromkeys(discovered))

        baseline_runs = self.query_service.list_runs(snapshot.run.project_name, query=baseline_query)
        filtered_run_ids = tuple(run.run_id for run in baseline_runs if run.run_id != snapshot.run.run_id)

        results: list[AnomalyResult] = []
        for metric_key in selected_metric_keys:
            filtered_query = _query_with_explicit_run_ids(baseline_query, filtered_run_ids)
            baseline = self.compute_baseline(
                metric_key,
                query=filtered_query,
                project_name=snapshot.run.project_name,
                stage_name=stage_name,
            )
            if baseline.computed_from_n_runs < 2:
                continue
            results.extend(self.detect_anomalies(run_id, baseline=baseline, stage_name=stage_name))
        return tuple(results)


def _filter_metric_records(
    records: tuple[ObservationRecord, ...],
    *,
    metric_key: str,
    stage_name: str | None = None,
) -> tuple[ObservationRecord, ...]:
    filtered = []
    for record in records:
        if record.record_type != "metric" or record.key != metric_key:
            continue
        if stage_name is not None:
            if record.stage_id is None or not record.stage_id.endswith(f".{stage_name}"):
                continue
        filtered.append(record)
    return tuple(sorted(filtered, key=lambda item: item.observed_at))


def _representative_metric_value(records: tuple[ObservationRecord, ...], aggregation: str) -> float | None:
    values = [float(record.value) for record in records if record.value is not None]
    if not values:
        return None
    if aggregation == "latest":
        return values[-1]
    if aggregation == "max":
        return max(values)
    if aggregation == "min":
        return min(values)
    return mean(values)


def _population_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return variance ** 0.5


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _severity_for_z_score(abs_z: float, threshold: float) -> str:
    if abs_z < threshold:
        return "info"
    if abs_z < threshold * 1.5:
        return "warning"
    return "error"


def _query_with_explicit_run_ids(query: RunListQuery | None, run_ids: tuple[str, ...]) -> RunListQuery:
    if query is None:
        query = RunListQuery()
    filtered_tags = dict(query.tags or {})
    if run_ids:
        filtered_tags["__run_ids__"] = ",".join(run_ids)
    return RunListQuery(
        project_name=query.project_name,
        status=query.status,
        tags=filtered_tags,
        time_range=query.time_range,
        metric_conditions=query.metric_conditions,
        sort_by=query.sort_by,
        sort_desc=query.sort_desc,
        offset=query.offset,
        limit=query.limit,
    )


__all__ = ["AnomalyError", "AnomalyPolicy", "AnomalyService"]
