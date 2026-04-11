"""Deployment repository for metadata persistence."""

from __future__ import annotations

from ....common.errors import NotFoundError
from ....contract import DeploymentExecution, deserialize_deployment_execution
from ._base import BaseRepository, normalize_ref_text


class DeploymentRepository(BaseRepository):
    table_name = "deployment_executions"

    def put_deployment_execution(self, deployment: DeploymentExecution) -> DeploymentExecution:
        self.store._ensure_writable()
        if not self.store.projects.exists_project(str(deployment.project_ref)):
            raise NotFoundError(
                "Deployment owner project does not exist.",
                code="metadata_missing_deployment_project",
                details={
                    "project_ref": str(deployment.project_ref),
                    "deployment_ref": str(deployment.deployment_execution_ref),
                },
            )
        payload_json = self._serialize(deployment)
        self._backend.upsert_payload_row(
            self.table_name,
            payload_json=payload_json,
            values={
                "ref": str(deployment.deployment_execution_ref),
                "project_ref": str(deployment.project_ref),
                "deployment_name": deployment.deployment_name,
                "run_ref": None if deployment.run_ref is None else str(deployment.run_ref),
                "order_index": deployment.order_index,
                "started_at": deployment.started_at,
                "status": deployment.status,
            },
        )
        self.store._register_refs(((str(deployment.deployment_execution_ref), "deployment", "deployment_execution"),))
        return deployment

    def get_deployment_execution(self, ref: str) -> DeploymentExecution:
        return self._fetch_one_payload(
            ref,
            deserializer=deserialize_deployment_execution,
            entity_name="DeploymentExecution",
        )

    def find_deployment_execution(self, ref: str) -> DeploymentExecution | None:
        return self._find_one_payload(ref, deserializer=deserialize_deployment_execution)

    def exists_deployment_execution(self, ref: str) -> bool:
        return self._exists(ref)

    def list_deployment_executions(
        self,
        *,
        project_ref: str | None = None,
        run_ref: str | None = None,
    ) -> tuple[DeploymentExecution, ...]:
        if run_ref is not None:
            return self._list_payloads(
                deserializer=deserialize_deployment_execution,
                where="run_ref = ?",
                params=(normalize_ref_text(run_ref, expected_kind="run"),),
                order_by="order_index, started_at, ref",
            )
        if project_ref is not None:
            return self._list_payloads(
                deserializer=deserialize_deployment_execution,
                where="project_ref = ?",
                params=(normalize_ref_text(project_ref, expected_kind="project"),),
                order_by="deployment_name, order_index, started_at, ref",
            )
        return self._list_payloads(
            deserializer=deserialize_deployment_execution,
            order_by="project_ref, deployment_name, order_index, started_at, ref",
        )


__all__ = ["DeploymentRepository"]
