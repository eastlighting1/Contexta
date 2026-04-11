"""Environment snapshot repository for metadata persistence."""

from __future__ import annotations

from ....common.errors import NotFoundError
from ....contract import EnvironmentSnapshot, deserialize_environment_snapshot
from ._base import BaseRepository, normalize_ref_text


class EnvironmentRepository(BaseRepository):
    table_name = "environment_snapshots"

    def put_environment_snapshot(self, snapshot: EnvironmentSnapshot) -> EnvironmentSnapshot:
        self.store._ensure_writable()
        if not self.store.runs.exists_run(str(snapshot.run_ref)):
            raise NotFoundError(
                "Environment snapshot owner run does not exist.",
                code="metadata_missing_environment_run",
                details={"run_ref": str(snapshot.run_ref), "environment_ref": str(snapshot.environment_snapshot_ref)},
            )
        payload_json = self._serialize(snapshot)
        self._backend.upsert_payload_row(
            self.table_name,
            payload_json=payload_json,
            values={
                "ref": str(snapshot.environment_snapshot_ref),
                "run_ref": str(snapshot.run_ref),
                "captured_at": snapshot.captured_at,
            },
        )
        self.store._register_refs(((str(snapshot.environment_snapshot_ref), "environment", "environment_snapshot"),))
        return snapshot

    def get_environment_snapshot(self, ref: str) -> EnvironmentSnapshot:
        return self._fetch_one_payload(ref, deserializer=deserialize_environment_snapshot, entity_name="EnvironmentSnapshot")

    def find_environment_snapshot(self, ref: str) -> EnvironmentSnapshot | None:
        return self._find_one_payload(ref, deserializer=deserialize_environment_snapshot)

    def exists_environment_snapshot(self, ref: str) -> bool:
        return self._exists(ref)

    def list_environment_snapshots(self, run_ref: str) -> tuple[EnvironmentSnapshot, ...]:
        return self._list_payloads(
            deserializer=deserialize_environment_snapshot,
            where="run_ref = ?",
            params=(normalize_ref_text(run_ref, expected_kind="run"),),
            order_by="captured_at, ref",
        )


__all__ = ["EnvironmentRepository"]
