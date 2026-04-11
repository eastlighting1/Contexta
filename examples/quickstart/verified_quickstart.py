"""Verified quickstart example for Contexta."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    MetricPayload,
    MetricRecord,
    Project,
    RecordEnvelope,
    Run,
    StageExecution,
)


PROJECT_NAME = "quickstart-proj"
RUN_NAME = "demo-run"
RUN_REF = f"run:{PROJECT_NAME}.{RUN_NAME}"


def _resolve_workspace(workspace: Path | str | None) -> Path:
    if workspace is None:
        root = Path(tempfile.mkdtemp(prefix="contexta-quickstart-"))
        return root / ".contexta"
    return Path(workspace)


def run_example(workspace: Path | str | None = None) -> dict[str, Any]:
    """Create a minimal workspace, query one run, and build a report."""

    workspace_path = _resolve_workspace(workspace)
    ctx = Contexta(
        config=UnifiedConfig(
            project_name=PROJECT_NAME,
            workspace=WorkspaceConfig(root_path=workspace_path),
        )
    )

    project = Project(
        project_ref=f"project:{PROJECT_NAME}",
        name=PROJECT_NAME,
        created_at="2024-06-01T12:00:00Z",
    )
    run = Run(
        run_ref=RUN_REF,
        project_ref=f"project:{PROJECT_NAME}",
        name=RUN_NAME,
        status="completed",
        started_at="2024-06-01T12:00:00Z",
        ended_at="2024-06-01T12:05:00Z",
    )
    stage = StageExecution(
        stage_execution_ref=f"stage:{PROJECT_NAME}.{RUN_NAME}.train",
        run_ref=RUN_REF,
        stage_name="train",
        status="completed",
        started_at="2024-06-01T12:01:00Z",
        ended_at="2024-06-01T12:04:00Z",
        order_index=0,
    )
    metric = MetricRecord(
        envelope=RecordEnvelope(
            record_ref=f"record:{PROJECT_NAME}.{RUN_NAME}.m0001",
            record_type="metric",
            recorded_at="2024-06-01T12:03:00Z",
            observed_at="2024-06-01T12:03:00Z",
            producer_ref="contexta.quickstart",
            run_ref=RUN_REF,
        ),
        payload=MetricPayload(
            metric_key="accuracy",
            value=0.93,
            value_type="float64",
        ),
    )

    store = ctx.metadata_store
    try:
        store.projects.put_project(project)
        store.runs.put_run(run)
        store.stages.put_stage_execution(stage)
        ctx.record_store.append(metric)

        runs = ctx.list_runs(PROJECT_NAME)
        snapshot = ctx.get_run_snapshot(RUN_REF)
        doc = ctx.build_snapshot_report(RUN_REF)

        report_path = ctx.config.workspace.reports_path / "quickstart-report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(doc.to_markdown(), encoding="utf-8")

        return {
            "workspace": str(workspace_path),
            "run_ref": RUN_REF,
            "runs_visible": len(runs),
            "snapshot_stage_count": len(snapshot.stages),
            "report_title": doc.title,
            "report_path": str(report_path),
        }
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the verified Contexta quickstart example.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Optional workspace root. Defaults to a temporary .contexta workspace.",
    )
    args = parser.parse_args()

    result = run_example(args.workspace)
    print(f"Workspace: {result['workspace']}")
    print(f"Run ref: {result['run_ref']}")
    print(f"Runs visible: {result['runs_visible']}")
    print(f"Report title: {result['report_title']}")
    print(f"Report path: {result['report_path']}")


if __name__ == "__main__":
    main()
