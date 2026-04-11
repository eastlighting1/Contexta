"""Stage repository for metadata persistence."""

from __future__ import annotations

from ....common.errors import NotFoundError
from ....contract import StageExecution, deserialize_stage_execution
from ._base import BaseRepository, normalize_ref_text


class StageRepository(BaseRepository):
    table_name = "stage_executions"

    def put_stage_execution(self, stage: StageExecution) -> StageExecution:
        self.store._ensure_writable()
        if not self.store.runs.exists_run(str(stage.run_ref)):
            raise NotFoundError(
                "Stage owner run does not exist.",
                code="metadata_missing_stage_run",
                details={"run_ref": str(stage.run_ref), "stage_ref": str(stage.stage_execution_ref)},
            )
        payload_json = self._serialize(stage)
        self._backend.upsert_payload_row(
            self.table_name,
            payload_json=payload_json,
            values={
                "ref": str(stage.stage_execution_ref),
                "run_ref": str(stage.run_ref),
                "stage_name": stage.stage_name,
                "order_index": stage.order_index,
                "started_at": stage.started_at,
                "status": stage.status,
            },
        )
        self.store._register_refs(((str(stage.stage_execution_ref), "stage", "stage_execution"),))
        return stage

    def get_stage_execution(self, ref: str) -> StageExecution:
        return self._fetch_one_payload(ref, deserializer=deserialize_stage_execution, entity_name="StageExecution")

    def find_stage_execution(self, ref: str) -> StageExecution | None:
        return self._find_one_payload(ref, deserializer=deserialize_stage_execution)

    def exists_stage_execution(self, ref: str) -> bool:
        return self._exists(ref)

    def list_stage_executions(self, run_ref: str) -> tuple[StageExecution, ...]:
        return self._list_payloads(
            deserializer=deserialize_stage_execution,
            where="run_ref = ?",
            params=(normalize_ref_text(run_ref, expected_kind="run"),),
            order_by="order_index, started_at, ref",
        )


__all__ = ["StageRepository"]
