"""Result models for interpretation aggregation workflows."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from ..compare import CompletenessNote


@dataclass(frozen=True, slots=True)
class StageAggregate:
    stage_name: str
    metric_key: str
    count: int
    mean: float
    min: float
    max: float


@dataclass(frozen=True, slots=True)
class RunSummaryTable:
    project_name: str | None
    total_runs: int
    by_stage: tuple[StageAggregate, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "by_stage", tuple(self.by_stage))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))


@dataclass(frozen=True, slots=True)
class MetricAggregate:
    metric_key: str
    project_name: str | None
    count: int
    mean: float
    std: float
    min: float
    p25: float
    p50: float
    p75: float
    p90: float
    p95: float
    p99: float
    max: float
    completeness_notes: tuple[CompletenessNote, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))


@dataclass(frozen=True, slots=True)
class StatusCount:
    status: str
    count: int


@dataclass(frozen=True, slots=True)
class RunStatusDistribution:
    project_name: str | None
    total: int
    by_status: tuple[StatusCount, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "by_status", tuple(self.by_status))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        completed = sum(item.count for item in self.by_status if item.status == "completed")
        return completed / self.total


__all__ = [
    "MetricAggregate",
    "RunStatusDistribution",
    "RunSummaryTable",
    "StageAggregate",
    "StatusCount",
]
