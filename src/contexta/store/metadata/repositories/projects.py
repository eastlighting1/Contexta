"""Project repository for metadata persistence."""

from __future__ import annotations

from ....contract import Project, deserialize_project
from ._base import BaseRepository, normalize_ref_text


class ProjectRepository(BaseRepository):
    table_name = "projects"

    def put_project(self, project: Project) -> Project:
        self.store._ensure_writable()
        payload_json = self._serialize(project)
        self._backend.upsert_payload_row(
            self.table_name,
            payload_json=payload_json,
            values={
                "ref": str(project.project_ref),
                "name": project.name,
                "created_at": project.created_at,
            },
        )
        self.store._register_refs(((str(project.project_ref), "project", "project"),))
        return project

    def get_project(self, ref: str) -> Project:
        return self._fetch_one_payload(ref, deserializer=deserialize_project, entity_name="Project")

    def find_project(self, ref: str) -> Project | None:
        return self._find_one_payload(ref, deserializer=deserialize_project)

    def exists_project(self, ref: str) -> bool:
        return self._exists(ref)

    def list_projects(self) -> tuple[Project, ...]:
        return self._list_payloads(deserializer=deserialize_project, order_by="name, ref")


__all__ = ["ProjectRepository"]
