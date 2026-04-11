"""Lineage traversal service over interpretation repositories."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from ...common.errors import InterpretationError, ValidationError
from ..compare import CompletenessNote
from ..query import EvidenceLink, QueryService
from ..repositories import ProvenanceView, RelationRecord
from .models import LineageEdge, LineageTraversal


@dataclass(frozen=True, slots=True)
class LineagePolicy:
    default_direction: str = "both"
    default_max_depth: int = 2
    include_provenance: bool = True

    def __post_init__(self) -> None:
        if self.default_direction not in {"inbound", "outbound", "both"}:
            raise ValidationError(
                "Unsupported lineage direction.",
                code="lineage_invalid_direction",
                details={"direction": self.default_direction},
            )
        if not isinstance(self.default_max_depth, int) or self.default_max_depth < 0:
            raise ValidationError(
                "default_max_depth must be a non-negative integer.",
                code="lineage_invalid_max_depth",
                details={"default_max_depth": self.default_max_depth},
            )


class LineageError(InterpretationError):
    """Raised for lineage-specific failures."""


class LineageService:
    """Read-only lineage traversal service over repository relations."""

    def __init__(
        self,
        query_service: QueryService,
        *,
        config: LineagePolicy | None = None,
    ) -> None:
        self.query_service = query_service
        self.config = config or LineagePolicy()

    def traverse_lineage(
        self,
        subject_ref: str,
        *,
        direction: str | None = None,
        max_depth: int | None = None,
    ) -> LineageTraversal:
        traversal_direction = self.config.default_direction if direction is None else direction
        if traversal_direction not in {"inbound", "outbound", "both"}:
            raise LineageError(
                "Unsupported lineage traversal direction.",
                code="lineage_invalid_direction",
                details={"direction": traversal_direction},
            )
        depth_limit = self.config.default_max_depth if max_depth is None else max_depth
        if not isinstance(depth_limit, int) or depth_limit < 0:
            raise LineageError(
                "max_depth must be a non-negative integer.",
                code="lineage_invalid_max_depth",
                details={"max_depth": max_depth},
            )

        queue: deque[tuple[str, int]] = deque([(subject_ref, 0)])
        queued_refs: set[str] = {subject_ref}
        visited_refs: list[str] = []
        edges_by_ref: dict[str, LineageEdge] = {}
        notes: list[CompletenessNote] = []

        while queue:
            current_ref, depth = queue.popleft()
            visited_refs.append(current_ref)
            if depth > depth_limit:
                continue
            relations = tuple(self.query_service.repository.list_relations(current_ref))
            if not relations and depth == 0:
                notes.append(
                    CompletenessNote(
                        severity="info",
                        summary="lineage_root_has_no_relations",
                        details={"root_ref": subject_ref},
                    )
                )
            for relation in relations:
                relation_direction = _relation_direction(current_ref, relation)
                if traversal_direction != "both" and relation_direction != traversal_direction:
                    continue
                if relation.relation_ref not in edges_by_ref:
                    provenance = self._get_relation_provenance(relation)
                    evidence_links = (
                        EvidenceLink(kind="relation", ref=relation.relation_ref, label=relation.relation_type),
                        EvidenceLink(kind="ref", ref=relation.source_ref, label=relation.source_ref),
                        EvidenceLink(kind="ref", ref=relation.target_ref, label=relation.target_ref),
                    )
                    edges_by_ref[relation.relation_ref] = LineageEdge(
                        relation_ref=relation.relation_ref,
                        source_ref=relation.source_ref,
                        target_ref=relation.target_ref,
                        relation_type=relation.relation_type,
                        recorded_at=relation.recorded_at,
                        direction=relation_direction,
                        depth=depth,
                        provenance=provenance,
                        evidence_links=evidence_links,
                    )
                if depth == depth_limit:
                    continue
                for next_ref in _next_refs(current_ref, relation, traversal_direction):
                    if next_ref in queued_refs:
                        continue
                    queued_refs.add(next_ref)
                    queue.append((next_ref, depth + 1))

        evidence_links = tuple(
            dict.fromkeys(link for edge in edges_by_ref.values() for link in edge.evidence_links)
        )
        return LineageTraversal(
            root_ref=subject_ref,
            edges=tuple(edges_by_ref[key] for key in sorted(edges_by_ref)),
            visited_refs=tuple(dict.fromkeys(visited_refs)),
            completeness_notes=tuple(notes),
            evidence_links=evidence_links,
        )

    def _get_relation_provenance(self, relation: RelationRecord) -> ProvenanceView | None:
        if not self.config.include_provenance:
            return None
        metadata_store = getattr(self.query_service.repository, "metadata_store", None)
        if metadata_store is None:
            return None
        provenance_rows = metadata_store.provenance.list_provenance_for_relation(relation.relation_ref)
        if not provenance_rows:
            return None
        selected = sorted(provenance_rows, key=lambda item: item.asserted_at)[-1]
        return ProvenanceView(
            run_id=_infer_run_id(relation),
            provenance_ref=str(selected.provenance_ref),
            relation_ref=str(selected.relation_ref),
            assertion_mode=selected.assertion_mode,
            asserted_at=selected.asserted_at,
            formation_context_ref=None if selected.formation_context_ref is None else str(selected.formation_context_ref),
            policy_ref=None if selected.policy_ref is None else str(selected.policy_ref),
            evidence_bundle_ref=None if selected.evidence_bundle_ref is None else str(selected.evidence_bundle_ref),
        )


def _relation_direction(current_ref: str, relation: RelationRecord) -> str:
    if relation.source_ref == current_ref and relation.target_ref == current_ref:
        return "both"
    if relation.source_ref == current_ref:
        return "outbound"
    if relation.target_ref == current_ref:
        return "inbound"
    return "both"


def _next_refs(current_ref: str, relation: RelationRecord, direction: str) -> tuple[str, ...]:
    refs: list[str] = []
    if direction in {"outbound", "both"} and relation.source_ref == current_ref:
        refs.append(relation.target_ref)
    if direction in {"inbound", "both"} and relation.target_ref == current_ref:
        refs.append(relation.source_ref)
    if not refs:
        if relation.source_ref != current_ref:
            refs.append(relation.source_ref)
        if relation.target_ref != current_ref:
            refs.append(relation.target_ref)
    return tuple(dict.fromkeys(refs))


def _infer_run_id(relation: RelationRecord) -> str:
    for ref_text in (relation.source_ref, relation.target_ref):
        if ref_text.startswith("run:"):
            return ref_text
        if ref_text.startswith(("stage:", "artifact:", "record:", "op:")):
            _, value = ref_text.split(":", 1)
            parts = value.split(".")
            if len(parts) >= 2:
                return f"run:{parts[0]}.{parts[1]}"
    return relation.relation_ref


__all__ = ["LineageError", "LineagePolicy", "LineageService"]
