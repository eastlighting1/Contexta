"""Workspace backup helpers for recovery orchestration."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..common.errors import RecoveryError
from ..common.io import atomic_write_json, ensure_directory, resolve_path
from ..common.time import iso_utc_now
from ..config import UnifiedConfig, config_to_mapping
from .models import BackupPlan, BackupResult


class BackupError(RecoveryError):
    """Raised when backup planning or creation fails."""


def plan_workspace_backup(
    config: UnifiedConfig,
    *,
    label: str | None = None,
    include_cache: bool = False,
    include_exports: bool = False,
) -> BackupPlan:
    workspace_root = Path(config.workspace.root_path)
    backup_root = ensure_directory(config.recovery.backup_root)
    backup_ref = _build_backup_ref(label)
    included_sections = ["config", "metadata", "records", "artifacts", "recovery"]
    if include_cache:
        included_sections.append("cache")
    if include_exports:
        included_sections.append("exports")
    estimated_bytes = sum(_estimate_section_bytes(config, section) for section in included_sections)
    notes: list[str] = []
    if not include_cache:
        notes.append("cache_excluded")
    if not include_exports:
        notes.append("exports_excluded")
    return BackupPlan(
        backup_ref=backup_ref,
        workspace_root=workspace_root,
        backup_root=backup_root,
        included_sections=tuple(included_sections),
        estimated_bytes=estimated_bytes,
        notes=tuple(notes),
    )


def create_workspace_backup(config: UnifiedConfig, plan: BackupPlan) -> BackupResult:
    destination_root = ensure_directory(plan.backup_root / plan.backup_ref)
    workspace_destination = ensure_directory(destination_root / "workspace")
    copied_sections: list[str] = []
    bytes_written = 0

    for section in plan.included_sections:
        if section == "config":
            target = ensure_directory(workspace_destination / "config") / "resolved.config.json"
            atomic_write_json(target, config_to_mapping(config), indent=2, sort_keys=True)
            copied_sections.append(section)
            bytes_written += target.stat().st_size
            continue
        source = _section_source(config, section)
        if source is None or not source.exists():
            continue
        target = workspace_destination / section
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            ensure_directory(target.parent)
            shutil.copy2(source, target)
        copied_sections.append(section)
        bytes_written += _path_size(target)

    manifest_path = destination_root / "manifest.json"
    atomic_write_json(
        manifest_path,
        {
            "backup_ref": plan.backup_ref,
            "created_at": iso_utc_now(),
            "workspace_root": str(plan.workspace_root),
            "profile_name": config.profile_name,
            "included_sections": copied_sections,
            "store_schema_versions": {
                "metadata": _safe_metadata_schema_version(config),
                "records": config.records.layout_version,
                "artifacts": config.artifacts.layout_version,
            },
            "notes": list(plan.notes),
        },
        indent=2,
        sort_keys=True,
    )
    bytes_written += manifest_path.stat().st_size
    return BackupResult(
        status="SUCCESS",
        backup_ref=plan.backup_ref,
        created_at=iso_utc_now(),
        location=destination_root,
        included_sections=tuple(copied_sections),
        bytes_written=bytes_written,
        verification_notes=("manifest_written",),
    )


def _build_backup_ref(label: str | None) -> str:
    stem = (label or "backup").strip() or "backup"
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in stem).strip("-_") or "backup"
    return f"{safe}-{iso_utc_now().replace(':', '-').replace('.', '_')}"


def _section_source(config: UnifiedConfig, section: str) -> Path | None:
    mapping = {
        "metadata": Path(config.workspace.metadata_path),
        "records": Path(config.workspace.records_path),
        "artifacts": Path(config.workspace.artifacts_path),
        "recovery": Path(config.recovery.outbox_root).parent if config.recovery.outbox_root is not None else None,
        "cache": Path(config.workspace.cache_path),
        "exports": Path(config.workspace.exports_path),
    }
    return mapping.get(section)


def _estimate_section_bytes(config: UnifiedConfig, section: str) -> int:
    source = _section_source(config, section)
    if source is None or not source.exists():
        return 0
    return _path_size(source)


def _path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def _safe_metadata_schema_version(config: UnifiedConfig) -> str | None:
    database_path = config.metadata.database_path
    if database_path is None:
        return None
    return "1"


__all__ = ["BackupError", "create_workspace_backup", "plan_workspace_backup"]
