"""Result models for interpretation anomaly workflows."""

from __future__ import annotations

from dataclasses import dataclass

from ..compare import CompletenessNote
from ..query import EvidenceLink


@dataclass(frozen=True, slots=True)
class MetricBaseline:
    metric_key: str
    mean: float
    std: float
    p5: float
    p95: float
    computed_from_n_runs: int


@dataclass(frozen=True, slots=True)
class AnomalyResult:
    metric_key: str
    run_id: str
    actual_value: float
    expected_range: tuple[float, float]
    z_score: float
    severity: str
    evidence_links: tuple[EvidenceLink, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))


__all__ = ["AnomalyResult", "MetricBaseline"]
