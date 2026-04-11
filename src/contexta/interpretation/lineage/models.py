"""Result models for interpretation lineage workflows."""

from __future__ import annotations

from dataclasses import dataclass

from ..compare import CompletenessNote
from ..query import EvidenceLink
from ..repositories import ProvenanceView


@dataclass(frozen=True, slots=True)
class LineageEdge:
    relation_ref: str
    source_ref: str
    target_ref: str
    relation_type: str
    recorded_at: str
    direction: str
    depth: int
    provenance: ProvenanceView | None = None
    evidence_links: tuple[EvidenceLink, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


@dataclass(frozen=True, slots=True)
class LineageTraversal:
    root_ref: str
    edges: tuple[LineageEdge, ...] = ()
    visited_refs: tuple[str, ...] = ()
    completeness_notes: tuple[CompletenessNote, ...] = ()
    evidence_links: tuple[EvidenceLink, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "edges", tuple(self.edges))
        object.__setattr__(self, "visited_refs", tuple(self.visited_refs))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


__all__ = ["LineageEdge", "LineageTraversal"]
