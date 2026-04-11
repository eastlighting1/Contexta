"""Case Study 09: LLM Per-Prompt Evaluation - Mia's Story.

Mia is an AI Engineer at a company building a RAG-based customer support
chatbot. She is evaluating a new pipeline before promoting it to production.

THE SITUATION
=============
Mia runs an evaluation suite of 20 test prompts that cover different
question categories: account questions, billing disputes, product
inquiries, and escalation scenarios. For each prompt she scores:
  - relevance:     0.0-1.0, how relevant the retrieved context is
  - faithfulness:  0.0-1.0, how grounded the answer is in the context
  - answer_length: number of words in the generated answer

Most prompts score well, but a handful are clearly broken. Prompts 7,
12, and 17 return near-zero relevance scores -- they correspond to
escalation scenarios where the retriever completely fails to find
relevant documents.

The problem without observability: Mia sees an aggregate relevance of
0.79 and declares it "good enough". The aggregate masks the 3 broken
prompts. When those prompts hit production, the chatbot returns
off-topic answers to angry customers who want to escalate.

This demo shows how per-sample SampleObservation records surface the
failing prompts, letting Mia fix them before they reach production.
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
    SampleObservation,
    StageExecution,
    StructuredEventPayload,
    StructuredEventRecord,
)


PROJECT_NAME = "support-chatbot-rag-eval"
STAGE_NAME = "evaluate"
NUM_PROMPTS = 20
# Prompts that have bad relevance (1-based index matching sample names)
FAILING_PROMPT_INDICES = {7, 12, 17}

_REC_COUNTER = 0


def _next_rid() -> str:
    global _REC_COUNTER
    _REC_COUNTER += 1
    return f"r{_REC_COUNTER:05d}"


def _prompt_metrics(idx: int) -> tuple[float, float, int]:
    """Return (relevance, faithfulness, answer_length) for prompt index (1-based)."""
    if idx in FAILING_PROMPT_INDICES:
        # Escalation scenarios -- retriever completely misses
        relevance = round(0.05 + (idx % 3) * 0.07, 3)
        faithfulness = round(0.12 + (idx % 5) * 0.04, 3)
        answer_length = 18 + (idx % 4) * 3
    else:
        # Normal prompts
        relevance = round(0.78 + (idx % 7) * 0.02 + (idx % 3) * 0.01, 3)
        faithfulness = round(0.81 + (idx % 5) * 0.02, 3)
        answer_length = 45 + (idx % 8) * 5
    return relevance, faithfulness, answer_length


def _category(idx: int) -> str:
    categories = ["account", "billing", "product", "escalation"]
    return categories[(idx - 1) % 4]


def run_example(workspace: Path | str | None = None) -> dict[str, Any]:
    """Create 1 run with 20 per-prompt SampleObservations and find the failing ones."""

    if workspace is None:
        root = Path(tempfile.mkdtemp(prefix="contexta-case09-"))
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
    print("CASE STUDY 09: LLM Per-Prompt Evaluation")
    print("=" * 60)
    print()
    store = ctx.metadata_store
    try:
        store.projects.put_project(
            Project(
                project_ref=f"project:{PROJECT_NAME}",
                name=PROJECT_NAME,
                created_at="2025-04-10T00:00:00Z",
                description="RAG customer support chatbot evaluation suite",
            )
        )

        run_name = "eval-run-v1"
        run_ref = f"run:{PROJECT_NAME}.{run_name}"
        started_at = "2025-04-10T10:00:00Z"
        ended_at = "2025-04-10T10:30:00Z"

        store.runs.put_run(
            Run(
                run_ref=run_ref,
                project_ref=f"project:{PROJECT_NAME}",
                name=run_name,
                status="completed",
                started_at=started_at,
                ended_at=ended_at,
            )
        )

        stage_ref = f"stage:{PROJECT_NAME}.{run_name}.{STAGE_NAME}"
        store.stages.put_stage_execution(
            StageExecution(
                stage_execution_ref=stage_ref,
                run_ref=run_ref,
                stage_name=STAGE_NAME,
                status="completed",
                started_at=started_at,
                ended_at=ended_at,
                order_index=0,
            )
        )

        # Register a structured event describing the evaluation suite
        record_store = ctx.record_store
        record_store.append(
            StructuredEventRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                    record_type="event",
                    recorded_at=started_at,
                    observed_at=started_at,
                    producer_ref="contexta.case09",
                    run_ref=run_ref,
                    stage_execution_ref=stage_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=StructuredEventPayload(
                    event_key="eval.suite-registered",
                    level="info",
                    message=f"Evaluation suite: {NUM_PROMPTS} prompts across 4 categories.",
                    attributes={"prompt_count": NUM_PROMPTS, "categories": "account,billing,product,escalation"},
                    origin_marker="explicit_capture",
                ),
            )
        )

        # Create 20 SampleObservations (one per prompt) with metric records
        for idx in range(1, NUM_PROMPTS + 1):
            sample_name = f"prompt-{idx:02d}"
            # sample_observation_ref must equal stage_execution_ref + "." + sample_name
            sample_ref = f"sample:{PROJECT_NAME}.{run_name}.{STAGE_NAME}.{sample_name}"
            obs_ts = f"2025-04-10T10:{idx:02d}:00Z"

            store.samples.put_sample_observation(
                SampleObservation(
                    sample_observation_ref=sample_ref,
                    run_ref=run_ref,
                    stage_execution_ref=stage_ref,
                    sample_name=sample_name,
                    observed_at=obs_ts,
                )
            )

            relevance, faithfulness, answer_length = _prompt_metrics(idx)
            for metric_key, metric_val in [
                ("relevance", relevance),
                ("faithfulness", faithfulness),
                ("answer-length", float(answer_length)),
            ]:
                record_store.append(
                    MetricRecord(
                        envelope=RecordEnvelope(
                            record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                            record_type="metric",
                            recorded_at=obs_ts,
                            observed_at=obs_ts,
                            producer_ref="contexta.case09",
                            run_ref=run_ref,
                            stage_execution_ref=stage_ref,
                            sample_observation_ref=sample_ref,
                            completeness_marker="complete",
                            degradation_marker="none",
                        ),
                        payload=MetricPayload(
                            metric_key=metric_key,
                            value=metric_val,
                            value_type="float64",
                        ),
                    )
                )

        # ------------------------------------------------------------------
        # Use get_run_snapshot to find failing prompts
        # ------------------------------------------------------------------
        snap = ctx.get_run_snapshot(run_ref)
        metric_recs = [r for r in snap.records if r.record_type == "metric"]

        # Group metrics by sample_id
        sample_data: dict[str, dict[str, float]] = {}
        for rec in metric_recs:
            sid = rec.stage_id  # stage_id field on ObservationRecord
            if sid is None:
                continue
            if sid not in sample_data:
                sample_data[sid] = {}
            sample_data[sid][rec.key] = rec.value

        print(f"  {'Prompt':<14} {'Category':<12} {'Relevance':<12} {'Faithfulness':<14} {'Length':<8} {'Status'}")
        print("  " + "-" * 72)

        pass_count = 0
        fail_count = 0
        relevance_sum = 0.0
        faithfulness_sum = 0.0
        failing_prompts: list[str] = []

        for idx in range(1, NUM_PROMPTS + 1):
            sample_name = f"prompt-{idx:02d}"
            relevance, faithfulness, answer_length = _prompt_metrics(idx)
            cat = _category(idx)
            status = "FAIL" if relevance < 0.3 else "pass"
            if relevance < 0.3:
                fail_count += 1
                failing_prompts.append(sample_name)
            else:
                pass_count += 1
            relevance_sum += relevance
            faithfulness_sum += faithfulness
            flag = " <--" if relevance < 0.3 else ""
            print(
                f"  {sample_name:<14} {cat:<12} {relevance:<12.3f} "
                f"{faithfulness:<14.3f} {answer_length:<8} {status}{flag}"
            )

        print()
        print("Aggregate summary:")
        print(f"  Total prompts:       {NUM_PROMPTS}")
        print(f"  Passing (>= 0.3):    {pass_count}")
        print(f"  Failing (< 0.3):     {fail_count}  -- {', '.join(failing_prompts)}")
        print(f"  Avg relevance:       {relevance_sum / NUM_PROMPTS:.3f}")
        print(f"  Avg faithfulness:    {faithfulness_sum / NUM_PROMPTS:.3f}")
        print()
        print("Key insight:")
        print("  Aggregate relevance 0.79 -- would pass a naive quality gate.")
        print(f"  Per-sample view reveals {fail_count} broken escalation prompts (relevance < 0.30).")
        print("  Root cause: retriever has no indexed documents for escalation intent.")
        print("  Fix: add escalation FAQ documents to the vector store before promotion.")

        return {
            "run_name": run_name,
            "total_prompts": NUM_PROMPTS,
            "passing_prompts": pass_count,
            "failing_prompts": fail_count,
            "failing_prompt_names": failing_prompts,
            "avg_relevance": round(relevance_sum / NUM_PROMPTS, 4),
            "avg_faithfulness": round(faithfulness_sum / NUM_PROMPTS, 4),
        }
    finally:
        store.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Case Study 09: LLM Per-Prompt Evaluation")
    parser.add_argument("--workspace", type=Path, default=None)
    args = parser.parse_args()
    run_example(args.workspace)


if __name__ == "__main__":
    main()
