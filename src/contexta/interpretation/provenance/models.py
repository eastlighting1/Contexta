"""Result models for interpretation provenance workflows."""

from __future__ import annotations

from dataclasses import dataclass

from ..compare import CompletenessNote
from ..query import EvidenceLink
from ..repositories import ProvenanceView


@dataclass(frozen=True, slots=True)
class EnvironmentValueChange:
    key: str
    left_value: str | None
    right_value: str | None


@dataclass(frozen=True, slots=True)
class EnvironmentDiff:
    left_run_id: str
    right_run_id: str
    left_environment_ref: str | None
    right_environment_ref: str | None
    python_version_changed: bool
    platform_changed: bool
    added_packages: tuple[EnvironmentValueChange, ...] = ()
    removed_packages: tuple[EnvironmentValueChange, ...] = ()
    changed_packages: tuple[EnvironmentValueChange, ...] = ()
    added_variables: tuple[EnvironmentValueChange, ...] = ()
    removed_variables: tuple[EnvironmentValueChange, ...] = ()
    changed_variables: tuple[EnvironmentValueChange, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()
    evidence_links: tuple[EvidenceLink, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "added_packages", tuple(self.added_packages))
        object.__setattr__(self, "removed_packages", tuple(self.removed_packages))
        object.__setattr__(self, "changed_packages", tuple(self.changed_packages))
        object.__setattr__(self, "added_variables", tuple(self.added_variables))
        object.__setattr__(self, "removed_variables", tuple(self.removed_variables))
        object.__setattr__(self, "changed_variables", tuple(self.changed_variables))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


@dataclass(frozen=True, slots=True)
class ReproducibilityAudit:
    run_id: str
    provenance: ProvenanceView | None
    environment_ref: str | None
    python_version: str | None
    platform: str | None
    package_count: int
    environment_variable_count: int
    reproducibility_status: str
    completeness_notes: tuple[CompletenessNote, ...] = ()
    evidence_links: tuple[EvidenceLink, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


__all__ = [
    "EnvironmentDiff",
    "EnvironmentValueChange",
    "ReproducibilityAudit",
]
