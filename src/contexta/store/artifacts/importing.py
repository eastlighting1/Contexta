"""Import helpers for the artifact truth store."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from ...common.errors import ConflictError, NotFoundError, ValidationError
from ...common.io import atomic_write_json, read_json
from ...common.time import iso_utc_now
from .export import PACKAGE_FORMAT_VERSION
from .models import ImportConflictPolicy, ImportOutcome, ImportReceipt

if TYPE_CHECKING:
    from .write import ArtifactStore


def import_artifact(
    store: "ArtifactStore",
    manifest: object,
    source: str | Path,
    *,
    conflict_policy: ImportConflictPolicy | str = ImportConflictPolicy.ERROR,
    _source_kind: str = "source_file",
    _mapping_loss_report: Any = None,
) -> ImportReceipt:
    policy = _normalize_conflict_policy(conflict_policy)
    normalized_manifest = store._normalize_manifest(manifest)
    source_path = store._normalize_source_path(source)
    artifact_ref = str(normalized_manifest.artifact_ref)
    existing = store._load_binding(artifact_ref)

    if existing is None:
        receipt = store.put_artifact(normalized_manifest, source_path, mode="copy")
        _append_import_history(
            store,
            artifact_ref=artifact_ref,
            source_kind=_source_kind,
            conflict_policy=policy,
            outcome=ImportOutcome.IMPORTED,
            bytes_written=receipt.bytes_written,
            quarantine_path=None,
            mapping_loss_report=_mapping_loss_report,
        )
        return ImportReceipt(
            artifact_ref=artifact_ref,
            outcome=ImportOutcome.IMPORTED,
            bytes_written=receipt.bytes_written,
            mapping_loss_report=_mapping_loss_report,
        )

    incoming_size, incoming_hash = store._compute_file_fingerprint(source_path)
    if existing.size_bytes == incoming_size and existing.hash_value == incoming_hash:
        outcome = ImportOutcome.IDEMPOTENT if policy is not ImportConflictPolicy.SKIP else ImportOutcome.SKIPPED
        _append_import_history(
            store,
            artifact_ref=artifact_ref,
            source_kind=_source_kind,
            conflict_policy=policy,
            outcome=outcome,
            bytes_written=0,
            quarantine_path=None,
            mapping_loss_report=_mapping_loss_report,
        )
        return ImportReceipt(
            artifact_ref=artifact_ref,
            outcome=outcome,
            bytes_written=0,
            mapping_loss_report=_mapping_loss_report,
        )

    if policy is ImportConflictPolicy.SKIP:
        _append_import_history(
            store,
            artifact_ref=artifact_ref,
            source_kind=_source_kind,
            conflict_policy=policy,
            outcome=ImportOutcome.SKIPPED,
            bytes_written=0,
            quarantine_path=None,
            mapping_loss_report=_mapping_loss_report,
        )
        return ImportReceipt(
            artifact_ref=artifact_ref,
            outcome=ImportOutcome.SKIPPED,
            bytes_written=0,
            mapping_loss_report=_mapping_loss_report,
        )

    if policy is ImportConflictPolicy.ERROR:
        raise ConflictError(
            "artifact_ref is already bound to a different body.",
            code="artifact_binding_conflict",
            details={"artifact_ref": artifact_ref, "conflict_policy": policy.value},
        )

    quarantine_path = store.quarantine_bound_artifact(artifact_ref)
    store._delete_binding(artifact_ref)
    receipt = store.put_artifact(normalized_manifest, source_path, mode="copy")
    _append_import_history(
        store,
        artifact_ref=artifact_ref,
        source_kind=_source_kind,
        conflict_policy=policy,
        outcome=ImportOutcome.REPLACED,
        bytes_written=receipt.bytes_written,
        quarantine_path=quarantine_path,
        mapping_loss_report=_mapping_loss_report,
    )
    return ImportReceipt(
        artifact_ref=artifact_ref,
        outcome=ImportOutcome.REPLACED,
        bytes_written=receipt.bytes_written,
        quarantine_path=quarantine_path,
        mapping_loss_report=_mapping_loss_report,
    )


def import_export_package(
    store: "ArtifactStore",
    package_root: str | Path,
    *,
    conflict_policy: ImportConflictPolicy | str = ImportConflictPolicy.ERROR,
) -> ImportReceipt:
    root = store._normalize_path(package_root)
    if not root.exists() or not root.is_dir():
        raise NotFoundError(
            "export package directory was not found.",
            code="artifact_export_package_not_found",
            details={"package_root": str(root)},
        )
    metadata_path = root / "export.package.json"
    manifest_path = root / "manifest.snapshot.json"
    if not metadata_path.exists() or not manifest_path.exists():
        raise ValidationError(
            "export package is missing required metadata files.",
            code="artifact_export_package_invalid",
            details={"package_root": str(root)},
        )
    metadata = read_json(metadata_path)
    if metadata.get("package_format_version") != PACKAGE_FORMAT_VERSION:
        raise ValidationError(
            "unsupported export package format version.",
            code="artifact_export_package_invalid",
            details={"package_format_version": metadata.get("package_format_version")},
        )
    body_file = metadata.get("body_file")
    if not isinstance(body_file, str) or not body_file.strip():
        raise ValidationError(
            "export package metadata must include body_file.",
            code="artifact_export_package_invalid",
        )
    body_path = root / body_file
    receipt = import_artifact(
        store,
        read_json(manifest_path),
        body_path,
        conflict_policy=conflict_policy,
        _source_kind="export_package",
        _mapping_loss_report={"package_root": str(root)},
    )
    return receipt


def _normalize_conflict_policy(value: ImportConflictPolicy | str) -> ImportConflictPolicy:
    if isinstance(value, ImportConflictPolicy):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        for candidate in ImportConflictPolicy:
            if candidate.value == normalized:
                return candidate
    raise ValidationError(
        "unsupported import conflict policy.",
        code="artifact_store_invalid_conflict_policy",
        details={"conflict_policy": value},
    )


def _append_import_history(
    store: "ArtifactStore",
    *,
    artifact_ref: str,
    source_kind: str,
    conflict_policy: ImportConflictPolicy,
    outcome: ImportOutcome,
    bytes_written: int,
    quarantine_path: Path | None,
    mapping_loss_report: Any,
) -> None:
    history_dir = store.root_path / "history" / "imports" / store._sanitize_component(artifact_ref)
    store._ensure_directory(history_dir)
    event_path = history_dir / f"{iso_utc_now().replace(':', '-').replace('.', '_')}-{uuid4().hex}.json"
    atomic_write_json(
        event_path,
        {
            "artifact_ref": artifact_ref,
            "source_kind": source_kind,
            "conflict_policy": conflict_policy.value,
            "outcome": outcome.value,
            "bytes_written": bytes_written,
            "quarantine_path": None if quarantine_path is None else str(quarantine_path),
            "mapping_loss_report": mapping_loss_report,
            "imported_at": iso_utc_now(),
        },
        indent=2,
        sort_keys=True,
    )


__all__ = ["import_artifact", "import_export_package"]
