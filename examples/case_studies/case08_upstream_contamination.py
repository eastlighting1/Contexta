"""Case Study 08: Upstream Data Contamination - MLE / Data Engineer.

THE SITUATION
=============
A data quality issue in the upstream feature store was quietly introduced
3 weeks ago when a vendor changed their API response schema. The change
caused a numeric feature (purchase_intent_score) to be silently clamped
to a narrow range [0.0, 0.1] instead of [0.0, 1.0] -- the field name
stayed the same, so no schema validation caught it.

Four model training runs happened during the contamination window
(2025-04-01 to 2025-04-21). Each run "looked fine" in isolation --
metrics were slightly lower than before but the team attributed that
to natural variance. Today (April 28), a data engineer noticed the
clamping while debugging a separate issue.

The team needs to answer three questions:
  1. Which runs were trained during the contamination window?
  2. What metrics did those runs report?
  3. How does the pre-contamination run compare to the most recent
     contaminated run?

This demo shows how Contexta answers all three questions and identifies
which contaminated run "looked best" -- a run that should NOT be
trusted or deployed.
"""

from __future__ import annotations

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
    StructuredEventPayload,
    StructuredEventRecord,
)


PROJECT_NAME = "purchase-intent-model"

_REC_COUNTER = 0


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
    contaminated: bool,
) -> str:
    """Register a training run with evaluation metrics and optional contamination event."""
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
            ended_at=f"{started_at[:10]}T10:00:00Z",
            order_index=0,
        )
    )
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=eval_ref,
            run_ref=run_ref,
            stage_name="evaluate",
            status="completed",
            started_at=f"{started_at[:10]}T10:00:00Z",
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
                    producer_ref="contexta.case08",
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

    if contaminated:
        # Tag the run as being within the contamination window
        record_store.append(
            StructuredEventRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                    record_type="event",
                    recorded_at=started_at,
                    observed_at=started_at,
                    producer_ref="contexta.case08",
                    run_ref=run_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=StructuredEventPayload(
                    event_key="data.contamination-window",
                    level="warning",
                    message=(
                        "Run trained during vendor schema contamination window "
                        "(2025-04-01 to 2025-04-21). Feature purchase_intent_score "
                        "was clamped to [0.0, 0.1] instead of [0.0, 1.0]."
                    ),
                    attributes={
                        "contamination_start": "2025-04-01",
                        "contamination_end": "2025-04-21",
                        "affected_feature": "purchase_intent_score",
                        "vendor_issue": "schema_range_clamp",
                    },
                    origin_marker="explicit_capture",
                ),
            )
        )

    return run_ref


def run_example(workspace: Path | str | None = None) -> dict[str, Any]:
    """Create 5 runs: 1 clean baseline + 4 contaminated, then answer the triage questions."""

    if workspace is None:
        root = Path(tempfile.mkdtemp(prefix="contexta-case08-"))
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
    print("CASE STUDY 08: Upstream Data Contamination")
    print("=" * 60)
    print()
    store = ctx.metadata_store
    try:
        store.projects.put_project(
            Project(
                project_ref=f"project:{PROJECT_NAME}",
                name=PROJECT_NAME,
                created_at="2025-03-01T00:00:00Z",
                description="Purchase intent prediction model",
            )
        )

        # 1 clean baseline before contamination
        baseline_ref = _build_run(
            store, ctx.record_store, PROJECT_NAME,
            run_name="run-2025-03-28",
            started_at="2025-03-28T09:00:00Z",
            ended_at="2025-03-28T12:00:00Z",
            accuracy=0.934, auc=0.961, f1=0.928,
            contaminated=False,
        )

        # 4 contaminated runs during the window
        contaminated_configs = [
            ("run-2025-04-03", "2025-04-03T09:00:00Z", "2025-04-03T12:00:00Z", 0.891, 0.912, 0.887),
            ("run-2025-04-08", "2025-04-08T09:00:00Z", "2025-04-08T12:00:00Z", 0.884, 0.905, 0.879),
            ("run-2025-04-14", "2025-04-14T09:00:00Z", "2025-04-14T12:00:00Z", 0.897, 0.918, 0.893),
            ("run-2025-04-21", "2025-04-21T09:00:00Z", "2025-04-21T12:00:00Z", 0.878, 0.901, 0.872),
        ]
        contaminated_refs: list[str] = []
        for run_name, started, ended, acc, auc, f1 in contaminated_configs:
            ref = _build_run(
                store, ctx.record_store, PROJECT_NAME,
                run_name=run_name,
                started_at=started,
                ended_at=ended,
                accuracy=acc, auc=auc, f1=f1,
                contaminated=True,
            )
            contaminated_refs.append(ref)

        latest_contaminated_ref = contaminated_refs[-1]



        # ------------------------------------------------------------------
        # Q1: Which runs were trained in the contamination window?
        # ------------------------------------------------------------------
        all_runs = ctx.list_runs(PROJECT_NAME)
        print("Q1. Runs trained during contamination window (2025-04-01 to 2025-04-21):")
        print(f"  {'Run Name':<24} {'Started At':<26} {'Contaminated'}")
        print("  " + "-" * 66)
        for run in all_runs:
            snap = ctx.get_run_snapshot(run.run_id)
            evt_keys = [r.key for r in snap.records if r.record_type == "event"]
            is_contaminated = "data.contamination-window" in evt_keys
            flag = "YES -- do not trust" if is_contaminated else "clean baseline"
            print(f"  {run.name:<24} {str(run.started_at):<26} {flag}")
        print()

        # ------------------------------------------------------------------
        # Q2: What metrics did contaminated runs report?
        # ------------------------------------------------------------------
        print("Q2. Metrics from contaminated runs:")
        print(f"  {'Run Name':<24} {'Accuracy':<12} {'AUC':<12} {'F1'}")
        print("  " + "-" * 58)
        for ref in contaminated_refs:
            snap = ctx.get_run_snapshot(ref)
            mrecs = [r for r in snap.records if r.record_type == "metric"]
            acc = next((r.value for r in mrecs if r.key == "accuracy"), None)
            auc = next((r.value for r in mrecs if r.key == "auc"), None)
            f1 = next((r.value for r in mrecs if r.key == "f1"), None)
            acc_s = f"{acc:.4f}" if acc is not None else "N/A"
            auc_s = f"{auc:.4f}" if auc is not None else "N/A"
            f1_s = f"{f1:.4f}" if f1 is not None else "N/A"
            print(f"  {snap.run.name:<24} {acc_s:<12} {auc_s:<12} {f1_s}")
        print()

        # ------------------------------------------------------------------
        # Q3: Baseline vs latest contaminated
        # ------------------------------------------------------------------
        print("Q3. Comparison: clean baseline vs latest contaminated run:")
        comparison = ctx.compare_runs(baseline_ref, latest_contaminated_ref)
        baseline_snap = ctx.get_run_snapshot(baseline_ref)
        latest_snap = ctx.get_run_snapshot(latest_contaminated_ref)
        print(f"  Baseline:    {baseline_snap.run.name}")
        print(f"  Contaminated: {latest_snap.run.name}")
        print()
        for sc in comparison.stage_comparisons:
            if sc.stage_name == "evaluate":
                for delta in sorted(sc.metric_deltas, key=lambda d: d.metric_key):
                    if delta.left_value is None or delta.right_value is None or delta.delta is None:
                        continue
                    direction = "+" if delta.delta >= 0 else ""
                    print(
                        f"  {delta.metric_key:<12} baseline={delta.left_value:.4f}  "
                        f"contaminated={delta.right_value:.4f}  "
                        f"delta={direction}{delta.delta:.4f}"
                    )
        print()

        # ------------------------------------------------------------------
        # select_best_run on contaminated window -- the "looks best" trap
        # ------------------------------------------------------------------
        best_contaminated_ref = ctx.select_best_run(
            contaminated_refs, "auc", stage_name="evaluate", higher_is_better=True
        )
        best_contaminated_snap = ctx.get_run_snapshot(best_contaminated_ref)
        best_mrecs = [r for r in best_contaminated_snap.records if r.record_type == "metric"]
        best_auc = next((r.value for r in best_mrecs if r.key == "auc"), None)
        print("select_best_run on contaminated window (by AUC):")
        print(f"  'Best' contaminated run: {best_contaminated_snap.run.name}")
        best_auc_s = f"{best_auc:.4f}" if best_auc is not None else "N/A"
        print(f"  AUC reported:            {best_auc_s}")
        print()
        print("WARNING: this run looks best within the contaminated window but")
        print("  was trained on clamped features. It should NOT be deployed.")
        print()
        print("Next action: retrain from the clean baseline data (post-vendor fix),")
        print("  quarantine all 4 contaminated runs, block promotion to production.")

        return {
            "total_runs": len(all_runs),
            "contaminated_run_count": len(contaminated_refs),
            "baseline_run": baseline_snap.run.name,
            "latest_contaminated_run": latest_snap.run.name,
            "best_contaminated_run": best_contaminated_snap.run.name,
        }
    finally:
        store.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Case Study 08: Upstream Data Contamination")
    parser.add_argument("--workspace", type=Path, default=None)
    args = parser.parse_args()
    run_example(args.workspace)


if __name__ == "__main__":
    main()
