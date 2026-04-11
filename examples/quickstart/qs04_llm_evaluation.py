"""Quickstart 04: LLM/RAG Pipeline Per-Prompt Evaluation.

Purpose:
    Shows SampleObservation for per-prompt quality tracking in a RAG
    pipeline evaluated with vLLM offline inference (or OpenAI as alternative).
    Relevance, faithfulness, and answer-length are logged per prompt.

Note:
    Requires vLLM on Linux/WSL with a compatible GPU.
    For the OpenAI API alternative, see comments near `generate_answer` below.
    The retrieval logic is keyword-overlap (simple) -- the point is the
    Contexta instrumentation, not retrieval quality.

Contexta features demonstrated:
    - SampleObservation (per-prompt)
    - MetricRecord per sample (relevance, faithfulness, answer-length)
    - MetricRecord aggregate (mean-relevance, mean-faithfulness, mean-latency-ms)
    - StructuredEventRecord for pipeline registration
    - EnvironmentSnapshot
    - get_run_snapshot (per-prompt table + failing prompt detection)
    - diagnose_run
    - build_snapshot_report

Dependencies:
    vllm, torch, numpy, contexta

Run:
    uv run python examples/quickstart/qs04_llm_evaluation.py
"""

from __future__ import annotations

import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

# ---------------------------------------------------------------------------
# LLM backend -- vLLM (default)
# ---------------------------------------------------------------------------
from vllm import LLM, SamplingParams

import vllm

MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"  # replace with any model available on your system

llm = LLM(model=MODEL_ID, max_model_len=2048)
sampling_params = SamplingParams(temperature=0.1, max_tokens=256, stop=["\n\n"])


def generate_answer(prompt: str) -> str:
    outputs = llm.generate([prompt], sampling_params)
    return outputs[0].outputs[0].text.strip()


# ---------------------------------------------------------------------------
# Alternative: OpenAI API
# Uncomment the block below and comment out the vLLM block above.
# ---------------------------------------------------------------------------
# from openai import OpenAI
# _client = OpenAI()  # reads OPENAI_API_KEY from env
#
# def generate_answer(prompt: str) -> str:
#     resp = _client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[{"role": "user", "content": prompt}],
#         max_tokens=256,
#     )
#     return resp.choices[0].message.content.strip()

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    EnvironmentSnapshot,
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

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_NAME = "rag-eval"
WORKSPACE = Path(__file__).parent / ".contexta" / PROJECT_NAME

_rid = 0


def _next_rid() -> str:
    global _rid
    _rid += 1
    return f"r{_rid:05d}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Knowledge base (8 paragraphs, one per category)
# ---------------------------------------------------------------------------
KNOWLEDGE_BASE = [
    "Python is a high-level interpreted programming language. It uses dynamic typing and "
    "supports multiple programming paradigms including procedural, object-oriented, and "
    "functional programming. Python is widely used in data science and web development.",

    "Machine learning is a subfield of artificial intelligence that enables systems to learn "
    "from data without being explicitly programmed. Common algorithms include decision trees, "
    "support vector machines, and gradient boosting methods for classification and regression.",

    "Neural networks are computational models inspired by the human brain. They consist of "
    "layers of interconnected nodes called neurons. Deep learning uses many hidden layers to "
    "learn hierarchical representations from raw data such as images and text.",

    "Natural language processing enables computers to understand and generate human language. "
    "Techniques include tokenization, named entity recognition, sentiment analysis, and "
    "transformer-based models such as BERT and GPT for downstream NLP tasks.",

    "Databases store and manage structured data. Relational databases use SQL for querying "
    "tables with defined schemas. NoSQL databases like MongoDB and Redis handle unstructured "
    "or high-throughput workloads with flexible document or key-value storage models.",

    "Cloud computing delivers computing resources over the internet on demand. Major providers "
    "include AWS, Azure, and Google Cloud. Services are categorized as infrastructure, platform, "
    "or software as a service, enabling scalable deployment without owning physical hardware.",

    "Security in software systems involves protecting data and infrastructure from unauthorized "
    "access. Key practices include encryption, authentication, authorization, and vulnerability "
    "scanning. Zero-trust architecture treats every request as potentially hostile by default.",

    "DevOps combines software development and IT operations to shorten the development lifecycle. "
    "Core practices include continuous integration, continuous delivery, containerization with "
    "Docker, and orchestration with Kubernetes for automated deployment and scaling.",
]

CATEGORIES = ["python", "machine-learning", "neural-networks", "nlp",
               "databases", "cloud", "security", "devops"]

# 24 test prompts (3 per category)
TEST_PROMPTS = [
    "What programming paradigms does Python support?",
    "Is Python dynamically or statically typed?",
    "What are common use cases for Python programming?",
    "What is machine learning and how does it differ from explicit programming?",
    "Name some common machine learning algorithms for classification.",
    "What is gradient boosting used for in machine learning?",
    "How are neural networks inspired by the human brain?",
    "What is deep learning and what makes it different from shallow networks?",
    "What types of data can deep learning process effectively?",
    "What techniques are used in natural language processing?",
    "What is the role of transformer models in NLP tasks?",
    "What does tokenization do in natural language processing?",
    "What is the difference between SQL and NoSQL databases?",
    "What is MongoDB and what kind of data does it store?",
    "How do relational databases organize and query data?",
    "What are the major cloud computing service providers?",
    "What does infrastructure as a service mean in cloud computing?",
    "Why do companies use cloud computing instead of physical hardware?",
    "What is zero-trust architecture in software security?",
    "What are key practices for securing software systems?",
    "How does encryption protect data in software systems?",
    "What is the goal of DevOps in software development?",
    "How do Docker and Kubernetes relate to DevOps practices?",
    "What does continuous integration mean in a DevOps context?",
]

GROUND_TRUTHS = [
    "Python supports procedural, object-oriented, and functional programming paradigms.",
    "Python uses dynamic typing.",
    "Python is used in data science and web development.",
    "Machine learning enables systems to learn from data without explicit programming.",
    "Decision trees, support vector machines, and gradient boosting are common algorithms.",
    "Gradient boosting is used for classification and regression tasks.",
    "Neural networks are inspired by the human brain using interconnected nodes called neurons.",
    "Deep learning uses many hidden layers to learn hierarchical representations.",
    "Deep learning can process images, text, and other raw data.",
    "NLP uses tokenization, named entity recognition, sentiment analysis, and transformers.",
    "Transformer models like BERT and GPT are used for downstream NLP tasks.",
    "Tokenization splits text into smaller units for processing.",
    "Relational databases use SQL; NoSQL handles unstructured or high-throughput workloads.",
    "MongoDB is a NoSQL database that stores flexible document-based data.",
    "Relational databases use SQL to query tables with defined schemas.",
    "AWS, Azure, and Google Cloud are major cloud computing providers.",
    "Infrastructure as a service provides computing resources without owning hardware.",
    "Cloud computing enables scalable deployment without owning physical hardware.",
    "Zero-trust architecture treats every request as potentially hostile by default.",
    "Key security practices include encryption, authentication, authorization, and scanning.",
    "Encryption protects data from unauthorized access.",
    "DevOps combines development and operations to shorten the development lifecycle.",
    "Docker provides containerization and Kubernetes handles orchestration and scaling.",
    "Continuous integration automates building and testing code changes frequently.",
]

PROMPT_CATEGORIES = [cat for cat in CATEGORIES for _ in range(3)]


# ---------------------------------------------------------------------------
# Retrieval and scoring helpers
# ---------------------------------------------------------------------------
def retrieve(question: str, kb: list[str], top_k: int = 2) -> list[str]:
    """Keyword-overlap retrieval."""
    q_tokens = set(question.lower().split())
    scores = [len(q_tokens & set(doc.lower().split())) for doc in kb]
    ranked = sorted(range(len(kb)), key=lambda i: scores[i], reverse=True)
    return [kb[i] for i in ranked[:top_k]]


def token_overlap(a: str, b: str) -> float:
    ta, tb = set(a.lower().split()), set(b.lower().split())
    return len(ta & tb) / len(tb) if tb else 0.0


def score_response(generated: str, ground_truth: str, context: list[str]) -> dict[str, float]:
    return {
        "relevance": token_overlap(generated, ground_truth),
        "faithfulness": token_overlap(generated, " ".join(context)),
        "answer-length": float(len(generated.split())),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 60)
    print("QS04: LLM/RAG Pipeline Per-Prompt Evaluation")
    print("=" * 60)

    ctx = Contexta(
        config=UnifiedConfig(
            project_name=PROJECT_NAME,
            workspace=WorkspaceConfig(root_path=WORKSPACE),
        )
    )
    store = ctx.metadata_store

    run_name = "rag-eval-v1"
    run_ref = f"run:{PROJECT_NAME}.{run_name}"
    project_ref = f"project:{PROJECT_NAME}"
    stage_ret_ref = f"stage:{PROJECT_NAME}.{run_name}.retrieve"
    stage_gen_ref = f"stage:{PROJECT_NAME}.{run_name}.generate"
    stage_eval_ref = f"stage:{PROJECT_NAME}.{run_name}.evaluate"
    env_ref = f"environment:{PROJECT_NAME}.{run_name}.env-snapshot"

    store.projects.put_project(
        Project(project_ref=project_ref, name=PROJECT_NAME, created_at=_now())
    )
    run_start = _now()
    store.runs.put_run(
        Run(
            run_ref=run_ref,
            project_ref=project_ref,
            name=run_name,
            status="open",
            started_at=run_start,
            ended_at=None,
        )
    )

    # ---- Stage: retrieve ----
    ret_start = _now()
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=stage_ret_ref,
            run_ref=run_ref,
            stage_name="retrieve",
            status="completed",
            started_at=ret_start,
            ended_at=ret_start,
            order_index=0,
        )
    )

    ctx.record_store.append(
        StructuredEventRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                record_type="event",
                recorded_at=ret_start,
                observed_at=ret_start,
                producer_ref="contexta.qs04",
                run_ref=run_ref,
                stage_execution_ref=stage_ret_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=StructuredEventPayload(
                event_key="pipeline.registered",
                level="info",
                message="RAG evaluation pipeline -- 24 prompts, 8 categories, keyword-overlap retrieval",
                attributes={"n_prompts": "24", "n_categories": "8", "retriever": "keyword-overlap"},
                origin_marker="explicit_capture",
            ),
        )
    )

    print("\nRetrieving context for all 24 prompts ...")
    contexts: list[list[str]] = []
    retrieval_overlaps: list[float] = []
    for prompt in TEST_PROMPTS:
        docs = retrieve(prompt, KNOWLEDGE_BASE, top_k=2)
        contexts.append(docs)
        retrieval_overlaps.append(token_overlap(prompt, " ".join(docs)))

    mean_retrieval = float(np.mean(retrieval_overlaps))
    ret_end = _now()
    ctx.record_store.append(
        MetricRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                record_type="metric",
                recorded_at=ret_end,
                observed_at=ret_end,
                producer_ref="contexta.qs04",
                run_ref=run_ref,
                stage_execution_ref=stage_ret_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=MetricPayload(metric_key="mean-retrieval-overlap", value=mean_retrieval, value_type="float64"),
        )
    )
    print(f"  Mean retrieval overlap: {mean_retrieval:.4f}")

    # ---- Stage: generate ----
    gen_start = _now()
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=stage_gen_ref,
            run_ref=run_ref,
            stage_name="generate",
            status="completed",
            started_at=gen_start,
            ended_at=gen_start,
            order_index=1,
        )
    )

    print("\nGenerating answers for all 24 prompts ...")
    generated_answers: list[str] = []
    latencies_ms: list[float] = []
    for i, (prompt, docs) in enumerate(zip(TEST_PROMPTS, contexts)):
        augmented = "Context:\n" + "\n".join(docs) + "\n\nQuestion: " + prompt + "\nAnswer:"
        t0 = time.perf_counter()
        answer = generate_answer(augmented)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        generated_answers.append(answer)
        latencies_ms.append(latency_ms)
        print(f"  Prompt {i+1:02d}/{len(TEST_PROMPTS)} latency={latency_ms:.1f}ms")

    mean_latency = float(np.mean(latencies_ms))
    gen_end = _now()
    ctx.record_store.append(
        MetricRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                record_type="metric",
                recorded_at=gen_end,
                observed_at=gen_end,
                producer_ref="contexta.qs04",
                run_ref=run_ref,
                stage_execution_ref=stage_gen_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=MetricPayload(metric_key="mean-latency-ms", value=mean_latency, value_type="float64"),
        )
    )
    print(f"  Mean generation latency: {mean_latency:.1f}ms")

    # ---- Stage: evaluate (per-prompt) ----
    eval_start = _now()
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=stage_eval_ref,
            run_ref=run_ref,
            stage_name="evaluate",
            status="completed",
            started_at=eval_start,
            ended_at=eval_start,
            order_index=2,
        )
    )

    print("\nEvaluating per-prompt quality ...")
    all_scores: list[dict[str, float]] = []
    for i, (answer, ground_truth, docs) in enumerate(zip(generated_answers, GROUND_TRUTHS, contexts)):
        sample_name = f"prompt-{i+1:02d}"
        sample_ref = f"sample:{PROJECT_NAME}.{run_name}.evaluate.{sample_name}"
        ts = _now()

        store.samples.put_sample_observation(
            SampleObservation(
                sample_observation_ref=sample_ref,
                run_ref=run_ref,
                stage_execution_ref=stage_eval_ref,
                sample_name=sample_name,
                observed_at=ts,
            )
        )

        scores = score_response(answer, ground_truth, docs)
        all_scores.append(scores)

        for mkey, mval in scores.items():
            ctx.record_store.append(
                MetricRecord(
                    envelope=RecordEnvelope(
                        record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                        record_type="metric",
                        recorded_at=ts,
                        observed_at=ts,
                        producer_ref="contexta.qs04",
                        run_ref=run_ref,
                        stage_execution_ref=stage_eval_ref,
                        sample_observation_ref=sample_ref,
                        completeness_marker="complete",
                        degradation_marker="none",
                    ),
                    payload=MetricPayload(metric_key=mkey, value=float(mval), value_type="float64"),
                )
            )

    # Aggregate stage-level metrics
    mean_relevance = float(np.mean([s["relevance"] for s in all_scores]))
    mean_faithfulness = float(np.mean([s["faithfulness"] for s in all_scores]))
    eval_end = _now()
    store.runs.put_run(
        Run(
            run_ref=run_ref,
            project_ref=project_ref,
            name=run_name,
            status="completed",
            started_at=run_start,
            ended_at=eval_end,
        )
    )
    for mkey, mval in [("mean-relevance", mean_relevance), ("mean-faithfulness", mean_faithfulness)]:
        ctx.record_store.append(
            MetricRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                    record_type="metric",
                    recorded_at=eval_end,
                    observed_at=eval_end,
                    producer_ref="contexta.qs04",
                    run_ref=run_ref,
                    stage_execution_ref=stage_eval_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=MetricPayload(metric_key=mkey, value=mval, value_type="float64"),
            )
        )

    # ---- Environment ----
    python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    store.environments.put_environment_snapshot(
        EnvironmentSnapshot(
            environment_snapshot_ref=env_ref,
            run_ref=run_ref,
            captured_at=eval_end,
            python_version=python_ver,
            platform=platform.system().lower(),
            packages={"vllm": vllm.__version__, "torch": torch.__version__},
        )
    )

    # ---- Results table ----
    print(f"\n{'Prompt':<14} {'Category':<18} {'Relevance':<12} {'Faithfulness':<14} {'Ans-Len':<10} Status")
    print("-" * 75)
    failing: list[str] = []
    for i, scores in enumerate(all_scores):
        sample_name = f"prompt-{i+1:02d}"
        rel, faith = scores["relevance"], scores["faithfulness"]
        alen = int(scores["answer-length"])
        status = "FAIL" if rel < 0.3 else "pass"
        if rel < 0.3:
            failing.append(sample_name)
        print(f"{sample_name:<14} {PROMPT_CATEGORIES[i]:<18} {rel:<12.3f} {faith:<14.3f} {alen:<10} {status}")

    print(f"\nAggregate mean-relevance:    {mean_relevance:.4f}")
    print(f"Aggregate mean-faithfulness: {mean_faithfulness:.4f}")
    if failing:
        print(f"Failing prompts (rel < 0.3): {', '.join(failing)}")
    else:
        print("No failing prompts (all relevance >= 0.3)")

    # ---- Analysis ----
    print("\n--- Analysis ---")

    diag = ctx.diagnose_run(run_ref)
    if diag.issues:
        print("\nDiagnostics issues:")
        for issue in diag.issues:
            print(f"  [{issue.severity}] {issue.code}: {issue.summary}")
    else:
        print("\nDiagnostics: no issues found.")

    report = ctx.build_snapshot_report(run_ref)
    print(f"\nSnapshot report: {report.title}")
    for sec in report.sections:
        print(f"  - {sec.title}")

    store.close()


if __name__ == "__main__":
    main()
