"""Verification and inspection helpers for the artifact truth store."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from ...common.errors import NotFoundError, ValidationError
from ...common.io import atomic_write_json, ensure_directory
from ...common.time import iso_utc_now
from .models import StoreSummary, SweepReport, VerificationRecord, VerificationReport, VerificationStatus

if TYPE_CHECKING:
    from ...contract import ArtifactManifest
    from .write import ArtifactStore
    from .models import ArtifactBinding


def verify_artifact(
    store: "ArtifactStore",
    artifact_ref: str,
    *,
    manifest: object | None = None,
) -> VerificationReport:
    binding = store._load_binding(artifact_ref)
    if binding is None:
        raise NotFoundError(
            "Artifact binding was not found.",
            code="artifact_store_binding_not_found",
            details={"artifact_ref": artifact_ref},
        )
    reference_manifest = binding.manifest_snapshot if manifest is None else store._normalize_manifest(manifest)
    if str(reference_manifest.artifact_ref) != binding.artifact_ref:
        raise ValidationError(
            "verification manifest must match the bound artifact_ref.",
            code="artifact_store_verification_manifest_mismatch",
            details={
                "artifact_ref": binding.artifact_ref,
                "manifest_artifact_ref": str(reference_manifest.artifact_ref),
            },
        )
    return _evaluate_binding(store, binding=binding, manifest=reference_manifest)


def inspect_store(store: "ArtifactStore") -> StoreSummary:
    bindings = _load_all_bindings(store)
    kinds: dict[str, int] = {}
    verified_count = 0
    missing_count = 0
    drift_count = 0
    total_size_bytes = 0
    for binding in bindings:
        kinds[binding.artifact_kind] = kinds.get(binding.artifact_kind, 0) + 1
        total_size_bytes += binding.size_bytes
        report = _evaluate_binding(store, binding=binding, manifest=binding.manifest_snapshot)
        if report.status is VerificationStatus.VERIFIED:
            verified_count += 1
        elif report.status is VerificationStatus.MISSING:
            missing_count += 1
        else:
            drift_count += 1
    orphan_paths = _find_orphan_paths(store, bindings)
    return StoreSummary(
        artifact_count=len(bindings),
        total_size_bytes=total_size_bytes,
        kinds=kinds,
        verified_count=verified_count,
        missing_count=missing_count,
        drift_count=drift_count,
        orphan_count=len(orphan_paths),
    )


def verify_all(store: "ArtifactStore") -> SweepReport:
    bindings = _load_all_bindings(store)
    verification_records: list[VerificationRecord] = []
    missing_refs: list[str] = []
    drifted_refs: list[str] = []
    for binding in bindings:
        report = _evaluate_binding(store, binding=binding, manifest=binding.manifest_snapshot)
        record = VerificationRecord(
            artifact_ref=binding.artifact_ref,
            status=report.status,
            checked_at=report.checked_at,
            message=report.messages[0] if report.messages else None,
        )
        verification_records.append(record)
        _append_verification_history(store, record=record, report=report)
        if report.status is VerificationStatus.MISSING:
            missing_refs.append(binding.artifact_ref)
        elif report.status in {VerificationStatus.SIZE_MISMATCH, VerificationStatus.HASH_MISMATCH}:
            drifted_refs.append(binding.artifact_ref)
    orphan_paths = _find_orphan_paths(store, bindings)
    return SweepReport(
        verification_records=tuple(verification_records),
        missing_refs=tuple(missing_refs),
        drifted_refs=tuple(drifted_refs),
        orphan_paths=tuple(orphan_paths),
    )


def _evaluate_binding(
    store: "ArtifactStore",
    *,
    binding: "ArtifactBinding",
    manifest: "ArtifactManifest",
) -> VerificationReport:
    path = store._expected_object_path(
        manifest,
        suffix=store._infer_suffix(None, manifest.location_ref),
    )
    checked_at = iso_utc_now()
    expected_size = manifest.size_bytes if manifest.size_bytes is not None else binding.size_bytes
    expected_hash = manifest.hash_value if manifest.hash_value is not None else binding.hash_value
    messages: list[str] = []

    if not path.exists():
        messages.append("artifact body is missing at the canonical object path")
        return VerificationReport(
            artifact_ref=binding.artifact_ref,
            status=VerificationStatus.MISSING,
            verified=False,
            exists=False,
            actual_size_bytes=None,
            expected_size_bytes=expected_size,
            actual_hash_value=None,
            expected_hash_value=expected_hash,
            checked_at=checked_at,
            messages=tuple(messages),
        )

    actual_size, actual_hash = store._compute_file_fingerprint(path)
    size_mismatch = expected_size is not None and actual_size != expected_size
    hash_mismatch = expected_hash is not None and actual_hash != expected_hash
    if size_mismatch:
        messages.append("artifact body size does not match the expected size")
    if hash_mismatch:
        messages.append("artifact body hash does not match the expected hash")

    if size_mismatch:
        status = VerificationStatus.SIZE_MISMATCH
    elif hash_mismatch:
        status = VerificationStatus.HASH_MISMATCH
    else:
        status = VerificationStatus.VERIFIED
        messages.append("artifact body matches the current verification claims")

    return VerificationReport(
        artifact_ref=binding.artifact_ref,
        status=status,
        verified=status is VerificationStatus.VERIFIED,
        exists=True,
        actual_size_bytes=actual_size,
        expected_size_bytes=expected_size,
        actual_hash_value=actual_hash,
        expected_hash_value=expected_hash,
        checked_at=checked_at,
        messages=tuple(messages),
    )


def _load_all_bindings(store: "ArtifactStore") -> list["ArtifactBinding"]:
    bindings_dir = store._bindings_dir()
    if not bindings_dir.exists():
        return []
    return [store._load_binding_from_path(path) for path in sorted(bindings_dir.glob("*.binding.json"))]


def _find_orphan_paths(store: "ArtifactStore", bindings: list["ArtifactBinding"]) -> list[Path]:
    object_paths = {
        store._expected_object_path(binding.manifest_snapshot, suffix=store._infer_suffix(None, binding.manifest_snapshot.location_ref))
        for binding in bindings
    }
    orphans: list[Path] = []
    objects_dir = store._objects_dir()
    if not objects_dir.exists():
        return orphans
    for path in sorted(candidate for candidate in objects_dir.rglob("*") if candidate.is_file()):
        if path not in object_paths:
            orphans.append(path)
    return orphans


def _append_verification_history(
    store: "ArtifactStore",
    *,
    record: VerificationRecord,
    report: VerificationReport,
) -> None:
    history_dir = store._history_verification_dir(record.artifact_ref)
    ensure_directory(history_dir)
    event_path = history_dir / f"{record.checked_at.replace(':', '-').replace('.', '_')}-{uuid4().hex}.json"
    atomic_write_json(
        event_path,
        {
            "artifact_ref": record.artifact_ref,
            "status": record.status.value,
            "checked_at": record.checked_at,
            "message": record.message,
            "report": {
                "artifact_ref": report.artifact_ref,
                "status": report.status.value,
                "verified": report.verified,
                "exists": report.exists,
                "actual_size_bytes": report.actual_size_bytes,
                "expected_size_bytes": report.expected_size_bytes,
                "actual_hash_value": report.actual_hash_value,
                "expected_hash_value": report.expected_hash_value,
                "checked_at": report.checked_at,
                "messages": list(report.messages),
            },
        },
        indent=2,
        sort_keys=True,
    )


__all__ = ["inspect_store", "verify_all", "verify_artifact"]
