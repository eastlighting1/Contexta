"""Case Study 01: Scattered HPO Experiments - Sara's Story.

Sara is a Data Scientist who spent two weeks running hyperparameter
optimization experiments locally. She tried 8 configurations varying
learning rate, batch size, and data augmentation strategy.

The problem: results are scattered across folders with names like
``lr0001_bs32_aug_20250318_v3_FINAL.csv``.  When her tech lead asks
"which experiment was best?" in a sprint review, Sara cannot answer
without 20 minutes of spreadsheet archaeology.

This demo shows how Contexta solves the problem: all runs are indexed
at creation time.  Answering the question takes three API calls.
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


PROJECT_NAME = "image-classifier-hpo"

# ---------------------------------------------------------------------------
# Experiment configurations Sara actually tried (she just didn't track them)
# ---------------------------------------------------------------------------
_EXPERIMENTS = [
    # (run_name, lr, batch_size, augment, accuracy, loss, status, end_offset_min)
    ("exp-lr1e-3-bs32-aug",    0.001,  32,  True,  0.874, 0.341, "completed", 45),
    ("exp-lr1e-3-bs64-aug",    0.001,  64,  True,  0.891, 0.298, "completed", 42),
    ("exp-lr1e-3-bs128-noaug", 0.001,  128, False, 0.863, 0.372, "completed", 38),
    ("exp-lr5e-4-bs32-aug",    0.0005, 32,  True,  0.901, 0.267, "completed", 51),
    ("exp-lr5e-4-bs64-aug",    0.0005, 64,  True,  0.918, 0.231, "completed", 49),  # best
    ("exp-lr5e-4-bs128-aug",   0.0005, 128, True,  0.897, 0.281, "completed", 44),
    ("exp-lr1e-4-bs32-aug",    0.0001, 32,  True,  0.812, 0.489, "failed",    12),  # NaN loss
    ("exp-lr2e-3-bs64-noaug",  0.002,  64,  False, 0.841, 0.421, "failed",    8),   # diverged
]

_RECORD_COUNTER = 0


def _next_record_id() -> str:
    global _RECORD_COUNTER
    _RECORD_COUNTER += 1
    return f"r{_RECORD_COUNTER:05d}"


def _setup_experiment(
    store: Any,
    record_store: Any,
    project_name: str,
    run_name: str,
    accuracy: float,
    loss: float,
    lr: float,
    batch_size: int,
    augment: bool,
    status: str,
    end_offset_min: int,
) -> str:
    """Register one HPO run with its train-stage metrics."""
    run_ref   = f"run:{project_name}.{run_name}"
    stage_ref = f"stage:{project_name}.{run_name}.train"
    started   = "2025-03-18T09:00:00Z"
    ended     = f"2025-03-18T09:{end_offset_min:02d}:00Z"

    store.runs.put_run(
        Run(
            run_ref=run_ref,
            project_ref=f"project:{project_name}",
            name=run_name,
            status=status,
            started_at=started,
            ended_at=ended,
        )
    )
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=stage_ref,
            run_ref=run_ref,
            stage_name="train",
            status=status,
            started_at=started,
            ended_at=ended,
            order_index=0,
        )
    )

    obs_ts = ended

    def _metric(key: str, value: float) -> MetricRecord:
        return MetricRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{project_name}.{run_name}.{_next_record_id()}",
                record_type="metric",
                recorded_at=obs_ts,
                observed_at=obs_ts,
                producer_ref="contexta.case01",
                run_ref=run_ref,
                stage_execution_ref=stage_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=MetricPayload(
                metric_key=key,
                value=value,
                value_type="float64",
                aggregation_scope="run",
            ),
        )

    if status == "completed":
        record_store.append(_metric("accuracy", accuracy))
        record_store.append(_metric("loss", loss))

    # Log the hyperparams as a structured event regardless of outcome
    record_store.append(
        StructuredEventRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{project_name}.{run_name}.{_next_record_id()}",
                record_type="event",
                recorded_at=started,
                observed_at=started,
                producer_ref="contexta.case01",
                run_ref=run_ref,
                stage_execution_ref=stage_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=StructuredEventPayload(
                event_key="training.config-logged",
                level="info",
                message=f"lr={lr} batch-size={batch_size} augment={augment}",
                origin_marker="explicit_capture",
            ),
        )
    )

    return run_ref


def run_example(workspace: Path | str | None = None) -> dict[str, Any]:
    """Simulate Sara's 8 HPO experiments and answer 'which was best?'."""

    if workspace is None:
        root = Path(tempfile.mkdtemp(prefix="contexta-case01-"))
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
    print("CASE STUDY 01: Sara's Scattered HPO Experiments")
    print("=" * 60)
    print()

    store = ctx.metadata_store
    try:
        store.projects.put_project(
            Project(
                project_ref=f"project:{PROJECT_NAME}",
                name=PROJECT_NAME,
                created_at="2025-03-18T08:55:00Z",
                description="Image classifier hyperparameter search",
            )
        )

        run_refs = []
        for (run_name, lr, bs, aug, acc, loss, status, end_min) in _EXPERIMENTS:
            ref = _setup_experiment(
                store,
                ctx.record_store,
                PROJECT_NAME,
                run_name,
                acc,
                loss,
                lr,
                bs,
                aug,
                status,
                end_min,
            )
            run_refs.append(ref)

        # -------------------------------------------------------------------
        # With Contexta: answer the question in three API calls
        # -------------------------------------------------------------------
        all_runs = ctx.list_runs(PROJECT_NAME)
        completed_run_ids = [r.run_id for r in all_runs if r.status == "completed"]
        failed_run_ids    = [r.run_id for r in all_runs if r.status == "failed"]

        print(f"  Total runs: {len(all_runs)}  |  "
              f"Completed: {len(completed_run_ids)}  |  Failed: {len(failed_run_ids)}")
        print()

        # Collect metrics from run snapshots (.records, filtered by record_type)
        run_metrics: list[tuple[str, float, float]] = []
        for run_id in completed_run_ids:
            snap = ctx.get_run_snapshot(run_id)
            metric_recs = [r for r in snap.records if r.record_type == "metric"]
            acc_val  = next((r.value for r in metric_recs if r.key == "accuracy"), None)
            loss_val = next((r.value for r in metric_recs if r.key == "loss"), None)
            if acc_val is not None:
                run_metrics.append((snap.run.name, acc_val, loss_val or 0.0))

        run_metrics.sort(key=lambda x: x[1], reverse=True)

        print("  Rank  Run name                       Accuracy   Loss")
        print("  " + "-" * 54)
        for rank, (name, acc, loss) in enumerate(run_metrics, start=1):
            print(f"  #{rank:<4} {name:<30} {acc:.4f}   {loss:.4f}")
        print()

        # select_best_run requires stage_name because metrics are stage-scoped
        best_run_id = ctx.select_best_run(
            completed_run_ids, "accuracy", stage_name="train", higher_is_better=True
        )
        best_snap = ctx.get_run_snapshot(best_run_id)
        best_metric_recs = [r for r in best_snap.records if r.record_type == "metric"]
        best_acc  = next((r.value for r in best_metric_recs if r.key == "accuracy"), None)
        best_loss = next((r.value for r in best_metric_recs if r.key == "loss"), None)

        print(f"ANSWER: Best run is '{best_snap.run.name}'")
        print(f"        accuracy={best_acc:.4f}  loss={best_loss:.4f}")
        print()

        # Run comparison: best vs second-best completed run
        second_best_id = next(
            r.run_id for r in all_runs
            if r.status == "completed" and r.run_id != best_run_id
        )
        comparison = ctx.compare_runs(best_run_id, second_best_id)
        second_snap = ctx.get_run_snapshot(second_best_id)
        print(f"Comparison: '{best_snap.run.name}' vs '{second_snap.run.name}'")
        for sc in comparison.stage_comparisons:
            for delta in sc.metric_deltas:
                if delta.left_value is None or delta.right_value is None or delta.delta is None:
                    continue
                direction = "+" if delta.delta >= 0 else ""
                print(f"  {delta.metric_key}: {delta.left_value:.4f} vs "
                      f"{delta.right_value:.4f}  (delta={direction}{delta.delta:.4f})")
        print()

        # Multi-run report
        multi_report = ctx.build_multi_run_report(completed_run_ids)
        print(f"Multi-run report: '{multi_report.title}'")
        print("  Sections:")
        for section in multi_report.sections:
            print(f"    - {section.title}")
        print()
        print("Sara's answer in the meeting: 3 seconds, not 20 minutes.")

        return {
            "total_runs": len(all_runs),
            "completed_runs": len(completed_run_ids),
            "failed_runs": len(failed_run_ids),
            "best_run_name": best_snap.run.name,
            "best_accuracy": best_acc,
            "best_loss": best_loss,
            "report_title": multi_report.title,
            "report_section_count": len(multi_report.sections),
        }
    finally:
        store.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Case Study 01: Scattered HPO Experiments")
    parser.add_argument("--workspace", type=Path, default=None)
    args = parser.parse_args()
    run_example(args.workspace)


if __name__ == "__main__":
    main()
