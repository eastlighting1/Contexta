"""Result models for interpretation diagnostics workflows."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from ..compare import CompletenessNote
from ..query import EvidenceLink


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not value:
        return MappingProxyType({})
    return MappingProxyType({key: value[key] for key in sorted(value)})


@dataclass(frozen=True, slots=True)
class DiagnosticsIssue:
    severity: str
    code: str
    summary: str
    details: Mapping[str, Any]
    subject_ref: str
    evidence_links: tuple[EvidenceLink, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", _freeze_mapping(self.details))
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


@dataclass(frozen=True, slots=True)
class DiagnosticsResult:
    run_id: str
    issues: tuple[DiagnosticsIssue, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()
    evidence_links: tuple[EvidenceLink, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


__all__ = ["DiagnosticsIssue", "DiagnosticsResult"]
