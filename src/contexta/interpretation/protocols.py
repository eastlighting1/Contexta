"""Read-only repository protocols for interpretation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RunStoreReader(Protocol):
    def list_projects(self) -> Sequence[str]: ...
    def list_runs(self, project_name: str | None = None) -> Sequence[Any]: ...
    def get_run(self, run_id: str) -> Any | None: ...
    def list_deployments(self, project_name: str | None = None, run_id: str | None = None) -> Sequence[Any]: ...
    def list_stages(self, run_id: str) -> Sequence[Any]: ...
    def list_batches(self, run_id: str, stage_id: str | None = None) -> Sequence[Any]: ...
    def list_samples(
        self,
        run_id: str,
        stage_id: str | None = None,
        batch_id: str | None = None,
    ) -> Sequence[Any]: ...


@runtime_checkable
class RecordStoreReader(Protocol):
    def list_records(
        self,
        *,
        run_id: str,
        stage_id: str | None = None,
        record_type: str | None = None,
    ) -> Sequence[Any]: ...


@runtime_checkable
class RelationStoreReader(Protocol):
    def list_relations(self, subject_ref: str | None = None) -> Sequence[Any]: ...
    def get_provenance(self, run_id: str) -> Any | None: ...


@runtime_checkable
class ArtifactStoreReader(Protocol):
    def get_artifact(self, artifact_ref: str) -> Any | None: ...
    def list_artifacts(
        self,
        *,
        run_id: str | None = None,
        stage_id: str | None = None,
    ) -> Sequence[Any]: ...


@runtime_checkable
class CompositeRepository(RunStoreReader, RecordStoreReader, RelationStoreReader, ArtifactStoreReader, Protocol):
    """Canonical read-only boundary for interpretation services."""


ObservabilityRepository = CompositeRepository


__all__ = [
    "ArtifactStoreReader",
    "CompositeRepository",
    "ObservabilityRepository",
    "RecordStoreReader",
    "RelationStoreReader",
    "RunStoreReader",
]
