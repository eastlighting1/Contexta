"""Case Study 04: Deployment Traceability - Carlos's Story.

Carlos is an MLE who deployed a model on Friday afternoon and headed into
the weekend.  Monday morning, his product manager pings him: CTR dropped
18% overnight.  The deployed model may be the cause.

The problem: Carlos's deployment notes say "model_20250401.pkl".  He
knows it was trained last week but cannot tell:
  - Which training run produced that checkpoint?
  - What were the training metrics at that point?
  - Which dataset version was used?
  - What would rolling back actually revert to?

Without lineage, reverting is a guess.

This demo shows how Contexta's deployment registry, run snapshots, and
lineage traversal answer every one of those questions.  Three API calls
replace 30 minutes of archaeology.
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


PROJECT_NAME = "ctr-ranking-model"

_REC_COUNTER = 0


def _next_rid() -> str:
    global _REC_COUNTER
    _REC_COUNTER += 1
    return f"r{_REC_COUNTER:05d}"


def _create_training_run(
    store: Any,
    record_store: Any,
    project_name: str,
    run_name: str,
    accuracy: float,
    auc: float,
    loss: float,
    dataset_version: str,
    started_at: str,
    ended_at: str,
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

    feat_stage_ref  = f"stage:{project_name}.{run_name}.feature-engineering"
    train_stage_ref = f"stage:{project_name}.{run_name}.train"

    # feat stage ends halfway between started_at and ended_at (simple midpoint by string isn't safe — use fixed offsets)
    from datetime import datetime, timedelta, timezone
    _s = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    _e = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
    _mid = _s + (_e - _s) / 2
    feat_ended = _mid.strftime("%Y-%m-%dT%H:%M:%SZ")
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=feat_stage_ref,
            run_ref=run_ref,
            stage_name="feature-engineering",
            status="completed",
            started_at=started_at,
            ended_at=feat_ended,
            order_index=0,
        )
    )
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=train_stage_ref,
            run_ref=run_ref,
            stage_name="train",
            status="completed",
            started_at=feat_ended,
            ended_at=ended_at,
            order_index=1,
        )
    )

    obs_ts = ended_at
    for key, val in [("accuracy", accuracy), ("auc", auc), ("loss", loss)]:
        record_store.append(
            MetricRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                    record_type="metric",
                    recorded_at=obs_ts,
                    observed_at=obs_ts,
                    producer_ref="contexta.case04",
                    run_ref=run_ref,
                    stage_execution_ref=train_stage_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=MetricPayload(
                    metric_key=key,
                    value=val,
                    value_type="float64",
                    aggregation_scope="run",
                ),
            )
        )

    # Log dataset version as a structured event on the run (no stage context)
    record_store.append(
        StructuredEventRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                record_type="event",
                recorded_at=started_at,
                observed_at=started_at,
                producer_ref="contexta.case04",
                run_ref=run_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=StructuredEventPayload(
                event_key="training.dataset-registered",
                level="info",
                message=f"Training dataset version: {dataset_version}",
                attributes={"dataset_version": dataset_version},
                origin_marker="explicit_capture",
            ),
        )
    )

    return run_ref


def _create_deployment(
    store: Any,
    project_name: str,
    deploy_name: str,
    run_ref: str,
    started_at: str,
    ended_at: str,
    order_index: int,
) -> str:
    deploy_ref = f"deployment:{project_name}.{deploy_name}"
    store.deployments.put_deployment_execution(
        DeploymentExecution(
            deployment_execution_ref=deploy_ref,
            project_ref=f"project:{project_name}",
            deployment_name=deploy_name,
            status="completed",
            started_at=started_at,
            ended_at=ended_at,
            order_index=order_index,
            run_ref=run_ref,
        )
    )
    return deploy_ref


def run_example(workspace: Path | str | None = None) -> dict[str, Any]:
    """Create 3 Friday training runs + deployment, then trace the Monday incident."""

    if workspace is None:
        root = Path(tempfile.mkdtemp(prefix="contexta-case04-"))
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
    print("CASE STUDY 04: Deployment Traceability")
    print("=" * 60)
    print()
    store = ctx.metadata_store
    try:
        store.projects.put_project(
            Project(
                project_ref=f"project:{PROJECT_NAME}",
                name=PROJECT_NAME,
                created_at="2025-03-01T00:00:00Z",
                description="Click-through rate ranking model",
            )
        )

        # Three training runs from Friday (a/b/c experiments before final deploy)
        run_a_ref = _create_training_run(
            store, ctx.record_store, PROJECT_NAME, "friday-run-a",
            accuracy=0.881, auc=0.912, loss=0.308,
            dataset_version="v2025-03-28",
            started_at="2025-04-01T08:00:00Z",
            ended_at="2025-04-01T09:30:00Z",
        )
        run_b_ref = _create_training_run(
            store, ctx.record_store, PROJECT_NAME, "friday-run-b",
            accuracy=0.893, auc=0.927, loss=0.281,
            dataset_version="v2025-03-28",
            started_at="2025-04-01T09:45:00Z",
            ended_at="2025-04-01T11:15:00Z",
        )
        # run-c is what actually got deployed - best offline AUC
        run_c_ref = _create_training_run(
            store, ctx.record_store, PROJECT_NAME, "friday-run-c",
            accuracy=0.901, auc=0.938, loss=0.261,
            dataset_version="v2025-03-31",  # newer dataset - might explain the CTR drop
            started_at="2025-04-01T12:00:00Z",
            ended_at="2025-04-01T13:45:00Z",
        )

        # Previous (safe) deployment linked to run-b
        _create_deployment(
            store, PROJECT_NAME, "prod-deploy-march",
            run_b_ref,
            started_at="2025-03-28T17:00:00Z",
            ended_at="2025-03-28T17:10:00Z",
            order_index=0,
        )

        # Friday deployment linked to run-c (the one with CTR drop)
        friday_deploy_ref = _create_deployment(
            store, PROJECT_NAME, "prod-deploy-april",
            run_c_ref,
            started_at="2025-04-01T16:00:00Z",
            ended_at="2025-04-01T16:08:00Z",
            order_index=1,
        )

        # -------------------------------------------------------------------
        # Monday morning: trace the deployment
        # -------------------------------------------------------------------


        # Step 1: list deployments to find what is live
        deployments = ctx.list_deployments(PROJECT_NAME)
        print("Step 1 - All registered deployments:")
        for dep in sorted(deployments, key=lambda d: (d.started_at or "")):
            print(f"  {dep.deployment_id:<45}  run_ref={dep.run_id}")
        print()

        # Step 2: get the Friday deployment's run snapshot
        print("Step 2 - Snapshot of the deployed run (friday-run-c):")
        deployed_snap = ctx.get_run_snapshot(run_c_ref)
        metric_recs = [r for r in deployed_snap.records if r.record_type == "metric"]
        event_recs  = [r for r in deployed_snap.records if r.record_type == "event"]

        print(f"  Run name:    {deployed_snap.run.name}")
        print(f"  Status:      {deployed_snap.run.status}")
        print(f"  Started:     {deployed_snap.run.started_at}")
        print(f"  Stages:      {[s.name for s in deployed_snap.stages]}")
        print("  Metrics:")
        for m in metric_recs:
            print(f"    {m.key:<12} = {m.value:.4f}")
        # Surface the dataset version from the logged event
        dataset_event = next(
            (e for e in event_recs if e.key == "training.dataset-registered"), None
        )
        if dataset_event:
            print(f"  Dataset evt: {dataset_event.message}")
        print()

        # Step 3: traverse lineage from the deployment ref
        print("Step 3 - Lineage traversal from friday deployment:")
        lineage = ctx.traverse_lineage(friday_deploy_ref)
        print(f"  Visited nodes:  {len(lineage.visited_refs)}")
        print(f"  Edges found:    {len(lineage.edges)}")
        if lineage.edges:
            for edge in lineage.edges:
                print(f"  {edge.source_ref}  -->  {edge.target_ref}  [{edge.relation_type}]")
        else:
            # Deployment->run link is stored on the DeploymentExecution itself,
            # not as a LineageEdge relation.  Show it directly from the registry.
            matching = [d for d in deployments if d.deployment_id == friday_deploy_ref]
            if matching:
                print(f"  Direct link: {friday_deploy_ref}  -->  {matching[0].run_id}  [deployment.run_ref]")
        print()

        # Step 4: compare deployed run vs previous safe deployment
        print("Step 4 - Metric comparison: deployed (run-c) vs safe baseline (run-b):")
        comparison = ctx.compare_runs(run_c_ref, run_b_ref)
        for sc in comparison.stage_comparisons:
            for delta in sc.metric_deltas:
                if delta.left_value is None or delta.right_value is None or delta.delta is None:
                    continue
                direction = "+" if delta.delta >= 0 else ""
                print(f"  {delta.metric_key:<12} deployed={delta.left_value:.4f}  "
                      f"previous={delta.right_value:.4f}  delta={direction}{delta.delta:.4f}")
        print()

        # Roll-back decision via select_best_run (stage_name="train" for stage-scoped metrics)
        best_run_id = ctx.select_best_run(
            [run_a_ref, run_b_ref, run_c_ref], "auc",
            stage_name="train", higher_is_better=True,
        )
        best_snap = ctx.get_run_snapshot(best_run_id)
        best_auc  = next(
            (r.value for r in best_snap.records if r.record_type == "metric" and r.key == "auc"),
            None,
        )

        # Find dataset version for best run from events
        best_dataset_event = next(
            (r for r in best_snap.records
             if r.record_type == "event" and r.key == "training.dataset-registered"),
            None,
        )
        best_dataset = best_dataset_event.message if best_dataset_event else "unknown"

        # Find what dataset run-b used (the previous safe deployment)
        run_b_snap = ctx.get_run_snapshot(run_b_ref)
        run_b_dataset_event = next(
            (r for r in run_b_snap.records
             if r.record_type == "event" and r.key == "training.dataset-registered"),
            None,
        )
        run_b_dataset = run_b_dataset_event.message if run_b_dataset_event else "unknown"

        print("Roll-back analysis:")
        print(f"  Currently deployed: 'friday-run-c'  (v2025-03-31 dataset)")
        print(f"  Best offline run:    '{best_snap.run.name}'  AUC={best_auc:.4f}  {best_dataset}")
        print(f"  Previous safe deploy used: 'friday-run-b'  {run_b_dataset}")
        print()
        print("Root cause hypothesis:")
        print("  friday-run-c used dataset v2025-03-31 (2 days newer than run-b).")
        print("  New dataset may contain label noise from a schema change.")
        print("  Recommended: roll back to prod-deploy-march, audit v2025-03-31 data quality.")
        print()
        print("Carlos's Monday answer: 3 minutes, not 30.")

        all_runs = ctx.list_runs(PROJECT_NAME)
        deployed_auc = next(
            (r.value for r in metric_recs if r.key == "auc"), None
        )
        return {
            "total_training_runs": len(all_runs),
            "total_deployments": len(deployments),
            "deployed_run_name": deployed_snap.run.name,
            "deployed_run_auc": deployed_auc,
            "lineage_nodes": len(lineage.visited_refs),
            "rollback_target": best_snap.run.name,
        }
    finally:
        store.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Case Study 04: Deployment Traceability")
    parser.add_argument("--workspace", type=Path, default=None)
    args = parser.parse_args()
    run_example(args.workspace)


if __name__ == "__main__":
    main()
