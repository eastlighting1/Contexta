"""Result models for interpretation trend workflows."""

from __future__ import annotations

from dataclasses import dataclass

from ..compare import CompletenessNote


@dataclass(frozen=True, slots=True)
class TrendPoint:
    run_id: str
    run_name: str
    value: float
    captured_at: str | None = None
    stage_name: str | None = None


@dataclass(frozen=True, slots=True)
class MetricTrend:
    metric_key: str
    project_name: str | None
    points: tuple[TrendPoint, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", tuple(self.points))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))

    @property
    def values(self) -> tuple[float, ...]:
        return tuple(point.value for point in self.points)


@dataclass(frozen=True, slots=True)
class StepPoint:
    step: int
    value: float
    observed_at: str


@dataclass(frozen=True, slots=True)
class StepSeries:
    run_id: str
    metric_key: str
    stage_id: str | None
    points: tuple[StepPoint, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()
    unit: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", tuple(self.points))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))


@dataclass(frozen=True, slots=True)
class StageDurationPoint:
    run_id: str
    run_name: str
    stage_name: str
    duration_seconds: float
    started_at: str | None = None


@dataclass(frozen=True, slots=True)
class DurationTrend:
    stage_name: str
    project_name: str | None
    points: tuple[StageDurationPoint, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", tuple(self.points))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))


@dataclass(frozen=True, slots=True)
class ArtifactSizePoint:
    run_id: str
    run_name: str
    artifact_kind: str
    size_bytes: int
    artifact_ref: str
    created_at: str | None = None


@dataclass(frozen=True, slots=True)
class ArtifactSizeTrend:
    artifact_kind: str
    project_name: str | None
    points: tuple[ArtifactSizePoint, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", tuple(self.points))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))


__all__ = [
    "ArtifactSizePoint",
    "ArtifactSizeTrend",
    "DurationTrend",
    "MetricTrend",
    "StageDurationPoint",
    "StepPoint",
    "StepSeries",
    "TrendPoint",
]
