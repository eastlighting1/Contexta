"""Backup and verify-only restore example for Contexta."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any

from contexta import Contexta
from contexta.config import RecoveryConfig, UnifiedConfig, WorkspaceConfig
from contexta.contract import MetricPayload, MetricRecord, Project, RecordEnvelope, Run, StageExecution
from contexta.recovery import create_workspace_backup, plan_restore, plan_workspace_backup, restore_workspace


PROJECT_NAME = "recovery-proj"
RUN_NAME = "demo-run"
RUN_REF = f"run:{PROJECT_NAME}.{RUN_NAME}"


def _resolve_root(root: Path | str | None) -> Path:
    if root is None:
        return Path(tempfile.mkdtemp(prefix="contexta-recovery-demo-"))
    return Path(root)


def _seed_workspace(config: UnifiedConfig) -> None:
    ctx = Contexta(config=config)
    store = ctx.metadata_store
    try:
        store.projects.put_project(
            Project(
                project_ref=f"project:{PROJECT_NAME}",
                name=PROJECT_NAME,
                created_at="2024-06-01T12:00:00Z",
            )
        )
        store.runs.put_run(
            Run(
                run_ref=RUN_REF,
                project_ref=f"project:{PROJECT_NAME}",
                name=RUN_NAME,
                status="completed",
                started_at="2024-06-01T12:00:00Z",
                ended_at="2024-06-01T12:05:00Z",
            )
        )
        store.stages.put_stage_execution(
            StageExecution(
                stage_execution_ref=f"stage:{PROJECT_NAME}.{RUN_NAME}.train",
                run_ref=RUN_REF,
                stage_name="train",
                status="completed",
                started_at="2024-06-01T12:01:00Z",
                ended_at="2024-06-01T12:04:00Z",
                order_index=0,
            )
        )
        ctx.record_store.append(
            MetricRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{PROJECT_NAME}.{RUN_NAME}.m0001",
                    record_type="metric",
                    recorded_at="2024-06-01T12:03:00Z",
                    observed_at="2024-06-01T12:03:00Z",
                    producer_ref="contexta.recovery.example",
                    run_ref=RUN_REF,
                ),
                payload=MetricPayload(metric_key="accuracy", value=0.93, value_type="float64"),
            )
        )
    finally:
        store.close()


def run_example(root: Path | str | None = None) -> dict[str, Any]:
    base_root = _resolve_root(root)
    workspace = base_root / ".contexta"
    backup_root = base_root / "backups"
    restore_staging_root = base_root / "restore-staging"

    config = UnifiedConfig(
        project_name=PROJECT_NAME,
        workspace=WorkspaceConfig(root_path=workspace),
        recovery=RecoveryConfig(
            backup_root=backup_root,
            restore_staging_root=restore_staging_root,
            create_backup_before_restore=False,
        ),
    )

    _seed_workspace(config)
    backup_plan = plan_workspace_backup(config, label="ops-demo")
    backup_result = create_workspace_backup(config, backup_plan)
    restore_plan = plan_restore(config, backup_result.backup_ref, verify_only=True)
    restore_result = restore_workspace(config, restore_plan)

    return {
        "workspace": str(workspace),
        "backup_ref": backup_result.backup_ref,
        "backup_location": str(backup_result.location),
        "included_sections": list(backup_result.included_sections),
        "restore_status": restore_result.status,
        "restore_applied": restore_result.applied,
        "verification_notes": list(restore_result.verification_notes),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Contexta backup/restore recovery example.")
    parser.add_argument("--root", type=Path, default=None, help="Optional demo root directory.")
    args = parser.parse_args()

    result = run_example(args.root)
    print(f"Workspace: {result['workspace']}")
    print(f"Backup ref: {result['backup_ref']}")
    print(f"Backup location: {result['backup_location']}")
    print(f"Included sections: {', '.join(result['included_sections'])}")
    print(f"Restore status: {result['restore_status']}")
    print(f"Restore applied: {result['restore_applied']}")


if __name__ == "__main__":
    main()
