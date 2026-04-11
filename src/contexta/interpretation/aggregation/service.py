"""Aggregation service over interpretation query snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean

from ...common.errors import InterpretationError
from ..compare import CompletenessNote
from ..query import QueryService, RunListQuery
from ..repositories import ObservationRecord
from ..trend.service import TrendPolicy
from .models import MetricAggregate, RunStatusDistribution, RunSummaryTable, StageAggregate, StatusCount


class AggregationError(InterpretationError):
    """Raised for aggregation-specific failures."""


class AggregationService:
    """Read-only aggregation service layered on top of QueryService."""

    def __init__(
        self,
        query_service: QueryService,
        *,
        metric_aggregation: str = "latest",
    ) -> None:
        self.query_service = query_service
        self.metric_aggregation = TrendPolicy(metric_aggregation=metric_aggregation).metric_aggregation

    def aggregate_metric(
        self,
        metric_key: str,
        *,
        query: RunListQuery | None = None,
        project_name: str | None = None,
        stage_name: str | None = None,
    ) -> MetricAggregate:
        runs = self.query_service.list_runs(project_name, query=query)
        values: list[float] = []
        notes: list[CompletenessNote] = []
        inferred_project_name = None
        for run in runs:
            snapshot = self.query_service.get_run_snapshot(run.run_id)
            inferred_project_name = inferred_project_name or snapshot.run.project_name
            records = _filter_metric_records(snapshot.records, metric_key=metric_key, stage_name=stage_name)
            value = _representative_metric_value(records, self.metric_aggregation)
            if value is None:
                notes.append(
                    CompletenessNote(
                        severity="warning",
                        summary=f"missing_metric_for_aggregate:{metric_key}",
                        details={"run_id": run.run_id, "stage_name": stage_name},
                    )
                )
                continue
            values.append(value)
        if not values:
            notes.append(
                CompletenessNote(
                    severity="warning",
                    summary=f"aggregate_population_empty:{metric_key}",
                    details={"project_name": inferred_project_name or project_name, "stage_name": stage_name},
                )
            )
            return MetricAggregate(
                metric_key=metric_key,
                project_name=inferred_project_name or project_name,
                count=0,
                mean=0.0,
                std=0.0,
                min=0.0,
                p25=0.0,
                p50=0.0,
                p75=0.0,
                p90=0.0,
                p95=0.0,
                p99=0.0,
                max=0.0,
                completeness_notes=tuple(notes),
            )
        return MetricAggregate(
            metric_key=metric_key,
            project_name=inferred_project_name or project_name,
            count=len(values),
            mean=mean(values),
            std=_population_std(values),
            min=min(values),
            p25=_percentile(values, 0.25),
            p50=_percentile(values, 0.50),
            p75=_percentile(values, 0.75),
            p90=_percentile(values, 0.90),
            p95=_percentile(values, 0.95),
            p99=_percentile(values, 0.99),
            max=max(values),
            completeness_notes=tuple(notes),
        )

    def aggregate_by_stage(
        self,
        *,
        query: RunListQuery | None = None,
        project_name: str | None = None,
    ) -> RunSummaryTable:
        runs = self.query_service.list_runs(project_name, query=query)
        inferred_project_name = None
        by_stage_metric: dict[tuple[str, str], list[float]] = {}
        for run in runs:
            snapshot = self.query_service.get_run_snapshot(run.run_id)
            inferred_project_name = inferred_project_name or snapshot.run.project_name
            for record in snapshot.records:
                if record.record_type != "metric" or record.value is None:
                    continue
                stage_bucket = "_unassigned"
                if record.stage_id is not None:
                    stage_bucket = record.stage_id.split(".")[-1]
                by_stage_metric.setdefault((stage_bucket, record.key), []).append(float(record.value))
        rows = tuple(
            StageAggregate(
                stage_name=stage_name,
                metric_key=metric_key,
                count=len(values),
                mean=mean(values),
                min=min(values),
                max=max(values),
            )
            for (stage_name, metric_key), values in sorted(by_stage_metric.items())
        )
        return RunSummaryTable(
            project_name=inferred_project_name or project_name,
            total_runs=len(runs),
            by_stage=rows,
            completeness_notes=(),
        )

    def run_status_distribution(
        self,
        *,
        query: RunListQuery | None = None,
        project_name: str | None = None,
    ) -> RunStatusDistribution:
        runs = self.query_service.list_runs(project_name, query=query)
        inferred_project_name = runs[0].project_name if runs else project_name
        counts: dict[str, int] = {}
        for run in runs:
            counts[run.status] = counts.get(run.status, 0) + 1
        return RunStatusDistribution(
            project_name=inferred_project_name,
            total=len(runs),
            by_status=tuple(StatusCount(status=status, count=counts[status]) for status in sorted(counts)),
            completeness_notes=(),
        )


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
    return sqrt(variance)


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


__all__ = ["AggregationError", "AggregationService"]
