"""Case Study 10: RAG Pipeline Stage Decomposition - AI Engineer's Story.

THE SITUATION
=============
An AI Engineer has built a 4-stage RAG pipeline for a knowledge-base
assistant:

  retrieve --> rerank --> generate --> evaluate

The pipeline has been running in production for two weeks. End-to-end
answer quality (measured as answer_quality, 0-1) has dropped from 0.87
in the baseline deployment to 0.64 in the latest version. Nobody knows
which stage is causing it.

Hypotheses:
  - The retrieve stage might be returning lower-precision documents.
  - The rerank model might have degraded on new query types.
  - The generation model might have drifted.
  - Or it could be measurement noise.

Without stage-level observability, the team can only look at the final
answer_quality number and guess. With stage-level metrics logged per
stage, the root cause is immediately visible.

This demo creates two runs (v1 baseline, v2 degraded), logs metrics at
each stage, uses compare_runs to surface which stage changed, and uses
diagnose_run to surface any warnings.
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


PROJECT_NAME = "knowledge-base-rag"

RAG_STAGES = ["retrieve", "rerank", "generate", "evaluate"]

_REC_COUNTER = 0


def _next_rid() -> str:
    global _REC_COUNTER
    _REC_COUNTER += 1
    return f"r{_REC_COUNTER:05d}"


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
                producer_ref="contexta.case10",
                run_ref=run_ref,
                stage_execution_ref=stage_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=MetricPayload(
                metric_key=key,
                value=value,
                value_type="float64",
            ),
        )
    )


def _build_rag_run(
    store: Any,
    record_store: Any,
    project_name: str,
    run_name: str,
    started_at: str,
    ended_at: str,
    stage_metrics: dict[str, dict[str, float]],
    emit_retrieval_warning: bool = False,
) -> str:
    """Create a RAG pipeline run with per-stage metrics."""
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

    # Build 4 stages with staggered timestamps
    date_str = started_at[:10]
    stage_time_slots = [
        (f"{date_str}T09:00:00Z", f"{date_str}T09:10:00Z"),
        (f"{date_str}T09:10:00Z", f"{date_str}T09:20:00Z"),
        (f"{date_str}T09:20:00Z", f"{date_str}T09:40:00Z"),
        (f"{date_str}T09:40:00Z", f"{date_str}T09:50:00Z"),
    ]

    stage_refs: dict[str, str] = {}
    for idx, stage_name in enumerate(RAG_STAGES):
        stage_ref = f"stage:{project_name}.{run_name}.{stage_name}"
        slot_start, slot_end = stage_time_slots[idx]
        store.stages.put_stage_execution(
            StageExecution(
                stage_execution_ref=stage_ref,
                run_ref=run_ref,
                stage_name=stage_name,
                status="completed",
                started_at=slot_start,
                ended_at=slot_end,
                order_index=idx,
            )
        )
        stage_refs[stage_name] = stage_ref

    # Emit metrics per stage
    for stage_name, metrics in stage_metrics.items():
        stage_ref = stage_refs[stage_name]
        ts = stage_time_slots[RAG_STAGES.index(stage_name)][1]
        for key, val in metrics.items():
            _emit_metric(record_store, project_name, run_name, run_ref, stage_ref, key, val, ts)

    # Optionally emit a degradation warning on the retrieve stage
    if emit_retrieval_warning:
        retrieve_ref = stage_refs["retrieve"]
        ts = stage_time_slots[0][1]
        record_store.append(
            DegradedRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                    record_type="degraded",
                    recorded_at=ts,
                    observed_at=ts,
                    producer_ref="contexta.case10",
                    run_ref=run_ref,
                    stage_execution_ref=retrieve_ref,
                    completeness_marker="partial",
                    degradation_marker="capture_gap",
                ),
                payload=DegradedPayload(
                    issue_key="rag.retrieval_precision_drop",
                    category="verification",
                    severity="warning",
                    summary=(
                        "Retrieval precision dropped below threshold (0.55 < 0.70). "
                        "Index may contain stale or out-of-distribution documents. "
                        "Downstream rerank and generate stages affected."
                    ),
                    origin_marker="explicit_capture",
                    attributes={
                        "retrieval-precision": 0.55,
                        "threshold": 0.70,
                        "top-k": 5,
                    },
                ),
            )
        )
        record_store.append(
            StructuredEventRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                    record_type="event",
                    recorded_at=ts,
                    observed_at=ts,
                    producer_ref="contexta.case10",
                    run_ref=run_ref,
                    stage_execution_ref=retrieve_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=StructuredEventPayload(
                    event_key="rag.retrieval-warning",
                    level="warning",
                    message="Retrieval precision below threshold. Cascading quality issues expected.",
                    origin_marker="explicit_capture",
                ),
            )
        )

    return run_ref


def run_example(workspace: Path | str | None = None) -> dict[str, Any]:
    """Create v1 baseline and v2 degraded RAG runs, then decompose the quality drop."""

    if workspace is None:
        root = Path(tempfile.mkdtemp(prefix="contexta-case10-"))
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
    print("CASE STUDY 10: RAG Pipeline Stage Decomposition")
    print("=" * 60)
    print()
    store = ctx.metadata_store
    try:
        store.projects.put_project(
            Project(
                project_ref=f"project:{PROJECT_NAME}",
                name=PROJECT_NAME,
                created_at="2025-04-01T00:00:00Z",
                description="Knowledge-base RAG pipeline (4 stages)",
            )
        )

        # v1: balanced quality across all stages
        v1_stage_metrics = {
            "retrieve":  {"retrieval-precision": 0.82, "retrieval-recall": 0.79},
            "rerank":    {"rerank-ndcg": 0.81, "rerank-mrr": 0.77},
            "generate":  {"generation-fluency": 0.88, "generation-coherence": 0.85},
            "evaluate":  {"answer-quality": 0.87, "faithfulness": 0.84},
        }
        v1_ref = _build_rag_run(
            store, ctx.record_store, PROJECT_NAME,
            run_name="rag-v1-baseline",
            started_at="2025-04-01T09:00:00Z",
            ended_at="2025-04-01T09:50:00Z",
            stage_metrics=v1_stage_metrics,
            emit_retrieval_warning=False,
        )

        # v2: retrieval precision drops -> cascading degradation downstream
        v2_stage_metrics = {
            "retrieve":  {"retrieval-precision": 0.55, "retrieval-recall": 0.51},
            "rerank":    {"rerank-ndcg": 0.61, "rerank-mrr": 0.57},
            "generate":  {"generation-fluency": 0.76, "generation-coherence": 0.68},
            "evaluate":  {"answer-quality": 0.64, "faithfulness": 0.59},
        }
        v2_ref = _build_rag_run(
            store, ctx.record_store, PROJECT_NAME,
            run_name="rag-v2-degraded",
            started_at="2025-04-15T09:00:00Z",
            ended_at="2025-04-15T09:50:00Z",
            stage_metrics=v2_stage_metrics,
            emit_retrieval_warning=True,
        )

        # ------------------------------------------------------------------
        # Stage-level metric comparison
        # ------------------------------------------------------------------
        comparison = ctx.compare_runs(v1_ref, v2_ref)
        for sc in comparison.stage_comparisons:
            print(f"  Stage: {sc.stage_name}")
            for delta in sorted(sc.metric_deltas, key=lambda d: d.metric_key):
                if delta.left_value is None or delta.right_value is None or delta.delta is None:
                    print(f"    {delta.metric_key:<26} v1=N/A  v2=N/A")
                    continue
                direction = "+" if delta.delta >= 0 else ""
                flag = " <-- ROOT STAGE" if sc.stage_name == "retrieve" and abs(delta.delta) > 0.2 else ""
                print(
                    f"    {delta.metric_key:<26} v1={delta.left_value:.3f}  "
                    f"v2={delta.right_value:.3f}  delta={direction}{delta.delta:.3f}{flag}"
                )
            print()

        # ------------------------------------------------------------------
        # Diagnostics on v2
        # ------------------------------------------------------------------
        print("diagnose_run on v2 (degraded run):")
        diag = ctx.diagnose_run(v2_ref)
        if diag.issues:
            for issue in diag.issues:
                print(f"  [{issue.severity.upper()}] {issue.code}: {issue.summary}")
        else:
            print("  No diagnostic issues.")
        print()

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print("Root cause analysis:")
        print("  retrieve stage: retrieval-precision dropped 0.82 -> 0.55 (delta -0.27)")
        print("  This is the root stage. All downstream metrics degraded as a result:")
        print("    rerank-ndcg:         0.81 -> 0.61")
        print("    generation-fluency:  0.88 -> 0.76")
        print("    answer-quality:      0.87 -> 0.64")
        print()
        print("Next action: audit the vector index for stale/OOD documents.")
        print("  Re-index with updated corpus, re-evaluate v2 pipeline.")

        v1_snap = ctx.get_run_snapshot(v1_ref)
        v2_snap = ctx.get_run_snapshot(v2_ref)
        v1_quality = next(
            (r.value for r in v1_snap.records if r.record_type == "metric" and r.key == "answer-quality"),
            None
        )
        v2_quality = next(
            (r.value for r in v2_snap.records if r.record_type == "metric" and r.key == "answer-quality"),
            None
        )

        return {
            "v1_run": v1_snap.run.name,
            "v2_run": v2_snap.run.name,
            "v1_answer_quality": v1_quality,
            "v2_answer_quality": v2_quality,
            "v2_diagnostic_issues": len(diag.issues),
            "root_stage": "retrieve",
        }
    finally:
        store.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Case Study 10: RAG Pipeline Stage Decomposition")
    parser.add_argument("--workspace", type=Path, default=None)
    args = parser.parse_args()
    run_example(args.workspace)


if __name__ == "__main__":
    main()
