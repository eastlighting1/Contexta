"""Canonical models for artifact binding, verification, and transfer workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from ...common.errors import ValidationError
from ...common.time import normalize_timestamp
from ...contract import ArtifactManifest


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not value:
        return MappingProxyType({})
    return MappingProxyType({key: value[key] for key in sorted(value)})


def _normalize_required_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(
            f"{field_name} must be a string.",
            code="artifact_store_invalid_text",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    text = value.strip()
    if not text:
        raise ValidationError(
            f"{field_name} must not be blank.",
            code="artifact_store_invalid_text",
            details={"field_name": field_name},
        )
    return text


def _normalize_optional_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_required_text(value, field_name=field_name)


def _normalize_timestamp(value: str | datetime, *, field_name: str) -> str:
    if isinstance(value, datetime):
        return normalize_timestamp(value)
    if not isinstance(value, str):
        raise ValidationError(
            f"{field_name} must be a UTC timestamp string.",
            code="artifact_store_invalid_timestamp",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    text = value.strip()
    if not text:
        raise ValidationError(
            f"{field_name} must not be blank.",
            code="artifact_store_invalid_timestamp",
            details={"field_name": field_name},
        )
    return normalize_timestamp(text)


def _normalize_nonnegative_int(value: int, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(
            f"{field_name} must be an integer.",
            code="artifact_store_invalid_number",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    if value < 0:
        raise ValidationError(
            f"{field_name} must be greater than or equal to zero.",
            code="artifact_store_invalid_number",
            details={"field_name": field_name, "value": value},
        )
    return value


def _normalize_path(value: Path | str, *, field_name: str) -> Path:
    path = value if isinstance(value, Path) else Path(_normalize_required_text(value, field_name=field_name))
    if not str(path):
        raise ValidationError(
            f"{field_name} must not be blank.",
            code="artifact_store_invalid_path",
            details={"field_name": field_name},
        )
    return path


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    MISSING = "missing"
    SIZE_MISMATCH = "size_mismatch"
    HASH_MISMATCH = "hash_mismatch"


class ImportOutcome(str, Enum):
    IMPORTED = "imported"
    SKIPPED = "skipped"
    REPLACED = "replaced"
    IDEMPOTENT = "idempotent"


class ImportConflictPolicy(str, Enum):
    ERROR = "error"
    SKIP = "skip"
    REPLACE = "replace"


class RetentionAction(str, Enum):
    KEEP = "keep"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class ArtifactBinding:
    artifact_ref: str
    artifact_kind: str
    binding_id: str
    source_name: str
    ingest_mode: str
    size_bytes: int
    hash_algorithm: str | None
    hash_value: str | None
    layout_version: str
    created_at: str | datetime
    manifest_snapshot: ArtifactManifest

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_ref", _normalize_required_text(self.artifact_ref, field_name="artifact_ref"))
        object.__setattr__(self, "artifact_kind", _normalize_required_text(self.artifact_kind, field_name="artifact_kind"))
        object.__setattr__(self, "binding_id", _normalize_required_text(self.binding_id, field_name="binding_id"))
        object.__setattr__(self, "source_name", _normalize_required_text(self.source_name, field_name="source_name"))
        object.__setattr__(self, "ingest_mode", _normalize_required_text(self.ingest_mode, field_name="ingest_mode").lower())
        object.__setattr__(self, "size_bytes", _normalize_nonnegative_int(self.size_bytes, field_name="size_bytes"))
        object.__setattr__(self, "hash_algorithm", _normalize_optional_text(self.hash_algorithm, field_name="hash_algorithm"))
        object.__setattr__(self, "hash_value", _normalize_optional_text(self.hash_value, field_name="hash_value"))
        object.__setattr__(self, "layout_version", _normalize_required_text(self.layout_version, field_name="layout_version"))
        object.__setattr__(self, "created_at", _normalize_timestamp(self.created_at, field_name="created_at"))
        if not isinstance(self.manifest_snapshot, ArtifactManifest):
            raise ValidationError(
                "manifest_snapshot must be an ArtifactManifest.",
                code="artifact_store_invalid_manifest_snapshot",
                details={"type": type(self.manifest_snapshot).__name__},
            )
        if str(self.manifest_snapshot.artifact_ref) != self.artifact_ref:
            raise ValidationError(
                "binding artifact_ref must match manifest_snapshot.artifact_ref.",
                code="artifact_store_binding_manifest_mismatch",
                details={
                    "artifact_ref": self.artifact_ref,
                    "manifest_artifact_ref": str(self.manifest_snapshot.artifact_ref),
                },
            )
        if self.manifest_snapshot.artifact_kind != self.artifact_kind:
            raise ValidationError(
                "binding artifact_kind must match manifest_snapshot.artifact_kind.",
                code="artifact_store_binding_manifest_mismatch",
                details={
                    "artifact_kind": self.artifact_kind,
                    "manifest_artifact_kind": self.manifest_snapshot.artifact_kind,
                },
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_ref": self.artifact_ref,
            "artifact_kind": self.artifact_kind,
            "binding_id": self.binding_id,
            "source_name": self.source_name,
            "ingest_mode": self.ingest_mode,
            "size_bytes": self.size_bytes,
            "hash_algorithm": self.hash_algorithm,
            "hash_value": self.hash_value,
            "layout_version": self.layout_version,
            "created_at": self.created_at,
            "manifest_snapshot": self.manifest_snapshot.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ArtifactHandle:
    binding: ArtifactBinding
    path: Path | str

    def __post_init__(self) -> None:
        if not isinstance(self.binding, ArtifactBinding):
            raise ValidationError(
                "binding must be an ArtifactBinding.",
                code="artifact_store_invalid_binding",
                details={"type": type(self.binding).__name__},
            )
        object.__setattr__(self, "path", _normalize_path(self.path, field_name="path"))


@dataclass(frozen=True, slots=True)
class ArtifactPutReceipt:
    binding: ArtifactBinding
    path: Path | str
    bytes_written: int

    def __post_init__(self) -> None:
        if not isinstance(self.binding, ArtifactBinding):
            raise ValidationError(
                "binding must be an ArtifactBinding.",
                code="artifact_store_invalid_binding",
                details={"type": type(self.binding).__name__},
            )
        object.__setattr__(self, "path", _normalize_path(self.path, field_name="path"))
        object.__setattr__(self, "bytes_written", _normalize_nonnegative_int(self.bytes_written, field_name="bytes_written"))


@dataclass(frozen=True, slots=True)
class VerificationRecord:
    artifact_ref: str
    status: VerificationStatus
    checked_at: str | datetime
    message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_ref", _normalize_required_text(self.artifact_ref, field_name="artifact_ref"))
        object.__setattr__(self, "checked_at", _normalize_timestamp(self.checked_at, field_name="checked_at"))
        object.__setattr__(self, "message", _normalize_optional_text(self.message, field_name="message"))


@dataclass(frozen=True, slots=True)
class VerificationReport:
    artifact_ref: str
    status: VerificationStatus
    verified: bool
    exists: bool
    actual_size_bytes: int | None
    expected_size_bytes: int | None
    actual_hash_value: str | None
    expected_hash_value: str | None
    checked_at: str | datetime
    messages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_ref", _normalize_required_text(self.artifact_ref, field_name="artifact_ref"))
        object.__setattr__(self, "actual_size_bytes", None if self.actual_size_bytes is None else _normalize_nonnegative_int(self.actual_size_bytes, field_name="actual_size_bytes"))
        object.__setattr__(self, "expected_size_bytes", None if self.expected_size_bytes is None else _normalize_nonnegative_int(self.expected_size_bytes, field_name="expected_size_bytes"))
        object.__setattr__(self, "actual_hash_value", _normalize_optional_text(self.actual_hash_value, field_name="actual_hash_value"))
        object.__setattr__(self, "expected_hash_value", _normalize_optional_text(self.expected_hash_value, field_name="expected_hash_value"))
        object.__setattr__(self, "checked_at", _normalize_timestamp(self.checked_at, field_name="checked_at"))
        object.__setattr__(self, "messages", tuple(_normalize_required_text(item, field_name="messages[]") for item in self.messages))

        expected_verified = self.status is VerificationStatus.VERIFIED
        if self.verified != expected_verified:
            raise ValidationError(
                "verified must match status == 'verified'.",
                code="artifact_store_invalid_verification_report",
                details={"status": self.status.value, "verified": self.verified},
            )
        if self.status is VerificationStatus.MISSING and self.exists:
            raise ValidationError(
                "exists must be False when status is 'missing'.",
                code="artifact_store_invalid_verification_report",
            )
        if self.status is not VerificationStatus.MISSING and not self.exists:
            raise ValidationError(
                "exists must be True when status is not 'missing'.",
                code="artifact_store_invalid_verification_report",
            )


@dataclass(frozen=True, slots=True)
class StoreSummary:
    artifact_count: int
    total_size_bytes: int
    kinds: Mapping[str, int]
    verified_count: int
    missing_count: int
    drift_count: int
    orphan_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_count", _normalize_nonnegative_int(self.artifact_count, field_name="artifact_count"))
        object.__setattr__(self, "total_size_bytes", _normalize_nonnegative_int(self.total_size_bytes, field_name="total_size_bytes"))
        object.__setattr__(self, "verified_count", _normalize_nonnegative_int(self.verified_count, field_name="verified_count"))
        object.__setattr__(self, "missing_count", _normalize_nonnegative_int(self.missing_count, field_name="missing_count"))
        object.__setattr__(self, "drift_count", _normalize_nonnegative_int(self.drift_count, field_name="drift_count"))
        object.__setattr__(self, "orphan_count", _normalize_nonnegative_int(self.orphan_count, field_name="orphan_count"))
        frozen_kinds = { _normalize_required_text(key, field_name="kinds.key"): _normalize_nonnegative_int(value, field_name=f"kinds[{key}]") for key, value in self.kinds.items() }
        object.__setattr__(self, "kinds", MappingProxyType(dict(sorted(frozen_kinds.items()))))


@dataclass(frozen=True, slots=True)
class SweepReport:
    verification_records: tuple[VerificationRecord, ...] = ()
    missing_refs: tuple[str, ...] = ()
    drifted_refs: tuple[str, ...] = ()
    orphan_paths: tuple[Path | str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "verification_records", tuple(self.verification_records))
        object.__setattr__(self, "missing_refs", tuple(_normalize_required_text(item, field_name="missing_refs[]") for item in self.missing_refs))
        object.__setattr__(self, "drifted_refs", tuple(_normalize_required_text(item, field_name="drifted_refs[]") for item in self.drifted_refs))
        object.__setattr__(self, "orphan_paths", tuple(_normalize_path(item, field_name="orphan_paths[]") for item in self.orphan_paths))


@dataclass(frozen=True, slots=True)
class RepairPlan:
    actions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "actions", tuple(_normalize_required_text(item, field_name="actions[]") for item in self.actions))


@dataclass(frozen=True, slots=True)
class ExportReceipt:
    artifact_ref: str
    export_directory: Path | str
    body_path: Path | str
    binding_path: Path | str
    package_metadata_path: Path | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_ref", _normalize_required_text(self.artifact_ref, field_name="artifact_ref"))
        object.__setattr__(self, "export_directory", _normalize_path(self.export_directory, field_name="export_directory"))
        object.__setattr__(self, "body_path", _normalize_path(self.body_path, field_name="body_path"))
        object.__setattr__(self, "binding_path", _normalize_path(self.binding_path, field_name="binding_path"))
        object.__setattr__(self, "package_metadata_path", _normalize_path(self.package_metadata_path, field_name="package_metadata_path"))


@dataclass(frozen=True, slots=True)
class ImportReceipt:
    artifact_ref: str
    outcome: ImportOutcome
    bytes_written: int
    mapping_loss_report: Mapping[str, Any] | None = None
    quarantine_path: Path | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_ref", _normalize_required_text(self.artifact_ref, field_name="artifact_ref"))
        object.__setattr__(self, "bytes_written", _normalize_nonnegative_int(self.bytes_written, field_name="bytes_written"))
        object.__setattr__(self, "mapping_loss_report", _freeze_mapping(self.mapping_loss_report))
        if self.quarantine_path is not None:
            object.__setattr__(self, "quarantine_path", _normalize_path(self.quarantine_path, field_name="quarantine_path"))


@dataclass(frozen=True, slots=True)
class RetentionCandidate:
    artifact_ref: str
    action: RetentionAction
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_ref", _normalize_required_text(self.artifact_ref, field_name="artifact_ref"))
        object.__setattr__(self, "reason", _normalize_required_text(self.reason, field_name="reason"))


@dataclass(frozen=True, slots=True)
class RetentionPlan:
    keep: tuple[RetentionCandidate, ...] = ()
    review: tuple[RetentionCandidate, ...] = ()

    def __post_init__(self) -> None:
        keep = tuple(self.keep)
        review = tuple(self.review)
        for candidate in keep:
            if candidate.action is not RetentionAction.KEEP:
                raise ValidationError(
                    "keep entries must use RetentionAction.KEEP.",
                    code="artifact_store_invalid_retention_plan",
                    details={"artifact_ref": candidate.artifact_ref, "action": candidate.action.value},
                )
        for candidate in review:
            if candidate.action is not RetentionAction.REVIEW:
                raise ValidationError(
                    "review entries must use RetentionAction.REVIEW.",
                    code="artifact_store_invalid_retention_plan",
                    details={"artifact_ref": candidate.artifact_ref, "action": candidate.action.value},
                )
        object.__setattr__(self, "keep", keep)
        object.__setattr__(self, "review", review)


@dataclass(frozen=True, slots=True)
class IngestSession:
    session_id: str
    staging_path: Path | str
    source_name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", _normalize_required_text(self.session_id, field_name="session_id"))
        object.__setattr__(self, "staging_path", _normalize_path(self.staging_path, field_name="staging_path"))
        object.__setattr__(self, "source_name", _normalize_required_text(self.source_name, field_name="source_name"))


__all__ = [
    "ArtifactBinding",
    "ArtifactHandle",
    "ArtifactPutReceipt",
    "ExportReceipt",
    "ImportConflictPolicy",
    "ImportOutcome",
    "ImportReceipt",
    "IngestSession",
    "RepairPlan",
    "RetentionAction",
    "RetentionCandidate",
    "RetentionPlan",
    "StoreSummary",
    "SweepReport",
    "VerificationRecord",
    "VerificationReport",
    "VerificationStatus",
]
