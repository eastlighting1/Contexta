"""Staged ingest helpers for the artifact store."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...common.errors import ArtifactError, ValidationError
from ...common.io import ensure_directory
from ...common.time import iso_utc_now
from .models import IngestSession

if TYPE_CHECKING:
    from .write import ArtifactStore


def begin_staged_ingest(store: "ArtifactStore", source_name: str) -> IngestSession:
    from .write import _StagingMetadata

    store._ensure_writable()
    if not isinstance(source_name, str) or not source_name.strip():
        raise ValidationError(
            "source_name must not be blank.",
            code="artifact_store_invalid_source_name",
        )
    session_id = store._new_session_id(source_name)
    session = IngestSession(
        session_id=session_id,
        staging_path=store._staging_part_path(session_id),
        source_name=source_name.strip(),
    )
    ensure_directory(session.staging_path.parent)
    session.staging_path.touch(exist_ok=False)
    store._write_staging_metadata(
        _StagingMetadata(
            session_id=session.session_id,
            source_name=session.source_name,
            created_at=iso_utc_now(),
        )
    )
    return session


def write_chunk(store: "ArtifactStore", session: IngestSession, chunk: bytes) -> int:
    store._ensure_writable()
    _require_active_session(store, session)
    if not isinstance(chunk, (bytes, bytearray)):
        raise ValidationError(
            "chunk must be bytes-like.",
            code="artifact_store_invalid_chunk",
            details={"type": type(chunk).__name__},
        )
    payload = bytes(chunk)
    with session.staging_path.open("ab") as handle:
        handle.write(payload)
    return len(payload)


def commit_staged_ingest(store: "ArtifactStore", manifest: object, session: IngestSession):
    store._ensure_writable()
    _require_active_session(store, session)
    store._read_staging_metadata(session.session_id)
    receipt = store.put_artifact(
        manifest,
        session.staging_path,
        mode="adopt",
        source_name=session.source_name,
    )
    store._delete_staging_metadata(session.session_id)
    return receipt


def abort_staged_ingest(store: "ArtifactStore", session: IngestSession) -> None:
    store._ensure_writable()
    session_path = session.staging_path
    session_path.unlink(missing_ok=True)
    store._delete_staging_metadata(session.session_id)


def _require_active_session(store: "ArtifactStore", session: IngestSession) -> None:
    if not isinstance(session, IngestSession):
        raise ValidationError(
            "session must be an IngestSession.",
            code="artifact_store_invalid_session",
            details={"type": type(session).__name__},
        )
    metadata_path = store._staging_metadata_path(session.session_id)
    if not metadata_path.exists():
        raise ArtifactError(
            "Staged ingest session is not active.",
            code="artifact_store_missing_session",
            details={"session_id": session.session_id},
        )
    if not session.staging_path.exists():
        raise ArtifactError(
            "Staged ingest payload file is missing.",
            code="artifact_store_missing_staging_file",
            details={"session_id": session.session_id, "staging_path": str(session.staging_path)},
        )


__all__ = [
    "abort_staged_ingest",
    "begin_staged_ingest",
    "commit_staged_ingest",
    "write_chunk",
]
