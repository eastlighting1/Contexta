"""Backup restore helpers for recovery orchestration."""

from __future__ import annotations

import shutil
from pathlib import Path

from ..common.errors import RecoveryError
from ..common.io import ensure_directory, read_json
from ..config import UnifiedConfig, load_config
from ..store.artifacts import ArtifactStore, VaultConfig
from ..store.metadata import MetadataStore, MetadataStoreConfig
from ..store.records import RecordStore, ReplayMode, StoreConfig
from .backup import create_workspace_backup, plan_workspace_backup
from .models import RestorePlan, RestoreResult


class RestoreError(RecoveryError):
    """Raised when restore planning or application fails."""


def plan_restore(
    config: UnifiedConfig,
    backup_ref: str,
    *,
    target_workspace: Path | None = None,
    verify_only: bool = False,
) -> RestorePlan:
    source_root = _resolve_backup_root(config, backup_ref)
    staging_root = ensure_directory(config.recovery.restore_staging_root / backup_ref)
    return RestorePlan(
        backup_ref=backup_ref,
        source_root=source_root,
        target_workspace=Path(target_workspace or config.workspace.root_path),
        staging_root=staging_root,
        create_safety_backup=config.recovery.create_backup_before_restore,
        verify_only=verify_only,
        notes=("verify_only" if verify_only else "apply_restore",),
    )


def restore_workspace(config: UnifiedConfig, plan: RestorePlan) -> RestoreResult:
    manifest = _load_manifest(plan.source_root)
    staged_workspace = _materialize_staging(plan)
    verification_notes, plane_results = _verify_workspace(Path(staged_workspace))

    safety_backup_ref = None
    applied = False
    if not plan.verify_only:
        if plan.create_safety_backup and plan.target_workspace.exists():
            safety = create_workspace_backup(config, plan_workspace_backup(config, label="pre-restore-safety"))
            safety_backup_ref = safety.backup_ref
        _apply_restore(staged_workspace, plan.target_workspace)
        applied = True

    return RestoreResult(
        status="SUCCESS",
        backup_ref=plan.backup_ref,
        target_workspace=plan.target_workspace,
        applied=applied,
        plane_results=plane_results,
        safety_backup_ref=safety_backup_ref,
        verification_notes=tuple(verification_notes + [f"manifest:{manifest.get('backup_ref', plan.backup_ref)}"]),
    )


def _resolve_backup_root(config: UnifiedConfig, backup_ref: str) -> Path:
    root = Path(config.recovery.backup_root) / backup_ref
    if not root.exists():
        raise RestoreError(
            "Backup reference does not exist.",
            code="recovery_backup_not_found",
            details={"backup_ref": backup_ref, "backup_root": str(root)},
        )
    return root


def _load_manifest(source_root: Path) -> dict:
    manifest_path = source_root / "manifest.json"
    if not manifest_path.exists():
        raise RestoreError("Backup manifest is missing.", code="recovery_manifest_missing", details={"source_root": str(source_root)})
    payload = read_json(manifest_path)
    if not isinstance(payload, dict):
        raise RestoreError("Backup manifest must be a JSON object.", code="recovery_manifest_invalid")
    return payload


def _materialize_staging(plan: RestorePlan) -> Path:
    source_workspace = plan.source_root / "workspace"
    if not source_workspace.exists():
        raise RestoreError("Backup workspace payload is missing.", code="recovery_backup_workspace_missing")
    staged_workspace = plan.staging_root / "workspace"
    if staged_workspace.exists():
        shutil.rmtree(staged_workspace)
    ensure_directory(staged_workspace.parent)
    shutil.copytree(source_workspace, staged_workspace)
    return staged_workspace


def _verify_workspace(workspace_root: Path) -> tuple[list[str], dict[str, object]]:
    verification_notes: list[str] = []
    restored_config = load_config(workspace=workspace_root)

    metadata_store = MetadataStore(MetadataStoreConfig.from_unified_config(restored_config))
    try:
        runs = metadata_store.runs.list_runs()
        verification_notes.append(f"metadata_runs:{len(runs)}")
    finally:
        metadata_store.close()

    record_store = RecordStore(StoreConfig.from_unified_config(restored_config))
    replay = record_store.replay(mode=ReplayMode.TOLERANT)
    verification_notes.append(f"record_replay:{replay.record_count}")

    artifact_store = ArtifactStore(VaultConfig.from_unified_config(restored_config))
    artifact_summary = artifact_store.inspect_store()
    verification_notes.append(f"artifact_count:{artifact_summary.artifact_count}")

    plane_results = {
        "metadata": {"run_count": len(runs)},
        "records": {"record_count": replay.record_count, "integrity_state": replay.integrity_state.value},
        "artifacts": {
            "artifact_count": artifact_summary.artifact_count,
            "verified_count": artifact_summary.verified_count,
            "missing_count": artifact_summary.missing_count,
            "drift_count": artifact_summary.drift_count,
            "orphan_count": artifact_summary.orphan_count,
        },
    }
    return verification_notes, plane_results


def _apply_restore(staged_workspace: Path, target_workspace: Path) -> None:
    if target_workspace.exists():
        shutil.rmtree(target_workspace)
    ensure_directory(target_workspace.parent)
    shutil.copytree(staged_workspace, target_workspace)


__all__ = ["RestoreError", "plan_restore", "restore_workspace"]
