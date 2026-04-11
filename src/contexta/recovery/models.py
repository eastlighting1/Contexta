"""Typed result and plan models for Contexta recovery workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from ..common.errors import ValidationError


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not value:
        return MappingProxyType({})
    return MappingProxyType({key: value[key] for key in sorted(value)})


def _freeze_paths(value: Sequence[str | Path] | None) -> tuple[Path, ...]:
    if not value:
        return ()
    return tuple(Path(item) for item in value)


def _require_text(field_name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(
            f"{field_name} must be a non-blank string.",
            code="recovery_invalid_text",
            details={"field_name": field_name},
        )
    return value.strip()


def _require_bool(field_name: str, value: bool) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(
            f"{field_name} must be a bool.",
            code="recovery_invalid_bool",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    return value


def _require_non_negative_int(field_name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(
            f"{field_name} must be a non-negative integer.",
            code="recovery_invalid_number",
            details={"field_name": field_name, "value": value},
        )
    return value


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    status: str
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    details: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _require_text("status", self.status).upper())
        object.__setattr__(self, "warnings", tuple(str(item) for item in self.warnings))
        object.__setattr__(self, "notes", tuple(str(item) for item in self.notes))
        object.__setattr__(self, "details", _freeze_mapping(self.details))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class ReplayEntryResult:
    replay_ref: str
    family: str
    target: str
    status: str
    detail: str = ""
    attempts: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "replay_ref", _require_text("replay_ref", self.replay_ref))
        object.__setattr__(self, "family", _require_text("family", self.family))
        object.__setattr__(self, "target", _require_text("target", self.target))
        object.__setattr__(self, "status", _require_text("status", self.status).upper())
        object.__setattr__(self, "detail", str(self.detail))
        object.__setattr__(self, "attempts", _require_non_negative_int("attempts", self.attempts))


@dataclass(frozen=True, slots=True)
class ReplayBatchResult(RecoveryResult):
    entries: tuple[ReplayEntryResult, ...] = ()
    acknowledged_count: int = 0
    pending_count: int = 0
    dead_lettered_count: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "entries", tuple(self.entries))
        object.__setattr__(self, "acknowledged_count", _require_non_negative_int("acknowledged_count", self.acknowledged_count))
        object.__setattr__(self, "pending_count", _require_non_negative_int("pending_count", self.pending_count))
        object.__setattr__(self, "dead_lettered_count", _require_non_negative_int("dead_lettered_count", self.dead_lettered_count))

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "entries": [entry.__dict__ for entry in self.entries],
                "acknowledged_count": self.acknowledged_count,
                "pending_count": self.pending_count,
                "dead_lettered_count": self.dead_lettered_count,
            }
        )
        return payload


@dataclass(frozen=True, slots=True)
class BackupPlan:
    backup_ref: str
    workspace_root: Path
    backup_root: Path
    included_sections: tuple[str, ...]
    estimated_bytes: int
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "backup_ref", _require_text("backup_ref", self.backup_ref))
        object.__setattr__(self, "workspace_root", Path(self.workspace_root))
        object.__setattr__(self, "backup_root", Path(self.backup_root))
        object.__setattr__(self, "included_sections", tuple(str(item) for item in self.included_sections))
        object.__setattr__(self, "estimated_bytes", _require_non_negative_int("estimated_bytes", self.estimated_bytes))
        object.__setattr__(self, "notes", tuple(str(item) for item in self.notes))


@dataclass(frozen=True, slots=True)
class BackupResult(RecoveryResult):
    backup_ref: str = ""
    created_at: str = ""
    location: Path | None = None
    included_sections: tuple[str, ...] = ()
    bytes_written: int = 0
    verification_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "backup_ref", _require_text("backup_ref", self.backup_ref))
        object.__setattr__(self, "created_at", _require_text("created_at", self.created_at))
        object.__setattr__(self, "location", None if self.location is None else Path(self.location))
        object.__setattr__(self, "included_sections", tuple(str(item) for item in self.included_sections))
        object.__setattr__(self, "bytes_written", _require_non_negative_int("bytes_written", self.bytes_written))
        object.__setattr__(self, "verification_notes", tuple(str(item) for item in self.verification_notes))

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "backup_ref": self.backup_ref,
                "created_at": self.created_at,
                "location": None if self.location is None else str(self.location),
                "included_sections": list(self.included_sections),
                "bytes_written": self.bytes_written,
                "verification_notes": list(self.verification_notes),
            }
        )
        return payload


@dataclass(frozen=True, slots=True)
class RestorePlan:
    backup_ref: str
    source_root: Path
    target_workspace: Path
    staging_root: Path
    create_safety_backup: bool
    verify_only: bool = False
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "backup_ref", _require_text("backup_ref", self.backup_ref))
        object.__setattr__(self, "source_root", Path(self.source_root))
        object.__setattr__(self, "target_workspace", Path(self.target_workspace))
        object.__setattr__(self, "staging_root", Path(self.staging_root))
        object.__setattr__(self, "create_safety_backup", _require_bool("create_safety_backup", self.create_safety_backup))
        object.__setattr__(self, "verify_only", _require_bool("verify_only", self.verify_only))
        object.__setattr__(self, "notes", tuple(str(item) for item in self.notes))


@dataclass(frozen=True, slots=True)
class RestoreResult(RecoveryResult):
    backup_ref: str = ""
    target_workspace: Path | None = None
    applied: bool = False
    plane_results: Mapping[str, Any] | None = None
    safety_backup_ref: str | None = None
    verification_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "backup_ref", _require_text("backup_ref", self.backup_ref))
        object.__setattr__(self, "target_workspace", None if self.target_workspace is None else Path(self.target_workspace))
        object.__setattr__(self, "applied", _require_bool("applied", self.applied))
        object.__setattr__(self, "plane_results", _freeze_mapping(self.plane_results))
        object.__setattr__(self, "safety_backup_ref", None if self.safety_backup_ref is None else str(self.safety_backup_ref))
        object.__setattr__(self, "verification_notes", tuple(str(item) for item in self.verification_notes))

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "backup_ref": self.backup_ref,
                "target_workspace": None if self.target_workspace is None else str(self.target_workspace),
                "applied": self.applied,
                "plane_results": dict(self.plane_results),
                "safety_backup_ref": self.safety_backup_ref,
                "verification_notes": list(self.verification_notes),
            }
        )
        return payload


@dataclass(frozen=True, slots=True)
class ImportResult(RecoveryResult):
    source_root: Path | None = None
    target_workspace: Path | None = None
    created_run_count: int = 0
    created_artifact_count: int = 0
    created_record_count: int = 0
    loss_notes: tuple[str, ...] = ()
    verification_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "source_root", None if self.source_root is None else Path(self.source_root))
        object.__setattr__(self, "target_workspace", None if self.target_workspace is None else Path(self.target_workspace))
        object.__setattr__(self, "created_run_count", _require_non_negative_int("created_run_count", self.created_run_count))
        object.__setattr__(self, "created_artifact_count", _require_non_negative_int("created_artifact_count", self.created_artifact_count))
        object.__setattr__(self, "created_record_count", _require_non_negative_int("created_record_count", self.created_record_count))
        object.__setattr__(self, "loss_notes", tuple(str(item) for item in self.loss_notes))
        object.__setattr__(self, "verification_notes", tuple(str(item) for item in self.verification_notes))


__all__ = [
    "BackupPlan",
    "BackupResult",
    "ImportResult",
    "RecoveryResult",
    "ReplayBatchResult",
    "ReplayEntryResult",
    "RestorePlan",
    "RestoreResult",
]
