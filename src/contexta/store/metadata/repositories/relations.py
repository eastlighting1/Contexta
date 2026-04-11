"""Relation repository for metadata persistence."""

from __future__ import annotations

from ....contract import LineageEdge, deserialize_lineage_edge
from ._base import BaseRepository, normalize_ref_text


class RelationRepository(BaseRepository):
    table_name = "relations"

    def put_relation(self, relation: LineageEdge) -> LineageEdge:
        self.store._ensure_writable()
        refs_to_register: list[tuple[str, str, str]] = [(str(relation.relation_ref), "relation", "relation")]
        self._ensure_endpoint_ref(str(relation.source_ref), refs_to_register)
        self._ensure_endpoint_ref(str(relation.target_ref), refs_to_register)
        payload_json = self._serialize(relation)
        self._backend.upsert_payload_row(
            self.table_name,
            payload_json=payload_json,
            values={
                "ref": str(relation.relation_ref),
                "source_ref": str(relation.source_ref),
                "target_ref": str(relation.target_ref),
                "relation_type": relation.relation_type,
                "recorded_at": relation.recorded_at,
            },
        )
        if relation.operation_context_ref is not None:
            refs_to_register.append((str(relation.operation_context_ref), "op", "operation_context"))
        for evidence_ref in relation.evidence_refs:
            refs_to_register.append((str(evidence_ref), StableRef.parse(str(evidence_ref)).kind, "relation_evidence"))
        self.store._register_refs(refs_to_register)
        return relation

    def _ensure_endpoint_ref(self, ref_text: str, refs_to_register: list[tuple[str, str, str]]) -> None:
        ref = StableRef.parse(ref_text)
        if ref.kind in {"artifact", "op"}:
            refs_to_register.append((ref_text, ref.kind, "relation_endpoint"))
            return
        self.store._require_registered_or_persisted_ref(ref_text)

    def get_relation(self, ref: str) -> LineageEdge:
        return self._fetch_one_payload(ref, deserializer=deserialize_lineage_edge, entity_name="LineageEdge")

    def find_relation(self, ref: str) -> LineageEdge | None:
        return self._find_one_payload(ref, deserializer=deserialize_lineage_edge)

    def exists_relation(self, ref: str) -> bool:
        return self._exists(ref)

    def list_relations_for_ref(self, anchor_ref: str) -> tuple[LineageEdge, ...]:
        ref_text = normalize_ref_text(anchor_ref)
        return self._list_payloads(
            deserializer=deserialize_lineage_edge,
            where="source_ref = ? OR target_ref = ?",
            params=(ref_text, ref_text),
            order_by="recorded_at, ref",
        )

    def list_relations_for_source(self, source_ref: str) -> tuple[LineageEdge, ...]:
        return self._list_payloads(
            deserializer=deserialize_lineage_edge,
            where="source_ref = ?",
            params=(normalize_ref_text(source_ref),),
            order_by="recorded_at, ref",
        )

    def list_relations_for_target(self, target_ref: str) -> tuple[LineageEdge, ...]:
        return self._list_payloads(
            deserializer=deserialize_lineage_edge,
            where="target_ref = ?",
            params=(normalize_ref_text(target_ref),),
            order_by="recorded_at, ref",
        )


from ....contract import StableRef

__all__ = ["RelationRepository"]
