"""Case Study 11: Project History Onboarding - Alex's Story.

Alex is a Team Lead at an ML platform team. A new ML engineer, Jamie, is
joining the team and needs to get up to speed on the churn prediction model.

THE SITUATION
=============
The churn model has been in production for 4 months. Over that time the
team ran 6 training experiments, made 2 deployments, and tracked
performance across multiple retrains. Jamie needs to understand:

  1. How many training runs exist and what their names are?
  2. How has accuracy evolved over time (performance trend)?
  3. Which run was ever deployed to production?
  4. Which run is objectively the best?
  5. What does a multi-run comparison report look like?

Without observability tooling, Alex would need to write a document manually
by digging through Git logs, Confluence pages, and old Slack threads -- a
task that easily takes half a day and goes stale immediately.

This demo shows how Contexta answers all 5 questions in seconds and
produces a living multi-run report that Alex can hand to Jamie on day one.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    DeploymentExecution,
    MetricPayload,
    MetricRecord,
    Project,
    RecordEnvelope,
    Run,
    StageExecution,
    StructuredEventPayload,
    StructuredEventRecord,
)


PROJECT_NAME = "churn-prediction"

_REC_COUNTER = 0

# Chronological run history: (run_name, month_label, started_at, ended_at, accuracy, auc, f1)
_RUN_HISTORY = [
    ("churn-v1-jan", "Jan", "2025-01-10T09:00:00Z", "2025-01-10T12:00:00Z", 0.821, 0.854, 0.811),
    ("churn-v2-feb", "Feb", "2025-02-07T09:00:00Z", "2025-02-07T12:00:00Z", 0.843, 0.872, 0.836),
    ("churn-v3-feb", "Feb", "2025-02-21T09:00:00Z", "2025-02-21T12:00:00Z", 0.861, 0.889, 0.854),
    ("churn-v4-mar", "Mar", "2025-03-14T09:00:00Z", "2025-03-14T12:00:00Z", 0.878, 0.907, 0.871),
    ("churn-v5-apr", "Apr", "2025-04-03T09:00:00Z", "2025-04-03T12:00:00Z", 0.894, 0.921, 0.888),
    ("churn-v6-apr", "Apr", "2025-04-18T09:00:00Z", "2025-04-18T12:00:00Z", 0.902, 0.933, 0.896),  # best
]

# Deployments: (deploy_name, linked_run_index 0-based, started_at, ended_at, order_index)
_DEPLOYMENT_HISTORY = [
    ("prod-deploy-v3", 2, "2025-02-22T15:00:00Z", "2025-02-22T15:12:00Z", 0),
    ("prod-deploy-v6", 5, "2025-04-19T14:00:00Z", "2025-04-19T14:10:00Z", 1),
]


def _next_rid() -> str:
    global _REC_COUNTER
    _REC_COUNTER += 1
    return f"r{_REC_COUNTER:05d}"


def _build_run(
    store: Any,
    record_store: Any,
    project_name: str,
    run_name: str,
    started_at: str,
    ended_at: str,
    accuracy: float,
    auc: float,
    f1: float,
) -> str:
    run_ref = f"run:{project_name}.{run_name}"

    store.runs.put_run(
        Run(
            run_ref=run_ref,
            project_ref=f"project:{project_name}",
            name=run_name,
            status="completed",
            started_at=started_at,
            ended_at=ended_at,
        )
    )

    train_ref = f"stage:{project_name}.{run_name}.train"
    eval_ref = f"stage:{project_name}.{run_name}.evaluate"

    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=train_ref,
            run_ref=run_ref,
            stage_name="train",
            status="completed",
            started_at=started_at,
            ended_at=f"{started_at[:10]}T10:30:00Z",
            order_index=0,
        )
    )
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=eval_ref,
            run_ref=run_ref,
            stage_name="evaluate",
            status="completed",
            started_at=f"{started_at[:10]}T10:30:00Z",
            ended_at=ended_at,
            order_index=1,
        )
    )

    obs_ts = ended_at
    for key, val in [("accuracy", accuracy), ("auc", auc), ("f1", f1)]:
        record_store.append(
            MetricRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                    record_type="metric",
                    recorded_at=obs_ts,
                    observed_at=obs_ts,
                    producer_ref="contexta.case11",
                    run_ref=run_ref,
                    stage_execution_ref=eval_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=MetricPayload(
                    metric_key=key,
                    value=val,
                    value_type="float64",
                ),
            )
        )

    # Log a notes event describing what changed in this run
    record_store.append(
        StructuredEventRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                record_type="event",
                recorded_at=started_at,
                observed_at=started_at,
                producer_ref="contexta.case11",
                run_ref=run_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=StructuredEventPayload(
                event_key="training.run-registered",
                level="info",
                message=f"Training run {run_name} started.",
                origin_marker="explicit_capture",
            ),
        )
    )

    return run_ref


def run_example(workspace: Path | str | None = None) -> dict[str, Any]:
    """Create 6 runs over 4 months, 2 deployments, then produce onboarding report."""

    if workspace is None:
        root = Path(tempfile.mkdtemp(prefix="contexta-case11-"))
        workspace_path = root / ".contexta"
    else:
        workspace_path = Path(workspace)

    ctx = Contexta(
        config=UnifiedConfig(
            project_name=PROJECT_NAME,
            workspace=WorkspaceConfig(root_path=workspace_path),
        )
    )

    print("=" * 60)
    print("CASE STUDY 11: Project History Onboarding")
    print("=" * 60)
    print()
    store = ctx.metadata_store
    try:
        store.projects.put_project(
            Project(
                project_ref=f"project:{PROJECT_NAME}",
                name=PROJECT_NAME,
                created_at="2025-01-01T00:00:00Z",
                description="Customer churn prediction model",
            )
        )

        run_refs: list[str] = []
        for run_name, _month, started, ended, acc, auc, f1 in _RUN_HISTORY:
            ref = _build_run(
                store, ctx.record_store, PROJECT_NAME,
                run_name=run_name,
                started_at=started,
                ended_at=ended,
                accuracy=acc, auc=auc, f1=f1,
            )
            run_refs.append(ref)

        for deploy_name, run_idx, started, ended, order in _DEPLOYMENT_HISTORY:
            store.deployments.put_deployment_execution(
                DeploymentExecution(
                    deployment_execution_ref=f"deployment:{PROJECT_NAME}.{deploy_name}",
                    project_ref=f"project:{PROJECT_NAME}",
                    deployment_name=deploy_name,
                    status="completed",
                    started_at=started,
                    ended_at=ended,
                    run_ref=run_refs[run_idx],
                    order_index=order,
                )
            )



        # Q1: list_runs
        all_runs = ctx.list_runs(PROJECT_NAME)
        print(f"Q1. Run inventory ({len(all_runs)} total runs):")
        for run in all_runs:
            print(f"  {run.name:<22}  started={str(run.started_at)[:10]}")
        print()

        # Q2: chronological performance trend
        print("Q2. Performance trend (chronological):")
        print(f"  {'Run Name':<22} {'Month':<6} {'Accuracy':<12} {'AUC':<12} {'F1'}")
        print("  " + "-" * 62)
        for run_name, month, _s, _e, acc, auc, f1 in _RUN_HISTORY:
            print(f"  {run_name:<22} {month:<6} {acc:<12.4f} {auc:<12.4f} {f1:.4f}")
        print()

        # Q3: deployment history via list_deployments
        deployments = ctx.list_deployments(PROJECT_NAME)
        print(f"Q3. Deployment history ({len(deployments)} deployments):")
        for dep in sorted(deployments, key=lambda d: (d.started_at or "")):
            print(f"  {dep.name:<22}  run_id={dep.run_id}")
        print()

        # Q4: best run via select_best_run
        best_run_id = ctx.select_best_run(run_refs, "auc", stage_name="evaluate", higher_is_better=True)
        best_snap = ctx.get_run_snapshot(best_run_id)
        best_mrecs = [r for r in best_snap.records if r.record_type == "metric"]
        best_auc = next((r.value for r in best_mrecs if r.key == "auc"), None)
        best_acc = next((r.value for r in best_mrecs if r.key == "accuracy"), None)
        best_auc_s = f"{best_auc:.4f}" if best_auc is not None else "N/A"
        best_acc_s = f"{best_acc:.4f}" if best_acc is not None else "N/A"
        print(f"Q4. Best run (by AUC): {best_snap.run.name}")
        print(f"    accuracy={best_acc_s}  auc={best_auc_s}")
        print()

        # Q5: multi-run report
        multi_report = ctx.build_multi_run_report(run_refs)
        print(f"Q5. Multi-run report: '{multi_report.title}'")
        print("    Sections:")
        for section in multi_report.sections:
            print(f"      - {section.title}")
        print()

        # Snapshot report for the best run
        snapshot_report = ctx.build_snapshot_report(best_run_id)
        print(f"    Best-run snapshot report: '{snapshot_report.title}'")
        print()
        print("Alex to Jamie:")
        print(f"  'Here is the full history of {len(all_runs)} runs across 4 months.'")
        print(f"  'Best run: {best_snap.run.name}. Currently deployed: prod-deploy-v6.'")
        print("  No document to maintain -- it regenerates on demand.")

        return {
            "total_runs": len(all_runs),
            "total_deployments": len(deployments),
            "best_run_name": best_snap.run.name,
            "best_run_auc": best_auc,
            "report_title": multi_report.title,
            "report_section_count": len(multi_report.sections),
        }
    finally:
        store.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Case Study 11: Project History Onboarding")
    parser.add_argument("--workspace", type=Path, default=None)
    args = parser.parse_args()
    run_example(args.workspace)


if __name__ == "__main__":
    main()
