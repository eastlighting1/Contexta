"""Run repository for metadata persistence."""

from __future__ import annotations

from ....common.errors import NotFoundError
from ....contract import Run, StableRef, deserialize_run
from ._base import BaseRepository, normalize_ref_text


class RunRepository(BaseRepository):
    table_name = "runs"

    def put_run(self, run: Run) -> Run:
        self.store._ensure_writable()
        if not self.store.projects.exists_project(str(run.project_ref)):
            raise NotFoundError(
                "Run owner project does not exist.",
                code="metadata_missing_run_project",
                details={"project_ref": str(run.project_ref), "run_ref": str(run.run_ref)},
            )
        payload_json = self._serialize(run)
        self._backend.upsert_payload_row(
            self.table_name,
            payload_json=payload_json,
            values={
                "ref": str(run.run_ref),
                "project_ref": str(run.project_ref),
                "name": run.name,
                "started_at": run.started_at,
                "status": run.status,
            },
        )
        self.store._register_refs(((str(run.run_ref), "run", "run"),))
        return run

    def get_run(self, ref: str) -> Run:
        return self._fetch_one_payload(ref, deserializer=deserialize_run, entity_name="Run")

    def find_run(self, ref: str) -> Run | None:
        return self._find_one_payload(ref, deserializer=deserialize_run)

    def exists_run(self, ref: str) -> bool:
        return self._exists(ref)

    def list_runs(self, project_ref: str | None = None) -> tuple[Run, ...]:
        if project_ref is None:
            return self._list_payloads(deserializer=deserialize_run, order_by="project_ref, started_at, ref")
        return self._list_payloads(
            deserializer=deserialize_run,
            where="project_ref = ?",
            params=(normalize_ref_text(project_ref, expected_kind="project"),),
            order_by="started_at, ref",
        )


__all__ = ["RunRepository"]
