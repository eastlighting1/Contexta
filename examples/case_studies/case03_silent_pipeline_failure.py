"""Case Study 03: Silent Pipeline Failure - Nina's Story.

Nina maintains a 5-stage ML pipeline that runs nightly:
  ingest -> preprocess -> validate -> train -> evaluate

On Day 1, a schema migration caused the ``validate`` stage to pass an
empty DataFrame downstream instead of raising an exception.  The train
stage still completed (it trained on zero rows and returned default weights).
The evaluate stage reported terrible metrics - but nobody noticed for three
days because the dashboard alert threshold was never configured.

By Day 3 the production model had three days of bad checkpoints queued
for promotion.

This demo shows how DegradedRecord emissions in the validate stage would
have surfaced the issue on Day 1 via ``diagnose_run``.  The contrast is
stark: train and evaluate both show status="completed", but diagnostics
immediately flags the degraded capture in validate.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    DegradedPayload,
    DegradedRecord,
    MetricPayload,
    MetricRecord,
    Project,
    RecordEnvelope,
    Run,
    StageExecution,
    StructuredEventPayload,
    StructuredEventRecord,
)


PROJECT_NAME = "nightly-ml-pipeline"

PIPELINE_STAGES = ["ingest", "preprocess", "validate", "train", "evaluate"]

_REC_COUNTER = 0


def _next_rid() -> str:
    global _REC_COUNTER
    _REC_COUNTER += 1
    return f"r{_REC_COUNTER:05d}"


def _create_stage(
    store: Any,
    project_name: str,
    run_name: str,
    run_ref: str,
    stage_name: str,
    status: str,
    started_at: str,
    ended_at: str,
    order_index: int,
) -> str:
    stage_ref = f"stage:{project_name}.{run_name}.{stage_name}"
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=stage_ref,
            run_ref=run_ref,
            stage_name=stage_name,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            order_index=order_index,
        )
    )
    return stage_ref


def _emit_metric(
    record_store: Any,
    project_name: str,
    run_name: str,
    run_ref: str,
    stage_ref: str,
    key: str,
    value: float,
    ts: str,
) -> None:
    record_store.append(
        MetricRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                record_type="metric",
                recorded_at=ts,
                observed_at=ts,
                producer_ref="contexta.case03",
                run_ref=run_ref,
                stage_execution_ref=stage_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=MetricPayload(
                metric_key=key,
                value=value,
                value_type="float64",
                aggregation_scope="stage",
            ),
        )
    )


def _emit_degraded(
    record_store: Any,
    project_name: str,
    run_name: str,
    run_ref: str,
    stage_ref: str,
    ts: str,
    row_count: int,
) -> None:
    """Emit a DegradedRecord representing empty-dataframe pass-through."""
    record_store.append(
        DegradedRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                record_type="degraded",
                recorded_at=ts,
                observed_at=ts,
                producer_ref="contexta.case03",
                run_ref=run_ref,
                stage_execution_ref=stage_ref,
                completeness_marker="partial",
                degradation_marker="capture_gap",  # data never arrived
            ),
            payload=DegradedPayload(
                issue_key="validate.empty_dataframe_passthrough",
                category="capture",
                severity="error",
                summary=(
                    f"Validate stage received {row_count} rows after schema migration. "
                    "Empty DataFrame passed to train stage without raising an exception."
                ),
                origin_marker="explicit_capture",
                attributes={
                    "row_count": row_count,
                    "expected_minimum_rows": 10000,
                    "stage": "validate",
                },
            ),
        )
    )


def _emit_event(
    record_store: Any,
    project_name: str,
    run_name: str,
    run_ref: str,
    stage_ref: str,
    event_key: str,
    message: str,
    level: str,
    ts: str,
) -> None:
    record_store.append(
        StructuredEventRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                record_type="event",
                recorded_at=ts,
                observed_at=ts,
                producer_ref="contexta.case03",
                run_ref=run_ref,
                stage_execution_ref=stage_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=StructuredEventPayload(
                event_key=event_key,
                level=level,
                message=message,
                origin_marker="explicit_capture",
            ),
        )
    )


def _build_daily_run(
    store: Any,
    record_store: Any,
    project_name: str,
    day: int,
    silent_failure: bool,
) -> str:
    """Create one nightly run.  If silent_failure=True, validate passes empty data."""
    run_name = f"nightly-day{day}"
    run_ref  = f"run:{project_name}.{run_name}"
    date_str = f"2025-03-{17 + day:02d}"
    base     = f"{date_str}T02:00:00Z"

    store.runs.put_run(
        Run(
            run_ref=run_ref,
            project_ref=f"project:{project_name}",
            name=run_name,
            status="completed",
            started_at=base,
            ended_at=f"{date_str}T04:30:00Z",
        )
    )

    # Build all 5 stages.  Validate "succeeds" superficially even on bad days.
    stage_times = [
        ("ingest",     f"{date_str}T02:00:00Z", f"{date_str}T02:20:00Z"),
        ("preprocess", f"{date_str}T02:20:00Z", f"{date_str}T02:50:00Z"),
        ("validate",   f"{date_str}T02:50:00Z", f"{date_str}T03:00:00Z"),
        ("train",      f"{date_str}T03:00:00Z", f"{date_str}T04:00:00Z"),
        ("evaluate",   f"{date_str}T04:00:00Z", f"{date_str}T04:30:00Z"),
    ]

    stage_refs: dict[str, str] = {}
    for idx, (sname, sstart, send) in enumerate(stage_times):
        ref = _create_stage(store, project_name, run_name, run_ref, sname, "completed", sstart, send, idx)
        stage_refs[sname] = ref

    # Ingest: records loaded
    ingest_rows = 120_000 if not silent_failure else 120_000  # ingest itself is fine
    _emit_event(record_store, project_name, run_name, run_ref, stage_refs["ingest"],
                "pipeline.ingest-complete", f"Loaded {ingest_rows} rows from warehouse.",
                "info", f"{date_str}T02:19:00Z")

    # Preprocess: OK
    _emit_event(record_store, project_name, run_name, run_ref, stage_refs["preprocess"],
                "pipeline.preprocess-complete", "Feature engineering done. 118,432 valid rows.",
                "info", f"{date_str}T02:49:00Z")

    # Validate: the silent failure lives here
    validate_ts = f"{date_str}T02:59:00Z"
    if silent_failure:
        # Schema migration broke the join - validate passes 0 rows downstream
        _emit_degraded(
            record_store, project_name, run_name, run_ref,
            stage_refs["validate"], validate_ts, row_count=0,
        )
        _emit_event(record_store, project_name, run_name, run_ref, stage_refs["validate"],
                    "pipeline.validate-complete",
                    "Validation check passed (0 rows - schema join returned empty).",
                    "warning", validate_ts)
    else:
        _emit_event(record_store, project_name, run_name, run_ref, stage_refs["validate"],
                    "pipeline.validate-complete",
                    "Validation passed. 117,800 rows passed quality checks.",
                    "info", validate_ts)

    # Train: runs but with garbage data on bad days
    train_ts = f"{date_str}T03:59:00Z"
    train_loss = 2.31 if silent_failure else 0.28   # default weights = random = high loss
    train_acc  = 0.11 if silent_failure else 0.934
    _emit_metric(record_store, project_name, run_name, run_ref,
                 stage_refs["train"], "train.loss", train_loss, train_ts)
    _emit_metric(record_store, project_name, run_name, run_ref,
                 stage_refs["train"], "train.accuracy", train_acc, train_ts)
    _emit_event(record_store, project_name, run_name, run_ref, stage_refs["train"],
                "training.epoch-end", f"Training complete. loss={train_loss:.3f}",
                "info", train_ts)

    # Evaluate
    eval_ts = f"{date_str}T04:29:00Z"
    eval_acc = 0.12 if silent_failure else 0.928
    _emit_metric(record_store, project_name, run_name, run_ref,
                 stage_refs["evaluate"], "eval.accuracy", eval_acc, eval_ts)
    _emit_event(record_store, project_name, run_name, run_ref, stage_refs["evaluate"],
                "evaluation.complete", f"Eval accuracy={eval_acc:.3f}",
                "info" if not silent_failure else "warning", eval_ts)

    return run_ref


def run_example(workspace: Path | str | None = None) -> dict[str, Any]:
    """Simulate 3 days of silent validate failure and show diagnostics catch it."""

    if workspace is None:
        root = Path(tempfile.mkdtemp(prefix="contexta-case03-"))
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
    print("CASE STUDY 03: Silent Pipeline Failure")
    print("=" * 60)
    print()
    store = ctx.metadata_store
    try:
        store.projects.put_project(
            Project(
                project_ref=f"project:{PROJECT_NAME}",
                name=PROJECT_NAME,
                created_at="2025-01-01T00:00:00Z",
                description="Nightly ML training pipeline (5 stages)",
            )
        )

        day_run_refs = []
        for day in range(1, 4):  # Days 1, 2, 3 - all silent failures
            ref = _build_daily_run(store, ctx.record_store, PROJECT_NAME, day, silent_failure=True)
            day_run_refs.append((day, ref))



        issue_counts = []
        for day, run_ref in day_run_refs:
            diag = ctx.diagnose_run(run_ref)
            snap = ctx.get_run_snapshot(run_ref)

            stage_statuses = {s.name: s.status for s in snap.stages}
            degraded_issues = [i for i in diag.issues if "degraded" in i.code]
            warning_issues  = [i for i in diag.issues if i.severity == "warning"]

            print(f"Day {day} run: '{snap.run.name}'")
            print(f"  Stage statuses: " + ", ".join(
                f"{name}={status}" for name, status in stage_statuses.items()
            ))
            print(f"  Diagnostics issues: {len(diag.issues)} total  "
                  f"({len(warning_issues)} warnings, {len(degraded_issues)} degraded-record flags)")
            if diag.issues:
                for issue in diag.issues:
                    print(f"    [{issue.severity.upper()}] {issue.code}: {issue.summary}")
            print()

            issue_counts.append(len(degraded_issues))

        print("Key insight:")
        print("  train/evaluate stages both show 'completed'.")
        print("  But diagnostics flags the DegradedRecord in the validate stage.")
        print()
        if all(c > 0 for c in issue_counts):
            print("  3 days of silent failure would have been caught on Day 1")
            print("  if DegradedRecord emissions were part of the validate stage contract.")
        print()
        print("Root cause: schema migration broke the join in validate.")
        print("Next action: add row-count assertion to validate; emit DegradedRecord if < 1000 rows.")

        return {
            "days_simulated": 3,
            "all_stages_show_completed": True,
            "day1_degraded_flags": issue_counts[0],
            "day2_degraded_flags": issue_counts[1],
            "day3_degraded_flags": issue_counts[2],
            "caught_on_day_1": issue_counts[0] > 0,
        }
    finally:
        store.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Case Study 03: Silent Pipeline Failure")
    parser.add_argument("--workspace", type=Path, default=None)
    args = parser.parse_args()
    run_example(args.workspace)


if __name__ == "__main__":
    main()
