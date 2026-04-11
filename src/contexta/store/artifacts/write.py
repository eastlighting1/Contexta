"""Filesystem-backed artifact ingest and binding store."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Mapping
from uuid import uuid4

from ...common.errors import ArtifactError, ConflictError, ReadOnlyStoreError, ValidationError
from ...common.io import atomic_write_json, ensure_directory, read_json, resolve_path
from ...common.time import iso_utc_now
from ...contract import (
    ArtifactManifest,
    deserialize_artifact_manifest,
    validate_artifact_manifest,
)
from .config import IngestMode, VaultConfig, VerificationMode
from .models import ArtifactBinding, ArtifactPutReceipt


_SAFE_PATH_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class _StagingMetadata:
    session_id: str
    source_name: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "source_name": self.source_name,
            "created_at": self.created_at,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "_StagingMetadata":
        return cls(
            session_id=str(payload["session_id"]),
            source_name=str(payload["source_name"]),
            created_at=str(payload["created_at"]),
        )


def _normalize_manifest(manifest: object) -> ArtifactManifest:
    if isinstance(manifest, ArtifactManifest):
        value = manifest
    else:
        value = deserialize_artifact_manifest(manifest)
    validate_artifact_manifest(value).raise_for_errors()
    return value


def _normalize_source_path(source: str | Path, *, field_name: str = "source") -> Path:
    path = resolve_path(source)
    if not path.exists():
        raise ValidationError(
            f"{field_name} does not exist.",
            code="artifact_store_missing_source",
            details={"field_name": field_name, "path": str(path)},
        )
    if not path.is_file():
        raise ValidationError(
            f"{field_name} must point to a file.",
            code="artifact_store_invalid_source",
            details={"field_name": field_name, "path": str(path)},
        )
    return path


def _sanitize_path_component(value: str) -> str:
    sanitized = _SAFE_PATH_PATTERN.sub("_", value.replace(":", "__"))
    sanitized = sanitized.strip("._")
    return sanitized or "artifact"


def _suffix_from_path(path: Path | str | None) -> str:
    if path is None:
        return ""
    suffixes = Path(path).suffixes
    return "".join(suffixes)


def _hash_artifact_ref(artifact_ref: str) -> str:
    return hashlib.sha256(artifact_ref.encode("utf-8")).hexdigest()


def _compute_file_fingerprint(path: Path, *, chunk_size: int) -> tuple[int, str]:
    size_bytes = 0
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            size_bytes += len(chunk)
            digest.update(chunk)
    return size_bytes, digest.hexdigest()


class ArtifactStore:
    """Filesystem-backed artifact truth store."""

    def __init__(self, config: VaultConfig | None = None) -> None:
        self.config = config or VaultConfig()
        if self.config.root_path is None:
            raise ValidationError(
                "ArtifactStore requires a concrete root_path.",
                code="artifact_store_missing_root_path",
            )
        self.root_path = resolve_path(self.config.root_path)
        self._bootstrap()

    def create_staging_path(self, source_name: str) -> Path:
        session_id = self._new_session_id(source_name)
        return self._staging_part_path(session_id)

    def put_artifact(
        self,
        manifest: object,
        source: str | Path,
        *,
        mode: IngestMode | str | None = None,
        source_name: str | None = None,
    ) -> ArtifactPutReceipt:
        self._ensure_writable()
        normalized_manifest = _normalize_manifest(manifest)
        ingest_mode = self._normalize_ingest_mode(mode)
        source_path = _normalize_source_path(source)
        source_name_value = source_name or source_path.name
        expected_path = self._expected_object_path(
            normalized_manifest,
            suffix=self._infer_suffix(source_path, normalized_manifest.location_ref),
        )
        if ingest_mode is IngestMode.ADOPT:
            self._validate_adopt_source(source_path)

        size_bytes, hash_value = _compute_file_fingerprint(
            source_path,
            chunk_size=self.config.chunk_size_bytes,
        )
        existing_binding = self._load_binding(str(normalized_manifest.artifact_ref))
        if existing_binding is not None:
            existing_path = self._expected_object_path(
                existing_binding.manifest_snapshot,
                suffix=self._infer_suffix(None, existing_binding.manifest_snapshot.location_ref),
            )
            if (
                existing_path.exists()
                and existing_binding.size_bytes == size_bytes
                and existing_binding.hash_value == hash_value
            ):
                return ArtifactPutReceipt(binding=existing_binding, path=existing_path, bytes_written=0)
            raise ConflictError(
                "artifact_ref is already bound to a different body.",
                code="artifact_binding_conflict",
                details={"artifact_ref": str(normalized_manifest.artifact_ref)},
            )

        self._verify_ingest_claims(normalized_manifest, size_bytes=size_bytes, hash_value=hash_value)

        self._finalize_source_to_object(source_path=source_path, destination=expected_path, mode=ingest_mode)
        binding = self._build_binding(
            manifest=normalized_manifest,
            source_name=source_name_value,
            ingest_mode=ingest_mode,
            size_bytes=size_bytes,
            hash_value=hash_value,
        )
        self._write_binding(binding)
        self._append_binding_history(binding=binding, path=expected_path, action="put")
        return ArtifactPutReceipt(binding=binding, path=expected_path, bytes_written=size_bytes)

    def put_artifact_from_stream(
        self,
        manifest: object,
        stream: BinaryIO,
        *,
        source_name: str,
    ) -> ArtifactPutReceipt:
        from .ingest import abort_staged_ingest, begin_staged_ingest, commit_staged_ingest, write_chunk

        session = begin_staged_ingest(self, source_name)
        try:
            while True:
                chunk = stream.read(self.config.chunk_size_bytes)
                if not chunk:
                    break
                write_chunk(self, session, chunk)
            return commit_staged_ingest(self, manifest, session)
        except Exception:
            abort_staged_ingest(self, session)
            raise

    def bind_artifact(self, manifest: object, body_path: str | Path) -> ArtifactBinding:
        self._ensure_writable()
        normalized_manifest = _normalize_manifest(manifest)
        resolved_body_path = _normalize_source_path(body_path, field_name="body_path")
        expected_path = self._expected_object_path(
            normalized_manifest,
            suffix=self._infer_suffix(resolved_body_path, normalized_manifest.location_ref),
        )
        if resolve_path(resolved_body_path) != resolve_path(expected_path):
            raise ValidationError(
                "bind_artifact requires a body that is already located at the canonical object path.",
                code="artifact_store_noncanonical_body_path",
                details={"body_path": str(resolved_body_path), "expected_path": str(expected_path)},
            )

        size_bytes, hash_value = _compute_file_fingerprint(
            resolved_body_path,
            chunk_size=self.config.chunk_size_bytes,
        )
        existing_binding = self._load_binding(str(normalized_manifest.artifact_ref))
        if existing_binding is not None:
            if existing_binding.size_bytes == size_bytes and existing_binding.hash_value == hash_value:
                return existing_binding
            raise ConflictError(
                "artifact_ref is already bound to a different body.",
                code="artifact_binding_conflict",
                details={"artifact_ref": str(normalized_manifest.artifact_ref)},
            )

        self._verify_ingest_claims(normalized_manifest, size_bytes=size_bytes, hash_value=hash_value)

        binding = self._build_binding(
            manifest=normalized_manifest,
            source_name=resolved_body_path.name,
            ingest_mode=IngestMode.ADOPT,
            size_bytes=size_bytes,
            hash_value=hash_value,
        )
        self._write_binding(binding)
        self._append_binding_history(binding=binding, path=expected_path, action="bind")
        return binding

    def begin_staged_ingest(self, source_name: str) -> Any:
        from .ingest import begin_staged_ingest

        return begin_staged_ingest(self, source_name)

    def verify_artifact(self, artifact_ref: str, *, manifest: object | None = None) -> Any:
        from .verify import verify_artifact

        return verify_artifact(self, artifact_ref, manifest=manifest)

    def inspect_store(self) -> Any:
        from .verify import inspect_store

        return inspect_store(self)

    def verify_all(self) -> Any:
        from .verify import verify_all

        return verify_all(self)

    def refresh_verification(self, artifact_ref: str) -> Any:
        from .repair import refresh_verification

        return refresh_verification(self, artifact_ref)

    def build_repair_plan(self, *, dry_run: bool = True) -> Any:
        from .repair import build_repair_plan

        return build_repair_plan(self, dry_run=dry_run)

    def quarantine_bound_artifact(self, artifact_ref: str) -> Path:
        from .repair import quarantine_bound_artifact

        return quarantine_bound_artifact(self, artifact_ref)

    def quarantine_orphan_body(self, orphan_path: str | Path) -> Path:
        from .repair import quarantine_orphan_body

        return quarantine_orphan_body(self, orphan_path)

    def remove_abandoned_staging(self) -> list[str]:
        from .repair import remove_abandoned_staging

        return remove_abandoned_staging(self)

    def plan_migration(self, *, target_layout_version: str | None = None) -> Any:
        from .repair import plan_migration

        return plan_migration(self, target_layout_version=target_layout_version)

    def migrate_bindings(self, *, target_layout_version: str | None = None, dry_run: bool = True) -> Any:
        from .repair import migrate_bindings

        return migrate_bindings(self, target_layout_version=target_layout_version, dry_run=dry_run)

    def export_artifact(self, artifact_ref: str, *, export_root: str | Path | None = None) -> Any:
        from .export import export_artifact

        return export_artifact(self, artifact_ref, export_root=export_root)

    def import_artifact(self, manifest: object, source: str | Path, *, conflict_policy: Any = "error") -> Any:
        from .importing import import_artifact

        return import_artifact(self, manifest, source, conflict_policy=conflict_policy)

    def import_export_package(self, package_root: str | Path, *, conflict_policy: Any = "error") -> Any:
        from .importing import import_export_package

        return import_export_package(self, package_root, conflict_policy=conflict_policy)

    def plan_retention(self, *, refs_to_keep: set[str] | None = None) -> Any:
        from .retention import plan_retention

        return plan_retention(self, refs_to_keep=refs_to_keep)

    def get_artifact(self, artifact_ref: str) -> Any:
        from .read import get_artifact

        return get_artifact(self, artifact_ref)

    def artifact_exists(self, artifact_ref: str) -> bool:
        from .read import artifact_exists

        return artifact_exists(self, artifact_ref)

    def open_artifact(self, artifact_ref: str, *, mode: str = "rb") -> BinaryIO:
        from .read import open_artifact

        return open_artifact(self, artifact_ref, mode=mode)

    def read_artifact_bytes(self, artifact_ref: str) -> bytes:
        from .read import read_artifact_bytes

        return read_artifact_bytes(self, artifact_ref)

    def iter_artifact_chunks(self, artifact_ref: str, *, chunk_size: int | None = None) -> Any:
        from .read import iter_artifact_chunks

        return iter_artifact_chunks(self, artifact_ref, chunk_size=chunk_size)

    def list_refs(self) -> list[str]:
        from .read import list_refs

        return list_refs(self)

    def write_chunk(self, session: Any, chunk: bytes) -> int:
        from .ingest import write_chunk

        return write_chunk(self, session, chunk)

    def commit_staged_ingest(self, manifest: object, session: Any) -> ArtifactPutReceipt:
        from .ingest import commit_staged_ingest

        return commit_staged_ingest(self, manifest, session)

    def abort_staged_ingest(self, session: Any) -> None:
        from .ingest import abort_staged_ingest

        abort_staged_ingest(self, session)

    def _bootstrap(self) -> None:
        if self.config.read_only:
            if not self.root_path.exists():
                raise ReadOnlyStoreError(
                    "Artifact store root does not exist in read-only mode.",
                    code="artifact_store_missing_root",
                    details={"root_path": str(self.root_path)},
                )
            return
        if self.config.create_missing_dirs:
            ensure_directory(self.root_path)
            ensure_directory(self._bindings_dir())
            ensure_directory(self._objects_dir())
            ensure_directory(self._staging_dir())
            ensure_directory(self._exports_dir())
            ensure_directory(self._history_bindings_dir())
            ensure_directory(self._quarantine_dir())

    def _ensure_writable(self) -> None:
        if self.config.read_only:
            raise ReadOnlyStoreError("Artifact store is read-only.", code="artifact_store_read_only")

    def _normalize_ingest_mode(self, value: IngestMode | str | None) -> IngestMode:
        if value is None:
            return self.config.default_ingest_mode
        if isinstance(value, IngestMode):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for candidate in IngestMode:
                if candidate.value == normalized:
                    return candidate
        raise ValidationError(
            "Unsupported artifact ingest mode.",
            code="artifact_store_invalid_ingest_mode",
            details={"ingest_mode": value},
        )

    def _expected_object_path(self, manifest: ArtifactManifest, *, suffix: str) -> Path:
        kind = _sanitize_path_component(manifest.artifact_kind)
        artifact_ref = str(manifest.artifact_ref)
        ref_hash = _hash_artifact_ref(artifact_ref)
        safe_ref = _sanitize_path_component(artifact_ref)
        return self._objects_dir() / kind / ref_hash[:2] / f"{safe_ref}{suffix}"

    def _infer_suffix(self, source_path: Path | None, location_ref: str | None) -> str:
        location_suffix = _suffix_from_path(location_ref)
        if location_suffix:
            return location_suffix
        return _suffix_from_path(source_path)

    def _binding_path(self, artifact_ref: str) -> Path:
        safe_ref = _sanitize_path_component(artifact_ref)
        return self._bindings_dir() / f"{safe_ref}.binding.json"

    def _load_binding(self, artifact_ref: str) -> ArtifactBinding | None:
        path = self._binding_path(artifact_ref)
        if not path.exists():
            return None
        return self._load_binding_from_path(path)

    def _load_binding_from_path(self, path: Path) -> ArtifactBinding:
        payload = read_json(path)
        manifest_payload = payload["manifest_snapshot"]
        manifest = deserialize_artifact_manifest(manifest_payload)
        return ArtifactBinding(
            artifact_ref=str(payload["artifact_ref"]),
            artifact_kind=str(payload["artifact_kind"]),
            binding_id=str(payload["binding_id"]),
            source_name=str(payload["source_name"]),
            ingest_mode=str(payload["ingest_mode"]),
            size_bytes=int(payload["size_bytes"]),
            hash_algorithm=payload.get("hash_algorithm"),
            hash_value=payload.get("hash_value"),
            layout_version=str(payload["layout_version"]),
            created_at=str(payload["created_at"]),
            manifest_snapshot=manifest,
        )

    def _write_binding(self, binding: ArtifactBinding) -> None:
        atomic_write_json(self._binding_path(binding.artifact_ref), binding.to_dict(), indent=2, sort_keys=True)

    def _delete_binding(self, artifact_ref: str) -> None:
        self._binding_path(artifact_ref).unlink(missing_ok=True)

    def _build_binding(
        self,
        *,
        manifest: ArtifactManifest,
        source_name: str,
        ingest_mode: IngestMode,
        size_bytes: int,
        hash_value: str,
    ) -> ArtifactBinding:
        return ArtifactBinding(
            artifact_ref=str(manifest.artifact_ref),
            artifact_kind=manifest.artifact_kind,
            binding_id=f"binding-{uuid4().hex}",
            source_name=source_name,
            ingest_mode=ingest_mode.value,
            size_bytes=size_bytes,
            hash_algorithm="sha256",
            hash_value=hash_value,
            layout_version=self.config.layout_version,
            created_at=iso_utc_now(),
            manifest_snapshot=manifest,
        )

    def _verify_ingest_claims(self, manifest: ArtifactManifest, *, size_bytes: int, hash_value: str) -> None:
        mode = self.config.verification_mode
        expected_size = manifest.size_bytes
        expected_hash = manifest.hash_value
        if mode is VerificationMode.STRICT:
            if expected_size is None or expected_hash is None:
                raise ArtifactError(
                    "STRICT ingest requires manifest size_bytes and hash_value.",
                    code="artifact_store_strict_verification_missing_claims",
                    details={"artifact_ref": str(manifest.artifact_ref)},
                )
        if expected_size is not None and mode in {
            VerificationMode.MANIFEST_IF_AVAILABLE,
            VerificationMode.STRICT,
        }:
            if expected_size != size_bytes:
                raise ArtifactError(
                    "Stored body size does not match manifest.size_bytes.",
                    code="artifact_store_size_mismatch",
                    details={
                        "artifact_ref": str(manifest.artifact_ref),
                        "expected_size_bytes": expected_size,
                        "actual_size_bytes": size_bytes,
                    },
                )
        if expected_hash is not None and mode in {
            VerificationMode.MANIFEST_IF_AVAILABLE,
            VerificationMode.STRICT,
        }:
            if expected_hash != hash_value:
                raise ArtifactError(
                    "Stored body hash does not match manifest.hash_value.",
                    code="artifact_store_hash_mismatch",
                    details={
                        "artifact_ref": str(manifest.artifact_ref),
                        "expected_hash_value": expected_hash,
                        "actual_hash_value": hash_value,
                    },
                )

    def _finalize_source_to_object(self, *, source_path: Path, destination: Path, mode: IngestMode) -> None:
        ensure_directory(destination.parent)
        temp_path = destination.with_name(f"{destination.name}.{uuid4().hex}.tmp")
        try:
            if mode is IngestMode.COPY:
                shutil.copy2(source_path, temp_path)
            elif mode in {IngestMode.MOVE, IngestMode.ADOPT}:
                os.replace(source_path, temp_path)
            else:
                raise ValidationError(
                    "Unsupported artifact ingest mode.",
                    code="artifact_store_invalid_ingest_mode",
                    details={"ingest_mode": mode.value},
                )
            os.replace(temp_path, destination)
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            raise ArtifactError(
                "Failed to finalize artifact body into the store.",
                code="artifact_store_finalize_failed",
                details={"destination": str(destination), "mode": mode.value},
                cause=exc,
            ) from exc

    def _validate_adopt_source(self, source_path: Path) -> None:
        staging_dir = self._staging_dir()
        try:
            source_path.relative_to(staging_dir)
        except ValueError as exc:
            raise ValidationError(
                "ADOPT mode requires a source under the staging directory.",
                code="artifact_store_invalid_adopt_source",
                details={"source_path": str(source_path), "staging_dir": str(staging_dir)},
            ) from exc

    def _append_binding_history(self, *, binding: ArtifactBinding, path: Path, action: str) -> None:
        history_dir = self._history_bindings_dir() / _sanitize_path_component(binding.artifact_ref)
        ensure_directory(history_dir)
        event_path = history_dir / f"{iso_utc_now().replace(':', '-').replace('.', '_')}-{uuid4().hex}.json"
        atomic_write_json(
            event_path,
            {
                "action": action,
                "artifact_ref": binding.artifact_ref,
                "path": str(path),
                "recorded_at": iso_utc_now(),
                "binding": binding.to_dict(),
            },
            indent=2,
            sort_keys=True,
        )

    def _make_verification_record(self, report: Any) -> Any:
        from .models import VerificationRecord

        return VerificationRecord(
            artifact_ref=report.artifact_ref,
            status=report.status,
            checked_at=report.checked_at,
            message=report.messages[0] if report.messages else None,
        )

    def _append_verification_history(self, *, record: Any, report: Any) -> None:
        from .verify import _append_verification_history

        _append_verification_history(self, record=record, report=report)

    def _append_quarantine_history(
        self,
        *,
        kind: str,
        source_path: Path,
        destination_path: Path,
        details: dict[str, Any],
    ) -> None:
        history_dir = self.root_path / "history" / "quarantine"
        ensure_directory(history_dir)
        event_path = history_dir / f"{iso_utc_now().replace(':', '-').replace('.', '_')}-{uuid4().hex}.json"
        atomic_write_json(
            event_path,
            {
                "kind": kind,
                "recorded_at": iso_utc_now(),
                "source_path": str(source_path),
                "destination_path": str(destination_path),
                "details": details,
            },
            indent=2,
            sort_keys=True,
        )

    def _new_session_id(self, source_name: str) -> str:
        safe_name = _sanitize_path_component(source_name)
        return f"ingest-{safe_name}-{uuid4().hex}"

    def _normalize_manifest(self, manifest: object) -> ArtifactManifest:
        return _normalize_manifest(manifest)

    def _compute_file_fingerprint(self, path: Path) -> tuple[int, str]:
        return _compute_file_fingerprint(path, chunk_size=self.config.chunk_size_bytes)

    def _normalize_path(self, path: str | Path) -> Path:
        return resolve_path(path)

    def _normalize_source_path(self, source: str | Path, *, field_name: str = "source") -> Path:
        return _normalize_source_path(source, field_name=field_name)

    def _sanitize_component(self, value: str) -> str:
        return _sanitize_path_component(value)

    def _ensure_directory(self, path: str | Path) -> Path:
        return ensure_directory(path)

    def _staging_part_path(self, session_id: str) -> Path:
        return self._staging_dir() / f"{session_id}.part"

    def _staging_metadata_path(self, session_id: str) -> Path:
        return self._staging_dir() / f"{session_id}.session.json"

    def _write_staging_metadata(self, metadata: _StagingMetadata) -> None:
        atomic_write_json(self._staging_metadata_path(metadata.session_id), metadata.to_dict(), indent=2, sort_keys=True)

    def _read_staging_metadata(self, session_id: str) -> _StagingMetadata:
        return _StagingMetadata.from_mapping(read_json(self._staging_metadata_path(session_id)))

    def _delete_staging_metadata(self, session_id: str) -> None:
        self._staging_metadata_path(session_id).unlink(missing_ok=True)

    def _bindings_dir(self) -> Path:
        return self.root_path / "bindings"

    def _objects_dir(self) -> Path:
        return self.root_path / "objects"

    def _staging_dir(self) -> Path:
        return self.root_path / "staging"

    def _exports_dir(self) -> Path:
        return self.root_path / "exports"

    def _history_bindings_dir(self) -> Path:
        return self.root_path / "history" / "bindings"

    def _history_verification_dir(self, artifact_ref: str) -> Path:
        return self.root_path / "history" / "verification" / _sanitize_path_component(artifact_ref)

    def _quarantine_dir(self) -> Path:
        return self.root_path / "quarantine"


__all__ = ["ArtifactStore"]
