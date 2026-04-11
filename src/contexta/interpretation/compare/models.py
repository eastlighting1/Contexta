"""Result models for interpretation compare workflows."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from ..query import EvidenceLink
from ..repositories import ProvenanceView


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not value:
        return MappingProxyType({})
    return MappingProxyType({key: value[key] for key in sorted(value)})


@dataclass(frozen=True, slots=True)
class CompletenessNote:
    severity: str
    summary: str
    details: Mapping[str, Any] | None = None
    evidence_links: tuple[EvidenceLink, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", _freeze_mapping(self.details))
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


@dataclass(frozen=True, slots=True)
class MetricDelta:
    metric_key: str
    left_value: float | None
    right_value: float | None
    delta: float | None
    change_ratio: float | None
    stage_name: str | None
    evidence_links: tuple[EvidenceLink, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))


@dataclass(frozen=True, slots=True)
class ArtifactChange:
    artifact_kind: str
    left_ref: str | None
    right_ref: str | None
    change: str
    evidence_links: tuple[EvidenceLink, ...] = ()
    change_detail: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


@dataclass(frozen=True, slots=True)
class StageComparison:
    stage_name: str
    left_stage_id: str | None
    right_stage_id: str | None
    left_status: str | None
    right_status: str | None
    metric_deltas: tuple[MetricDelta, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()
    evidence_links: tuple[EvidenceLink, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_deltas", tuple(self.metric_deltas))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


@dataclass(frozen=True, slots=True)
class ProvenanceComparison:
    code_revision_changed: bool
    config_hash_changed: bool
    environment_changed: bool
    dataset_refs_changed: bool
    left_provenance: ProvenanceView | None
    right_provenance: ProvenanceView | None


@dataclass(frozen=True, slots=True)
class RunComparison:
    left_run_id: str
    right_run_id: str
    summary: str
    stage_comparisons: tuple[StageComparison, ...] = ()
    artifact_changes: tuple[ArtifactChange, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()
    evidence_links: tuple[EvidenceLink, ...] = ()
    provenance_comparison: ProvenanceComparison | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage_comparisons", tuple(self.stage_comparisons))
        object.__setattr__(self, "artifact_changes", tuple(self.artifact_changes))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


@dataclass(frozen=True, slots=True)
class MultiRunMetricRow:
    metric_key: str
    stage_name: str | None
    values: tuple[float | None, ...]
    best_run_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", tuple(self.values))


@dataclass(frozen=True, slots=True)
class ArtifactKindCountRow:
    artifact_kind: str
    counts: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "counts", tuple(self.counts))


@dataclass(frozen=True, slots=True)
class MultiRunComparison:
    run_ids: tuple[str, ...]
    run_names: tuple[str, ...]
    metric_table: tuple[MultiRunMetricRow, ...] = ()
    artifact_kind_counts: tuple[ArtifactKindCountRow, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()
    evidence_links: tuple[EvidenceLink, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_ids", tuple(self.run_ids))
        object.__setattr__(self, "run_names", tuple(self.run_names))
        object.__setattr__(self, "metric_table", tuple(self.metric_table))
        object.__setattr__(self, "artifact_kind_counts", tuple(self.artifact_kind_counts))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


@dataclass(frozen=True, slots=True)
class SectionDiff:
    section_title: str
    left_body: str | None
    right_body: str | None
    changed: bool


@dataclass(frozen=True, slots=True)
class ReportComparison:
    left_title: str
    right_title: str
    section_diffs: tuple[SectionDiff, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "section_diffs", tuple(self.section_diffs))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))


__all__ = [
    "ArtifactChange",
    "ArtifactKindCountRow",
    "CompletenessNote",
    "MetricDelta",
    "MultiRunComparison",
    "MultiRunMetricRow",
    "ProvenanceComparison",
    "ReportComparison",
    "RunComparison",
    "SectionDiff",
    "StageComparison",
]
