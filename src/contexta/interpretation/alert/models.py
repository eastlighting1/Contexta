"""Result models for interpretation alert workflows."""

from __future__ import annotations

from dataclasses import dataclass

from ..compare import CompletenessNote
from ..query import EvidenceLink


@dataclass(frozen=True, slots=True)
class AlertRule:
    metric_key: str
    operator: str
    threshold: float
    stage_name: str | None = None
    severity: str = "warning"
    name: str | None = None


@dataclass(frozen=True, slots=True)
class AlertResult:
    rule_name: str
    metric_key: str
    run_id: str
    actual_value: float | None
    threshold: float
    operator: str
    triggered: bool
    severity: str
    stage_name: str | None = None
    evidence_links: tuple[EvidenceLink, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))


@dataclass(frozen=True, slots=True)
class AlertReport:
    run_ids: tuple[str, ...]
    results: tuple[AlertResult, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_ids", tuple(self.run_ids))
        object.__setattr__(self, "results", tuple(self.results))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))


__all__ = ["AlertReport", "AlertResult", "AlertRule"]
