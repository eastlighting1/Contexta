"""Batch repository for metadata persistence."""

from __future__ import annotations

from ....common.errors import NotFoundError
from ....contract import BatchExecution, deserialize_batch_execution
from ._base import BaseRepository, normalize_ref_text


class BatchRepository(BaseRepository):
    table_name = "batch_executions"

    def put_batch_execution(self, batch: BatchExecution) -> BatchExecution:
        self.store._ensure_writable()
        if not self.store.runs.exists_run(str(batch.run_ref)):
            raise NotFoundError(
                "Batch owner run does not exist.",
                code="metadata_missing_batch_run",
                details={"run_ref": str(batch.run_ref), "batch_ref": str(batch.batch_execution_ref)},
            )
        if not self.store.stages.exists_stage_execution(str(batch.stage_execution_ref)):
            raise NotFoundError(
                "Batch owner stage does not exist.",
                code="metadata_missing_batch_stage",
                details={"stage_ref": str(batch.stage_execution_ref), "batch_ref": str(batch.batch_execution_ref)},
            )
        payload_json = self._serialize(batch)
        self._backend.upsert_payload_row(
            self.table_name,
            payload_json=payload_json,
            values={
                "ref": str(batch.batch_execution_ref),
                "run_ref": str(batch.run_ref),
                "stage_ref": str(batch.stage_execution_ref),
                "batch_name": batch.batch_name,
                "order_index": batch.order_index,
                "started_at": batch.started_at,
                "status": batch.status,
            },
        )
        self.store._register_refs(((str(batch.batch_execution_ref), "batch", "batch_execution"),))
        return batch

    def get_batch_execution(self, ref: str) -> BatchExecution:
        return self._fetch_one_payload(ref, deserializer=deserialize_batch_execution, entity_name="BatchExecution")

    def find_batch_execution(self, ref: str) -> BatchExecution | None:
        return self._find_one_payload(ref, deserializer=deserialize_batch_execution)

    def exists_batch_execution(self, ref: str) -> bool:
        return self._exists(ref)

    def list_batch_executions(
        self,
        *,
        run_ref: str | None = None,
        stage_ref: str | None = None,
    ) -> tuple[BatchExecution, ...]:
        if stage_ref is not None:
            return self._list_payloads(
                deserializer=deserialize_batch_execution,
                where="stage_ref = ?",
                params=(normalize_ref_text(stage_ref, expected_kind="stage"),),
                order_by="order_index, started_at, ref",
            )
        if run_ref is not None:
            return self._list_payloads(
                deserializer=deserialize_batch_execution,
                where="run_ref = ?",
                params=(normalize_ref_text(run_ref, expected_kind="run"),),
                order_by="stage_ref, order_index, started_at, ref",
            )
        return self._list_payloads(
            deserializer=deserialize_batch_execution,
            order_by="run_ref, stage_ref, order_index, started_at, ref",
        )


__all__ = ["BatchRepository"]
