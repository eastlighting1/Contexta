"""TST-026: Workspace backup creation and restore application tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contexta.config.models import RecoveryConfig, UnifiedConfig, WorkspaceConfig
from contexta.recovery.backup import BackupError, create_workspace_backup, plan_workspace_backup
from contexta.recovery.restore import RestoreError, plan_restore, restore_workspace
from contexta.recovery.models import BackupPlan, BackupResult, RestorePlan, RestoreResult


def _make_config(tmp_path: Path) -> UnifiedConfig:
    workspace = tmp_path / ".contexta"
    workspace.mkdir(exist_ok=True)
    (workspace / "dummy.txt").write_text("workspace data")
    backup_root = tmp_path / "backups"
    backup_root.mkdir(exist_ok=True)
    staging_root = tmp_path / "staging"
    staging_root.mkdir(exist_ok=True)
    return UnifiedConfig(
        project_name="my-proj",
        workspace=WorkspaceConfig(root_path=workspace),
        recovery=RecoveryConfig(
            backup_root=backup_root,
            restore_staging_root=staging_root,
            create_backup_before_restore=False,
        ),
    )


# ---------------------------------------------------------------------------
# plan_workspace_backup
# ---------------------------------------------------------------------------

class TestPlanWorkspaceBackup:
    def test_plan_returns_backup_plan(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        assert isinstance(plan, BackupPlan)

    def test_plan_has_backup_ref(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        assert plan.backup_ref

    def test_plan_has_included_sections(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        assert len(plan.included_sections) >= 1
        assert "config" in plan.included_sections

    def test_plan_with_label(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config, label="test-label")
        assert "test-label" in plan.backup_ref

    def test_plan_with_cache_include(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config, include_cache=True)
        assert "cache" in plan.included_sections

    def test_plan_with_exports_include(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config, include_exports=True)
        assert "exports" in plan.included_sections

    def test_plan_notes_cache_excluded_by_default(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        assert "cache_excluded" in plan.notes

    def test_plan_backup_root_matches_config(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        assert plan.backup_root == config.recovery.backup_root

    def test_plan_workspace_root_matches_config(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        assert plan.workspace_root == Path(config.workspace.root_path)


# ---------------------------------------------------------------------------
# create_workspace_backup
# ---------------------------------------------------------------------------

class TestCreateWorkspaceBackup:
    def test_backup_returns_result(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        result = create_workspace_backup(config, plan)
        assert isinstance(result, BackupResult)

    def test_backup_status_is_success(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        result = create_workspace_backup(config, plan)
        assert result.status == "SUCCESS"

    def test_backup_has_backup_ref(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        result = create_workspace_backup(config, plan)
        assert result.backup_ref == plan.backup_ref

    def test_backup_location_exists(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        result = create_workspace_backup(config, plan)
        assert result.location is not None
        assert result.location.exists()

    def test_backup_manifest_exists(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        result = create_workspace_backup(config, plan)
        manifest_path = result.location / "manifest.json"
        assert manifest_path.exists()

    def test_backup_manifest_is_valid_json(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        result = create_workspace_backup(config, plan)
        manifest = json.loads((result.location / "manifest.json").read_text())
        assert "backup_ref" in manifest

    def test_backup_has_verification_notes(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        result = create_workspace_backup(config, plan)
        assert "manifest_written" in result.verification_notes

    def test_backup_bytes_written_positive(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        result = create_workspace_backup(config, plan)
        assert result.bytes_written > 0

    def test_backup_created_at_is_set(self, tmp_path):
        config = _make_config(tmp_path)
        plan = plan_workspace_backup(config)
        result = create_workspace_backup(config, plan)
        assert result.created_at


# ---------------------------------------------------------------------------
# plan_restore
# ---------------------------------------------------------------------------

class TestPlanRestore:
    def _create_backup(self, config: UnifiedConfig) -> BackupResult:
        plan = plan_workspace_backup(config)
        return create_workspace_backup(config, plan)

    def test_plan_restore_returns_plan(self, tmp_path):
        config = _make_config(tmp_path)
        backup = self._create_backup(config)
        plan = plan_restore(config, backup.backup_ref)
        assert isinstance(plan, RestorePlan)

    def test_plan_restore_has_correct_backup_ref(self, tmp_path):
        config = _make_config(tmp_path)
        backup = self._create_backup(config)
        plan = plan_restore(config, backup.backup_ref)
        assert plan.backup_ref == backup.backup_ref

    def test_plan_restore_source_root_exists(self, tmp_path):
        config = _make_config(tmp_path)
        backup = self._create_backup(config)
        plan = plan_restore(config, backup.backup_ref)
        assert plan.source_root.exists()

    def test_plan_restore_verify_only_flag(self, tmp_path):
        config = _make_config(tmp_path)
        backup = self._create_backup(config)
        plan = plan_restore(config, backup.backup_ref, verify_only=True)
        assert plan.verify_only is True

    def test_plan_restore_missing_backup_raises(self, tmp_path):
        config = _make_config(tmp_path)
        with pytest.raises(RestoreError):
            plan_restore(config, "nonexistent-backup-ref")

    def test_plan_restore_has_staging_root(self, tmp_path):
        config = _make_config(tmp_path)
        backup = self._create_backup(config)
        plan = plan_restore(config, backup.backup_ref)
        assert plan.staging_root is not None


# ---------------------------------------------------------------------------
# restore_workspace (verify_only=True — no actual data overwrite)
# ---------------------------------------------------------------------------

class TestRestoreWorkspace:
    def _create_backup(self, config: UnifiedConfig) -> BackupResult:
        plan = plan_workspace_backup(config)
        return create_workspace_backup(config, plan)

    def test_restore_verify_only_returns_result(self, tmp_path):
        config = _make_config(tmp_path)
        backup = self._create_backup(config)
        restore_plan = plan_restore(config, backup.backup_ref, verify_only=True)
        result = restore_workspace(config, restore_plan)
        assert isinstance(result, RestoreResult)

    def test_restore_verify_only_applied_is_false(self, tmp_path):
        config = _make_config(tmp_path)
        backup = self._create_backup(config)
        restore_plan = plan_restore(config, backup.backup_ref, verify_only=True)
        result = restore_workspace(config, restore_plan)
        assert result.applied is False

    def test_restore_verify_only_status_is_success(self, tmp_path):
        config = _make_config(tmp_path)
        backup = self._create_backup(config)
        restore_plan = plan_restore(config, backup.backup_ref, verify_only=True)
        result = restore_workspace(config, restore_plan)
        assert result.status == "SUCCESS"

    def test_restore_verify_only_has_verification_notes(self, tmp_path):
        config = _make_config(tmp_path)
        backup = self._create_backup(config)
        restore_plan = plan_restore(config, backup.backup_ref, verify_only=True)
        result = restore_workspace(config, restore_plan)
        assert len(result.verification_notes) >= 1

    def test_restore_verify_only_has_plane_results(self, tmp_path):
        config = _make_config(tmp_path)
        backup = self._create_backup(config)
        restore_plan = plan_restore(config, backup.backup_ref, verify_only=True)
        result = restore_workspace(config, restore_plan)
        assert result.plane_results is not None

    def test_restore_verify_only_backup_ref_preserved(self, tmp_path):
        config = _make_config(tmp_path)
        backup = self._create_backup(config)
        restore_plan = plan_restore(config, backup.backup_ref, verify_only=True)
        result = restore_workspace(config, restore_plan)
        assert result.backup_ref == backup.backup_ref
