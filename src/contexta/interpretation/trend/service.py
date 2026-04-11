"""Trend service over interpretation query snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean

from ...common.errors import InterpretationError, ValidationError
from ..compare import CompletenessNote
from ..query import QueryService, RunListQuery
from ..repositories import ObservationRecord
from .models import (
    ArtifactSizePoint,
    ArtifactSizeTrend,
    DurationTrend,
    MetricTrend,
    StageDurationPoint,
    StepPoint,
    StepSeries,
    TrendPoint,
)


@dataclass(frozen=True, slots=True)
class TrendPolicy:
    default_window_runs: int = 20
    metric_aggregation: str = "latest"

    def __post_init__(self) -> None:
        if not isinstance(self.default_window_runs, int) or self.default_window_runs <= 0:
            raise ValidationError(
                "default_window_runs must be a positive integer.",
                code="trend_invalid_window_runs",
                details={"default_window_runs": self.default_window_runs},
            )
        if self.metric_aggregation not in {"latest", "mean", "max", "min"}:
            raise ValidationError(
                "Unsupported trend metric aggregation.",
                code="trend_invalid_metric_aggregation",
                details={"metric_aggregation": self.metric_aggregation},
            )


class TrendError(InterpretationError):
    """Raised for trend-specific failures."""


class TrendService:
    """Read-only trend service layered on top of QueryService."""

    def __init__(
        self,
        query_service: QueryService,
        *,
        config: TrendPolicy | None = None,
    ) -> None:
        self.query_service = query_service
        self.config = config or TrendPolicy()

    def get_metric_trend(
        self,
        metric_key: str,
        *,
        query: RunListQuery | None = None,
        project_name: str | None = None,
        stage_name: str | None = None,
    ) -> MetricTrend:
        runs = self._list_runs(project_name=project_name, query=query)
        points: list[TrendPoint] = []
        notes: list[CompletenessNote] = []
        inferred_project_name = None
        for run in runs:
            snapshot = self.query_service.get_run_snapshot(run.run_id)
            inferred_project_name = inferred_project_name or snapshot.run.project_name
            records = self._filter_metric_records(snapshot.records, metric_key=metric_key, stage_name=stage_name)
            value = self._representative_metric_value(records)
            if value is None:
                notes.append(
                    CompletenessNote(
                        severity="warning",
                        summary=f"missing_metric_for_run:{metric_key}",
                        details={"run_id": run.run_id, "stage_name": stage_name},
                    )
                )
                continue
            captured_at = records[-1].observed_at if records else None
            points.append(
                TrendPoint(
                    run_id=run.run_id,
                    run_name=run.name,
                    value=value,
                    captured_at=captured_at,
                    stage_name=stage_name,
                )
            )
        return MetricTrend(
            metric_key=metric_key,
            project_name=inferred_project_name or project_name,
            points=tuple(points),
            completeness_notes=tuple(notes),
        )

    def get_step_series(
        self,
        run_id: str,
        metric_key: str,
        *,
        stage_id: str | None = None,
    ) -> StepSeries:
        snapshot = self.query_service.get_run_snapshot(run_id)
        records = self._filter_metric_records(snapshot.records, metric_key=metric_key, stage_id=stage_id)
        points: list[StepPoint] = []
        notes: list[CompletenessNote] = []
        unit = records[0].unit if records else None
        for fallback_step, record in enumerate(records):
            payload_step = record.payload.get("step")
            step = int(payload_step) if isinstance(payload_step, (int, float)) and not isinstance(payload_step, bool) else fallback_step
            if record.value is None:
                continue
            points.append(StepPoint(step=step, value=float(record.value), observed_at=record.observed_at))
        if not points:
            notes.append(
                CompletenessNote(
                    severity="info",
                    summary=f"step_series_empty:{metric_key}",
                    details={"run_id": snapshot.run.run_id, "stage_id": stage_id},
                )
            )
        return StepSeries(
            run_id=snapshot.run.run_id,
            metric_key=metric_key,
            stage_id=stage_id,
            points=tuple(points),
            completeness_notes=tuple(notes),
            unit=unit,
        )

    def get_stage_duration_trend(
        self,
        stage_name: str,
        *,
        query: RunListQuery | None = None,
        project_name: str | None = None,
    ) -> DurationTrend:
        runs = self._list_runs(project_name=project_name, query=query)
        points: list[StageDurationPoint] = []
        notes: list[CompletenessNote] = []
        inferred_project_name = None
        for run in runs:
            snapshot = self.query_service.get_run_snapshot(run.run_id)
            inferred_project_name = inferred_project_name or snapshot.run.project_name
            matched_stage = next((stage for stage in snapshot.stages if stage.name == stage_name), None)
            if matched_stage is None:
                notes.append(
                    CompletenessNote(
                        severity="warning",
                        summary=f"missing_stage_for_duration:{stage_name}",
                        details={"run_id": run.run_id},
                    )
                )
                continue
            if matched_stage.started_at is None or matched_stage.ended_at is None:
                notes.append(
                    CompletenessNote(
                        severity="warning",
                        summary=f"stage_duration_unavailable:{stage_name}",
                        details={"run_id": run.run_id, "stage_id": matched_stage.stage_id},
                    )
                )
                continue
            duration_seconds = _duration_seconds(matched_stage.started_at, matched_stage.ended_at)
            points.append(
                StageDurationPoint(
                    run_id=run.run_id,
                    run_name=run.name,
                    stage_name=stage_name,
                    duration_seconds=duration_seconds,
                    started_at=matched_stage.started_at,
                )
            )
        return DurationTrend(
            stage_name=stage_name,
            project_name=inferred_project_name or project_name,
            points=tuple(points),
            completeness_notes=tuple(notes),
        )

    def get_artifact_size_trend(
        self,
        artifact_kind: str,
        *,
        query: RunListQuery | None = None,
        project_name: str | None = None,
    ) -> ArtifactSizeTrend:
        runs = self._list_runs(project_name=project_name, query=query)
        points: list[ArtifactSizePoint] = []
        notes: list[CompletenessNote] = []
        inferred_project_name = None
        for run in runs:
            snapshot = self.query_service.get_run_snapshot(run.run_id)
            inferred_project_name = inferred_project_name or snapshot.run.project_name
            artifacts = [artifact for artifact in snapshot.artifacts if artifact.kind == artifact_kind]
            if not artifacts:
                notes.append(
                    CompletenessNote(
                        severity="warning",
                        summary=f"missing_artifact_kind:{artifact_kind}",
                        details={"run_id": run.run_id},
                    )
                )
                continue
            for artifact in artifacts:
                if artifact.size_bytes is None:
                    notes.append(
                        CompletenessNote(
                            severity="warning",
                            summary=f"artifact_size_unavailable:{artifact_kind}",
                            details={"run_id": run.run_id, "artifact_ref": artifact.artifact_ref},
                        )
                    )
                    continue
                points.append(
                    ArtifactSizePoint(
                        run_id=run.run_id,
                        run_name=run.name,
                        artifact_kind=artifact_kind,
                        size_bytes=artifact.size_bytes,
                        artifact_ref=artifact.artifact_ref,
                        created_at=artifact.created_at,
                    )
                )
        return ArtifactSizeTrend(
            artifact_kind=artifact_kind,
            project_name=inferred_project_name or project_name,
            points=tuple(points),
            completeness_notes=tuple(notes),
        )

    def _list_runs(
        self,
        *,
        project_name: str | None,
        query: RunListQuery | None,
    ) -> tuple[object, ...]:
        runs = self.query_service.list_runs(project_name, query=query)
        if len(runs) <= self.config.default_window_runs:
            return runs
        return runs[-self.config.default_window_runs :]

    def _filter_metric_records(
        self,
        records: tuple[ObservationRecord, ...],
        *,
        metric_key: str,
        stage_name: str | None = None,
        stage_id: str | None = None,
    ) -> tuple[ObservationRecord, ...]:
        filtered = []
        for record in records:
            if record.record_type != "metric" or record.key != metric_key:
                continue
            if stage_id is not None and record.stage_id != stage_id:
                continue
            if stage_name is not None:
                if record.stage_id is None or not record.stage_id.endswith(f".{stage_name}"):
                    continue
            filtered.append(record)
        return tuple(sorted(filtered, key=lambda item: item.observed_at))

    def _representative_metric_value(self, records: tuple[ObservationRecord, ...]) -> float | None:
        values = [float(record.value) for record in records if record.value is not None]
        if not values:
            return None
        if self.config.metric_aggregation == "latest":
            return values[-1]
        if self.config.metric_aggregation == "max":
            return max(values)
        if self.config.metric_aggregation == "min":
            return min(values)
        return mean(values)


def _duration_seconds(started_at: str, ended_at: str) -> float:
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    end = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
    return (end - start).total_seconds()


__all__ = ["TrendError", "TrendPolicy", "TrendService"]
