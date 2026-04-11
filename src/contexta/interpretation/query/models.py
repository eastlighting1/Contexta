"""Result models for interpretation query workflows."""

from __future__ import annotations

from dataclasses import dataclass

from ..repositories import (
    ArtifactRecord,
    BatchRecord,
    DeploymentRecord,
    ObservationRecord,
    ProvenanceView,
    RelationRecord,
    RunRecord,
    SampleRecord,
    StageRecord,
)


@dataclass(frozen=True, slots=True)
class EvidenceLink:
    kind: str
    ref: str
    label: str


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    run: RunRecord
    deployments: tuple[DeploymentRecord, ...] = ()
    stages: tuple[StageRecord, ...] = ()
    batches: tuple[BatchRecord, ...] = ()
    samples: tuple[SampleRecord, ...] = ()
    artifacts: tuple[ArtifactRecord, ...] = ()
    relations: tuple[RelationRecord, ...] = ()
    records: tuple[ObservationRecord, ...] = ()
    evidence_links: tuple[EvidenceLink, ...] = ()
    completeness_notes: tuple[str, ...] = ()
    provenance: ProvenanceView | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "deployments", tuple(self.deployments))
        object.__setattr__(self, "stages", tuple(self.stages))
        object.__setattr__(self, "batches", tuple(self.batches))
        object.__setattr__(self, "samples", tuple(self.samples))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "relations", tuple(self.relations))
        object.__setattr__(self, "records", tuple(self.records))
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))


__all__ = ["EvidenceLink", "RunSnapshot"]
