"""Provenance repository for metadata persistence."""

from __future__ import annotations

from ....common.errors import NotFoundError
from ....contract import ProvenanceRecord, StableRef, deserialize_provenance_record
from ._base import BaseRepository, normalize_ref_text


class ProvenanceRepository(BaseRepository):
    table_name = "provenance_records"

    def put_provenance(self, provenance: ProvenanceRecord) -> ProvenanceRecord:
        self.store._ensure_writable()
        if not self.store.relations.exists_relation(str(provenance.relation_ref)):
            raise NotFoundError(
                "Provenance owner relation does not exist.",
                code="metadata_missing_provenance_relation",
                details={"relation_ref": str(provenance.relation_ref), "provenance_ref": str(provenance.provenance_ref)},
            )
        payload_json = self._serialize(provenance)
        self._backend.upsert_payload_row(
            self.table_name,
            payload_json=payload_json,
            values={
                "ref": str(provenance.provenance_ref),
                "relation_ref": str(provenance.relation_ref),
                "asserted_at": provenance.asserted_at,
                "assertion_mode": provenance.assertion_mode,
            },
        )
        refs_to_register = [(str(provenance.provenance_ref), "provenance", "provenance")]
        if provenance.formation_context_ref is not None:
            refs_to_register.append((str(provenance.formation_context_ref), "op", "formation_context"))
        if provenance.evidence_bundle_ref is not None:
            refs_to_register.append((str(provenance.evidence_bundle_ref), "artifact", "relation_evidence"))
        self.store._register_refs(refs_to_register)
        return provenance

    def get_provenance(self, ref: str) -> ProvenanceRecord:
        return self._fetch_one_payload(ref, deserializer=deserialize_provenance_record, entity_name="ProvenanceRecord")

    def find_provenance(self, ref: str) -> ProvenanceRecord | None:
        return self._find_one_payload(ref, deserializer=deserialize_provenance_record)

    def exists_provenance(self, ref: str) -> bool:
        return self._exists(ref)

    def list_provenance_for_relation(self, relation_ref: str) -> tuple[ProvenanceRecord, ...]:
        return self._list_payloads(
            deserializer=deserialize_provenance_record,
            where="relation_ref = ?",
            params=(normalize_ref_text(relation_ref, expected_kind="relation"),),
            order_by="asserted_at, ref",
        )


__all__ = ["ProvenanceRepository"]
