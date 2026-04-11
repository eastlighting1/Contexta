"""Case Study 07: Batch Job Monitoring - David's Story.

David is a Data Engineer responsible for a nightly ETL batch job that
feature-engineers raw events into model-ready features. The job is
orchestrated by a cron scheduler and reports exit code 0 on success.

THE SITUATION
=============
Three nights ago (night 5 of 7), the job completed with exit code 0 but
silently truncated one of its output columns because an upstream vendor
changed their API response schema. The vendor's new schema dropped a
field that the join relied on -- the join succeeded but returned NULLs
where numeric values were expected, and the feature column was quietly
zeroed out.

The downstream model retrained that morning, its accuracy dropped from
0.934 to 0.871, and no alert fired because the batch job "succeeded".
David has been chasing the accuracy drop for two days without knowing
where to look.

This demo shows how DegradedRecord emissions in the feature-engineering
stage would have surfaced the issue on night 5 via diagnose_run. The
contrast is stark: all 7 batches show status=completed, but diagnostics
immediately flags the verification degradation on night 5.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    BatchExecution,
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


PROJECT_NAME = "nightly-etl-feature-engineering"
STAGE_NAME = "feature-engineering"

_REC_COUNTER = 0


def _next_rid() -> str:
    global _REC_COUNTER
    _REC_COUNTER += 1
    return f"r{_REC_COUNTER:05d}"


def _build_nightly_run(
    store: Any,
    record_store: Any,
    project_name: str,
    night: int,
    has_schema_issue: bool,
) -> str:
    """Create one nightly ETL run with a single feature-engineering stage and batch."""
    run_name = f"etl-night-{night:02d}"
    run_ref = f"run:{project_name}.{run_name}"
    date_str = f"2025-04-{night:02d}"
    run_started = f"{date_str}T01:00:00Z"
    run_ended = f"{date_str}T01:45:00Z"
    stage_started = run_started
    stage_ended = f"{date_str}T01:30:00Z"
    batch_started = f"{date_str}T01:05:00Z"
    batch_ended = f"{date_str}T01:25:00Z"
    obs_ts = stage_ended

    store.runs.put_run(
        Run(
            run_ref=run_ref,
            project_ref=f"project:{project_name}",
            name=run_name,
            status="completed",
            started_at=run_started,
            ended_at=run_ended,
        )
    )

    stage_ref = f"stage:{project_name}.{run_name}.{STAGE_NAME}"
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=stage_ref,
            run_ref=run_ref,
            stage_name=STAGE_NAME,
            status="completed",
            started_at=stage_started,
            ended_at=stage_ended,
            order_index=0,
        )
    )

    batch_name = f"batch-night-{night:02d}"
    batch_ref = f"batch:{project_name}.{run_name}.{STAGE_NAME}.{batch_name}"
    store.batches.put_batch_execution(
        BatchExecution(
            batch_execution_ref=batch_ref,
            run_ref=run_ref,
            stage_execution_ref=stage_ref,
            batch_name=batch_name,
            status="completed",
            started_at=batch_started,
            ended_at=batch_ended,
            order_index=0,
        )
    )

    # Normal metrics
    rows_processed = 0 if has_schema_issue else 118_000 + night * 200
    null_rate = 1.0 if has_schema_issue else 0.002
    record_store.append(
        MetricRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                record_type="metric",
                recorded_at=obs_ts,
                observed_at=obs_ts,
                producer_ref="contexta.case07",
                run_ref=run_ref,
                stage_execution_ref=stage_ref,
                batch_execution_ref=batch_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=MetricPayload(
                metric_key="rows-processed",
                value=float(rows_processed),
                value_type="float64",
            ),
        )
    )
    record_store.append(
        MetricRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                record_type="metric",
                recorded_at=obs_ts,
                observed_at=obs_ts,
                producer_ref="contexta.case07",
                run_ref=run_ref,
                stage_execution_ref=stage_ref,
                batch_execution_ref=batch_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=MetricPayload(
                metric_key="feature-null-rate",
                value=null_rate,
                value_type="float64",
            ),
        )
    )

    if has_schema_issue:
        # Vendor changed schema: join returned NULLs for the purchase_amount column.
        # Exit code still 0. Emit a DegradedRecord to capture the verification gap.
        record_store.append(
            DegradedRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                    record_type="degraded",
                    recorded_at=obs_ts,
                    observed_at=obs_ts,
                    producer_ref="contexta.case07",
                    run_ref=run_ref,
                    stage_execution_ref=stage_ref,
                    batch_execution_ref=batch_ref,
                    completeness_marker="partial",
                    degradation_marker="capture_gap",
                ),
                payload=DegradedPayload(
                    issue_key="etl.feature_column_null_overflow",
                    category="verification",
                    severity="warning",
                    summary=(
                        "Feature column purchase_amount was fully zeroed after "
                        "vendor schema change dropped the source field. "
                        "Join succeeded but all values are NULL. Exit code was 0."
                    ),
                    origin_marker="explicit_capture",
                    attributes={
                        "column": "purchase_amount",
                        "null_rate": 1.0,
                        "vendor_schema_version": "v2",
                        "expected_schema_version": "v1",
                    },
                ),
            )
        )
        record_store.append(
            StructuredEventRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                    record_type="event",
                    recorded_at=obs_ts,
                    observed_at=obs_ts,
                    producer_ref="contexta.case07",
                    run_ref=run_ref,
                    stage_execution_ref=stage_ref,
                    batch_execution_ref=batch_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=StructuredEventPayload(
                    event_key="etl.batch-completed",
                    level="warning",
                    message=(
                        f"Batch {batch_name} completed. "
                        "purchase_amount column zeroed (vendor schema mismatch). "
                        "Exit code: 0."
                    ),
                    origin_marker="explicit_capture",
                ),
            )
        )
    else:
        record_store.append(
            StructuredEventRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                    record_type="event",
                    recorded_at=obs_ts,
                    observed_at=obs_ts,
                    producer_ref="contexta.case07",
                    run_ref=run_ref,
                    stage_execution_ref=stage_ref,
                    batch_execution_ref=batch_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=StructuredEventPayload(
                    event_key="etl.batch-completed",
                    level="info",
                    message=f"Batch {batch_name} completed. {rows_processed} rows processed.",
                    origin_marker="explicit_capture",
                ),
            )
        )

    return run_ref


def run_example(workspace: Path | str | None = None) -> dict[str, Any]:
    """Simulate 7 nightly ETL runs; night 5 has a silent schema mismatch."""

    if workspace is None:
        root = Path(tempfile.mkdtemp(prefix="contexta-case07-"))
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
    print("CASE STUDY 07: Nightly Batch Job Monitoring")
    print("=" * 60)
    print()
    store = ctx.metadata_store
    try:
        store.projects.put_project(
            Project(
                project_ref=f"project:{PROJECT_NAME}",
                name=PROJECT_NAME,
                created_at="2025-04-01T00:00:00Z",
                description="Nightly ETL feature-engineering pipeline",
            )
        )

        # Night 5 (April 5) has the schema issue
        PROBLEM_NIGHT = 5
        night_run_refs: list[tuple[int, str]] = []
        for night in range(1, 8):
            has_issue = (night == PROBLEM_NIGHT)
            ref = _build_nightly_run(
                store, ctx.record_store, PROJECT_NAME, night, has_schema_issue=has_issue
            )
            night_run_refs.append((night, ref))

        # ------------------------------------------------------------------
        # Weekly summary table
        # ------------------------------------------------------------------
        print(f"  {'Night':<8} {'Run Name':<22} {'Rows Processed':<18} {'Null Rate':<12} {'Issues'}")
        print("  " + "-" * 72)

        problem_run_ref = None
        for night, run_ref in night_run_refs:
            snap = ctx.get_run_snapshot(run_ref)
            diag = ctx.diagnose_run(run_ref)
            metric_recs = [r for r in snap.records if r.record_type == "metric"]
            rows = next((r.value for r in metric_recs if r.key == "rows-processed"), 0.0)
            null_rate = next((r.value for r in metric_recs if r.key == "feature-null-rate"), 0.0)
            # Filter for degraded_record issues only (not missing-stage info issues)
            degraded_issues = [i for i in diag.issues if i.code == "degraded_record"]
            flag = " <-- SCHEMA MISMATCH DETECTED" if degraded_issues else ""
            print(
                f"  {night:<8} {snap.run.name:<22} {int(rows):<18} {null_rate:<12.4f} "
                f"{len(degraded_issues)} degraded{flag}"
            )
            if degraded_issues:
                problem_run_ref = run_ref

        print()

        # ------------------------------------------------------------------
        # Diagnose the problem night
        # ------------------------------------------------------------------
        if problem_run_ref is not None:
            print(f"Diagnostics for problem night (night {PROBLEM_NIGHT}):")
            diag = ctx.diagnose_run(problem_run_ref)
            for issue in diag.issues:
                print(f"  [{issue.severity.upper()}] {issue.code}: {issue.summary}")
            print()

        print("Key insight:")
        print("  All 7 nightly batch jobs show status=completed (exit code 0).")
        print(f"  Night {PROBLEM_NIGHT} DegradedRecord flagged by diagnose_run on the same night.")
        print("  Without the DegradedRecord, this silent failure is invisible.")
        print()
        print("Root cause: vendor API changed schema (v1 -> v2).")
        print("Next action: add null-rate threshold check; emit DegradedRecord if > 0.01.")

        problem_diag = ctx.diagnose_run(night_run_refs[PROBLEM_NIGHT - 1][1])
        problem_degraded = [i for i in problem_diag.issues if i.code == "degraded_record"]
        other_degraded = [
            i
            for n, ref in night_run_refs
            if n != PROBLEM_NIGHT
            for i in ctx.diagnose_run(ref).issues
            if i.code == "degraded_record"
        ]
        return {
            "nights_simulated": 7,
            "problem_night": PROBLEM_NIGHT,
            "all_statuses_completed": True,
            "problem_night_degraded_issues": len(problem_degraded),
            "other_nights_clean": len(other_degraded) == 0,
        }
    finally:
        store.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Case Study 07: Batch Job Monitoring")
    parser.add_argument("--workspace", type=Path, default=None)
    args = parser.parse_args()
    run_example(args.workspace)


if __name__ == "__main__":
    main()
