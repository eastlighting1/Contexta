# Case Studies

Twelve real-world scenarios showing how Contexta replaces manual processes — spreadsheet
archaeology, Slack checklists, estimated audit answers — with a small number of API calls.

Each scenario has a runnable example under `examples/case_studies/`.

---

## Why Contexta?

### The gap that motivated it

ML teams already have experiment trackers (MLflow, W&B), orchestrators (Airflow, Prefect),
and monitoring platforms (Grafana, Datadog). So why another tool?

Because none of those tools answer the question you have at 9 AM on Monday morning:

> "The CTR dropped 18% overnight. Which training run was deployed? What dataset did it use?
> Can I safely roll back, and to what?"

Experiment trackers record metrics — but they don't link a production deployment back to the
exact run, stage, and dataset. Orchestrators know whether a job succeeded or failed — but they
don't record *why* the output was subtly wrong when the exit code was 0. Monitoring platforms
alert on thresholds — but they can't tell you which training run caused the drift.

Contexta fills the gap between those systems. Its job is to record the evidence that connects
your training history, your runtime behaviour, and your production deployments into a single
queryable graph — so that questions you couldn't answer before take three API calls instead of
two days.

### What Contexta does differently

| Concern | Typical approach | Contexta |
|---------|-----------------|---------|
| Experiment comparison | Manual spreadsheet or MLflow UI | `compare_runs`, `select_best_run`, `build_multi_run_report` |
| Deployment traceability | Filename convention or release notes | `DeploymentExecution` links run → deployment; `traverse_lineage` |
| Silent failures | Dashboard threshold alerts | `DegradedRecord` + `diagnose_run` — surfaced even when exit code is 0 |
| Environment reproducibility | `requirements.txt` (often stale) | `EnvironmentSnapshot` recorded at run time; `audit_reproducibility` |
| Compliance evidence | 2-day manual search | `get_run_snapshot`, `build_snapshot_report` — seconds |
| Deployment gate | Slack checklist | Programmatic gate: diagnostics + required metrics + regression check |
| Per-sample evaluation | Aggregate metrics only | `SampleObservation` + per-sample `MetricRecord` |
| Stage-level decomposition | End-to-end metric only | Stage-scoped `MetricRecord` per pipeline stage |

### Design principles

- **Zero additional infrastructure.** Contexta stores everything locally alongside your
  code. No hosted backend, no separate service to operate.
- **Additive, not prescriptive.** You attach records to runs and stages you already create.
  You do not restructure your training code around Contexta's abstractions.
- **Evidence over summaries.** Every number in a report can be traced back to a specific
  `RecordEnvelope` with a timestamp, producer, and run reference.
- **Programmatic first.** Reports, comparisons, and gates are Python objects — scriptable,
  testable, and CI-friendly. No GUI required.

---

## Group 1 — Experiment Tracking

### Case 01: Sara's Scattered HPO Experiments

**Persona:** Sara, ML Engineer  
**Example:** `examples/case_studies/case01_scattered_experiments.py`

#### Situation

Sara runs 8 hyperparameter search experiments over a weekend. Each produces a CSV or JSON
file with a name like `lr0001_bs32_aug_20250318_v3_FINAL.csv`. On Monday, her tech lead
asks: "Which experiment was best?" Sara cannot answer without 20 minutes of
spreadsheet archaeology — opening each file, extracting the accuracy number, and manually
ranking them.

#### Without Contexta

```
lr0001_bs32_aug_20250318_v3_FINAL.csv
results_bs64_lr001_with_augmentation.xlsx
experiment_march18_attempt2.txt
BEST_run_maybe_lr0005_bs64.csv
...
```

- Results live in files named by the engineer, not the framework.
- No common schema → comparing across files requires custom parsing.
- No ranking API → the "best" run is wherever the engineer left a sticky note.
- Two weeks later, the CSV files may be gone from the laptop.

#### With Contexta

```python
# All 8 runs indexed at creation time.
best_ref = ctx.select_best_run(run_refs, "accuracy", stage_name="train")
report   = ctx.build_multi_run_report(run_refs)
```

Every run is registered with its metrics at the moment it completes. `select_best_run`
answers the sprint-review question in one call. `build_multi_run_report` produces a
structured comparison with no manual work.

**Key APIs:** `select_best_run`, `build_multi_run_report`, `compare_runs`

---

### Case 02: James's Silent Performance Regression

**Persona:** James, ML Engineer  
**Example:** `examples/case_studies/case02_performance_regression.py`

#### Situation

James upgrades a library and retrains. Accuracy drops from 0.91 to 0.87. He suspects a
dependency change but cannot confirm it — the environment from the previous training was
never recorded. His `requirements.txt` was committed three weeks ago and may not reflect
what was actually installed.

#### Without Contexta

- `requirements.txt` is a snapshot in time, not a training-time record.
- Diffing two `requirements.txt` files requires knowing which commit to compare against.
- If the file wasn't committed, the old environment is gone.
- Guessing which package caused the regression means iterative manual testing.

#### With Contexta

```python
env_diff = ctx.compare_environments(old_run_ref, new_run_ref)
# env_diff.python_version_changed → True
# env_diff.changed_packages → [torch: 2.0.0 → 2.1.0, numpy: 1.24.0 → 1.26.0]

audit = ctx.audit_reproducibility(old_run_ref)
# audit.python_version, audit.package_count, audit.reproducibility_status
```

`EnvironmentSnapshot` is recorded at run creation time — not as a file, but as a
structured record linked to the run. `compare_environments` produces an exact diff of
packages and Python version between any two runs.

**Key APIs:** `EnvironmentSnapshot`, `compare_environments`, `audit_reproducibility`

---

## Group 2 — Production Monitoring

### Case 03: Nina's Silent Pipeline Failure

**Persona:** Nina, MLE / Data Engineer  
**Example:** `examples/case_studies/case03_silent_pipeline_failure.py`

#### Situation

A 5-stage nightly pipeline (ingest → validate → featurize → train → evaluate) runs for 3
days with `status=completed` on every stage. On Day 1, a schema migration caused the
`validate` stage to pass an empty DataFrame downstream instead of raising an exception.
The train stage trained on zero rows and returned default weights. The evaluate stage
reported terrible metrics — but no alert fired. By Day 3, three days of bad checkpoints
were queued for production.

#### Without Contexta

- Exit code 0 + `status=completed` is the only signal available to the orchestrator.
- The orchestrator cannot distinguish "completed correctly" from "completed on empty input".
- Dashboard alerts require threshold configuration that nobody got around to.
- Debugging three days later means reconstructing what happened from logs that may have
  rotated.

#### With Contexta

```python
# validate stage emits a DegradedRecord when it detects empty output
DegradedRecord(
    envelope=RecordEnvelope(..., degradation_marker="partial_failure"),
    payload=DegradedPayload(
        category="verification", severity="error",
        summary="output-dataframe-empty-after-join",
    )
)

# Day 1 — immediately visible
diag = ctx.diagnose_run(run_ref)
errors = [i for i in diag.issues if i.severity == "error"]
# → 1 error: degraded_record in validate stage
```

`DegradedRecord` is a first-class record type that survives even when the stage exits 0.
`diagnose_run` surfaces it on Day 1 before any checkpoint is promoted.

**Key APIs:** `DegradedRecord`, `diagnose_run`

---

### Case 04: Carlos's Deployment Traceability Problem

**Persona:** Carlos, ML Engineer  
**Example:** `examples/case_studies/case04_deployment_traceability.py`

#### Situation

Carlos deploys a model on Friday afternoon. Monday morning, the product manager reports
an 18% CTR drop overnight. Carlos's deployment notes say `model_20250401.pkl`. He cannot
answer four questions:

1. Which training run produced that checkpoint?
2. What were the training metrics?
3. Which dataset version was used?
4. What would rolling back revert to?

#### Without Contexta

- A filename is not a run reference. It does not link to metrics, dataset, or environment.
- "Roll back" means swapping in a different `.pkl` file and hoping it was the previous one.
- Answering the product manager takes 30 minutes of git log archaeology, Slack search,
  and notebook hunting.

#### With Contexta

```python
# Step 1 — find all deployments and their linked runs
deployments = ctx.list_deployments(PROJECT_NAME)

# Step 2 — inspect the deployed run
snap = ctx.get_run_snapshot(run_c_ref)
# snap.run.name, snap.stages, snap.records (metrics + dataset event)

# Step 3 — traverse lineage from the deployment
lineage = ctx.traverse_lineage(friday_deploy_ref)

# Step 4 — compare deployed run vs safe baseline
comparison = ctx.compare_runs(run_c_ref, run_b_ref)
```

`DeploymentExecution` permanently links a deployment to the exact run that was deployed.
Three API calls replace 30 minutes of archaeology.

**Key APIs:** `DeploymentExecution`, `list_deployments`, `get_run_snapshot`, `traverse_lineage`, `compare_runs`

---

## Group 3 — MLOps and Deployment

### Case 05: Automated Deployment Gate

**Persona:** MLOps Engineer / Forward Deployed Engineer  
**Example:** `examples/case_studies/case05_deployment_gate.py`

#### Situation

The team deploys models via a Slack checklist: "Did you check metrics? Did you compare with
the previous version? Did you validate the data?" Three failures in the past quarter:

- **March:** deployed with evaluation metrics from the wrong stage
- **April:** deployed run-c with dataset v2025-03-31 (caused the CTR drop — Case 04)
- **May:** `evaluate` stage was skipped entirely; no metrics in the run

#### Without Contexta

A Slack checklist relies on humans remembering to check the right things. The March failure
passed because nobody verified *which* stage the metrics came from. The May failure passed
because the checkbox said "metrics ✓" — nobody noticed the evaluate stage had been skipped.
Manual processes have no memory of past failure modes.

#### With Contexta

```python
def pre_deployment_gate(ctx, candidate_run_id, previous_deploy_run_id):
    # Check 1: no error-level diagnostics
    diag   = ctx.diagnose_run(candidate_run_id)
    errors = [i for i in diag.issues if i.severity == "error"]

    # Check 2: all required metrics present
    snap   = ctx.get_run_snapshot(candidate_run_id)
    obs_keys = {o.key for o in snap.records if o.record_type == "metric"}
    missing  = [m for m in REQUIRED_METRICS if m not in obs_keys]

    # Check 3: no regression vs previous deployment
    comp = ctx.compare_runs(previous_deploy_run_id, candidate_run_id)
    ...
```

| Scenario | Manual gate | Programmatic gate |
|----------|-------------|-------------------|
| Wrong-stage metrics | PASS (human missed it) | FAIL (metrics absent from evaluate stage) |
| Dataset version mismatch | PASS (nobody checked) | FAIL (DegradedRecord present) |
| Evaluate stage skipped | PASS (checkbox ticked) | FAIL (required metrics missing) |

**Key APIs:** `diagnose_run`, `get_run_snapshot`, `compare_runs`

---

### Case 06: Elena's Compliance Audit Trail

**Persona:** Solutions Architect / Compliance  
**Example:** `examples/case_studies/case06_compliance_audit.py`

#### Situation

Elena's team delivers AI solutions to a regulated insurance client. The client's regulator
audits the production model and asks five questions:

1. What dataset version was used to train the production model?
2. What were the training-time evaluation metrics (original numbers, not summaries)?
3. What was the Python and library environment at training time?
4. How does this model compare to the previous version?
5. Who approved the deployment?

The team spent two days searching Git logs, personal Jupyter notebooks, Slack threads, and
a shared drive. Some information was estimated. The auditor rejected it: *"provide documented
evidence."*

#### Without Contexta

- Dataset version: written in a notebook cell or a Slack message. Neither is auditable.
- Eval metrics: in a script's stdout, possibly scrolled off or the terminal was closed.
- Environment: `requirements.txt` "might be stale."
- Model comparison: "we think it improved" — no structured diff.
- Answers take 2 days and some are estimates. Regulators reject estimates.

#### With Contexta

```python
# Q1: Dataset version
snapshot      = ctx.get_run_snapshot(curr_run_ref)
dataset_event = next(e for e in snapshot.records if e.key == "training.dataset-registered")

# Q2: Original evaluation metrics
eval_records = [o for o in snapshot.records if o.record_type == "metric"]

# Q3: Training environment
audit = ctx.audit_reproducibility(curr_run_ref)
# audit.python_version, audit.platform, audit.package_count

# Q4: Comparison with previous version
env_diff = ctx.compare_environments(prev_run_ref, curr_run_ref)
comp     = ctx.compare_runs(prev_run_ref, curr_run_ref)

# Q5: Formal audit document
report = ctx.build_snapshot_report(curr_run_ref)
```

All answers are backed by records written at training time — not reconstructed. The audit
package assembles in under 5 seconds.

**Key APIs:** `EnvironmentSnapshot`, `get_run_snapshot`, `audit_reproducibility`, `compare_environments`, `compare_runs`, `build_snapshot_report`

---

## Group 4 — Data Engineering

### Case 07: David's Silent Batch Job Failure

**Persona:** David, Data Engineer  
**Example:** `examples/case_studies/case07_batch_job_monitoring.py`

#### Situation

A nightly ETL job feature-engineers data for the ML model. On Night 5 of 7, the job
completed with exit code 0, but silently truncated a feature column because an upstream
vendor changed their API response schema. The vendor's new schema dropped a field that a
join relied on — the join succeeded but returned NULLs, and a numeric feature column was
quietly zeroed out. The downstream model retrained, accuracy dropped from 0.934 to 0.871,
and no alert fired because the batch job "succeeded."

#### Without Contexta

- Exit code 0 is the scheduler's only health signal.
- Batch job status `completed` does not distinguish "correct output" from "zero-filled column."
- Two days of debugging without knowing which night caused the accuracy drop.
- Logs may have rotated. Reproducing the exact failure requires re-running the pipeline.

#### With Contexta

```python
# Night 5 feature-engineering stage emits a DegradedRecord
DegradedRecord(
    payload=DegradedPayload(
        category="verification", severity="warning",
        summary="null-rate-exceeded-threshold",
        details={"column": "purchase_intent_score", "null_rate": 0.98},
    )
)

# Immediately visible
diag   = ctx.diagnose_run(night5_run_ref)
issues = [i for i in diag.issues if i.code == "degraded_record"]
# → 1 warning: null-rate-exceeded-threshold in feature-engineering stage
```

`BatchExecution` records link each night's job to its run, stage, and records. A weekly
summary table shows which night had the degradation — without re-running anything.

**Key APIs:** `BatchExecution`, `DegradedRecord`, `diagnose_run`

---

### Case 08: Upstream Data Contamination Window

**Persona:** MLE + Data Engineer pair  
**Example:** `examples/case_studies/case08_upstream_contamination.py`

#### Situation

A vendor changed their API response schema 3 weeks ago. The change silently clamped
`purchase_intent_score` from `[0.0, 1.0]` to `[0.0, 0.1]` — the field name stayed the
same, so schema validation did not catch it. Four training runs happened during the
contamination window (April 1–21). Each run "looked fine" in isolation — metrics were
slightly lower but the team attributed that to natural variance. Today a data engineer
noticed the clamping while debugging a separate issue.

#### Without Contexta

- No record of which runs overlapped with which data quality events.
- Identifying affected runs requires cross-referencing training dates against
  the contamination window — manually, across multiple systems.
- The "best" run during the window was promoted to production. There is no
  programmatic way to quarantine it.

#### With Contexta

```python
# Contaminated runs tagged at training time
StructuredEventRecord(payload=StructuredEventPayload(
    event_key="data.contamination-window",
    message="Training during vendor API contamination window Apr 1-21",
))

# Triage: identify, compare, select
contaminated_refs = [r for r in run_refs if was_in_window(r)]
comparison = ctx.compare_runs(clean_baseline_ref, latest_contaminated_ref)

# Which contaminated run "looked best" but shouldn't be trusted?
false_best = ctx.select_best_run(contaminated_refs, "auc", higher_is_better=True)
```

Event records tag the contamination window at training time. `compare_runs` shows how much
the contaminated runs diverged from the clean baseline. `select_best_run` identifies the
run that would have been promoted — and confirms it should be quarantined.

**Key APIs:** `StructuredEventRecord`, `compare_runs`, `select_best_run`

---

## Group 5 — AI and LLM Engineering

### Case 09: Mia's Per-Prompt Evaluation

**Persona:** Mia, AI Engineer  
**Example:** `examples/case_studies/case09_llm_per_prompt_evaluation.py`

#### Situation

Mia evaluates a RAG pipeline for a customer-support chatbot. She runs 20 test prompts
across four categories (account questions, billing disputes, product inquiries, escalation
scenarios) and scores each on relevance, faithfulness, and answer length. Prompts 7, 12,
and 17 are escalation scenarios where the retriever completely fails to find relevant
documents — they return near-zero relevance scores.

The problem: the aggregate relevance is 0.79. That passes the quality gate. The 3 broken
prompts are invisible in the aggregate. When those prompts reach production, the chatbot
returns off-topic answers to customers trying to escalate.

#### Without Contexta

- Aggregate metrics are the only available signal: `mean_relevance = 0.79`.
- Detecting which specific prompts are broken requires writing custom analysis code
  against the raw eval output, which is usually a JSON file or a dataframe.
- As the eval suite grows, the custom analysis code grows with it — and rarely gets
  maintained.

#### With Contexta

```python
# Each prompt is a SampleObservation; metrics are per-sample
for i, prompt in enumerate(PROMPTS):
    sample_ref = f"sample:{PROJECT}.run01.evaluate.prompt-{i+1:02d}"
    store.samples.put_sample_observation(SampleObservation(
        sample_observation_ref=sample_ref, ...
    ))
    record_store.append(MetricRecord(..., payload=MetricPayload(
        metric_key="relevance", value=scores[i]["relevance"]
    )))

# Analysis: find failing prompts
snapshot = ctx.get_run_snapshot(run_ref)
for rec in snapshot.records:
    if rec.record_type == "metric" and rec.key == "relevance" and rec.value < 0.3:
        print(f"FAIL: {rec.stage_id} / {rec.sample_id}")
```

Per-sample `MetricRecord` records mean the full distribution is queryable, not just the
aggregate. The three failing prompts are found by a simple filter — no custom analysis code.

**Key APIs:** `SampleObservation`, `MetricRecord` (per-sample), `get_run_snapshot`

---

### Case 10: RAG Pipeline Stage-Level Decomposition

**Persona:** AI Engineer  
**Example:** `examples/case_studies/case10_rag_pipeline_decomposition.py`

#### Situation

A 4-stage RAG pipeline (retrieve → rerank → generate → evaluate) is in production.
End-to-end `answer_quality` has dropped from 0.87 in the baseline to 0.64 in the latest
version. Nobody knows which stage caused it. The team has four hypotheses:

- The retrieve stage is returning lower-precision documents.
- The rerank model has degraded on new query types.
- The generation model has drifted.
- It is measurement noise.

Without stage-level metrics, testing each hypothesis requires a separate investigation run.

#### Without Contexta

- End-to-end metric: `answer_quality = 0.64`. That is the only number available.
- Each hypothesis requires instrumenting a stage, re-running the pipeline,
  and checking whether the hypothesis-specific number changed.
- Four hypotheses = four investigation cycles = days of work.

#### With Contexta

```python
# Metrics logged per stage at training time
# retrieve stage: retrieval-precision
# rerank stage:   rerank-ndcg
# generate stage: generation-fluency
# evaluate stage: answer-quality

comparison = ctx.compare_runs(v1_ref, v2_ref)
for sc in comparison.stage_comparisons:
    for d in sc.metric_deltas:
        print(f"{sc.stage_name}/{d.metric_key}: {d.left_value:.3f} → {d.right_value:.3f}")

# Output:
# retrieve/retrieval-precision: 0.810 → 0.620   ← root cause
# rerank/rerank-ndcg:           0.870 → 0.790   ← cascade
# generate/generation-fluency:  0.880 → 0.760   ← cascade
# evaluate/answer-quality:      0.870 → 0.640   ← effect
```

Stage-scoped `MetricRecord` records make the root stage visible in one `compare_runs` call.
The cascading degradation pattern (retrieve → everything downstream) is immediately apparent.

**Key APIs:** Stage-scoped `MetricRecord`, `compare_runs`, `diagnose_run`

---

## Group 6 — Team and Delivery

### Case 11: Alex's Onboarding Summary

**Persona:** Alex, Team Lead  
**Example:** `examples/case_studies/case11_project_history_onboarding.py`

#### Situation

A new ML engineer, Jamie, joins the team. The churn model has been in production for
4 months: 6 training runs, 2 deployments, performance tracked across multiple retrains.
Jamie needs answers to five questions on day one:

1. How many training runs exist and what are their names?
2. How has accuracy evolved over time?
3. Which runs were deployed to production?
4. Which run is objectively the best?
5. What does a structured comparison across all runs look like?

Without tooling, Alex writes a document manually by searching Git logs, Confluence pages,
and old Slack threads — half a day of work that goes stale in two weeks.

#### Without Contexta

- Project history lives across Git, Confluence, Slack, and individual notebooks.
- A handwritten document is a snapshot — it does not update when a new run is created.
- "Which run is best?" requires opening each notebook, finding the final metric, and
  ranking them manually.

#### With Contexta

```python
all_runs    = ctx.list_runs(PROJECT_NAME)
deployments = ctx.list_deployments(PROJECT_NAME)
best_ref    = ctx.select_best_run(run_refs, "accuracy", higher_is_better=True)
report      = ctx.build_multi_run_report(run_refs)
```

The summary regenerates on demand. It reflects the current state of all registered runs —
no manual maintenance required. `build_multi_run_report` produces a structured, sectioned
report that can be rendered as HTML or exported as CSV.

**Key APIs:** `list_runs`, `list_deployments`, `select_best_run`, `build_multi_run_report`

---

### Case 12: Tom's Delivery Quality Certificate

**Persona:** Tom, Forward Deployed Engineer  
**Example:** `examples/case_studies/case12_delivery_quality_certificate.py`

#### Situation

Tom delivers a trained model to FinanceBank Corp, whose procurement team requires a formal
"Model Quality Certificate" before accepting any AI model. The certificate must document:

1. Training data version used
2. Evaluation metrics (exact numbers, not estimates)
3. Training environment (Python version, key packages)
4. Pass/fail result for each agreed quality threshold
5. Overall PASS or FAIL decision

Without tooling, Tom assembles the certificate manually from training logs,
`requirements.txt`, and notebook outputs — 3 to 4 hours of work per delivery, plus a
review cycle when numbers don't match. Delays delivery by 1 to 2 days per engagement.

#### Without Contexta

| Step | Manual process | Time |
|------|---------------|------|
| Metrics | Open training log, copy numbers into Word | 30 min |
| Environment | Check `requirements.txt` (may be stale), paste Python version | 20 min |
| Dataset version | Recall from memory or search Slack | 15 min |
| Threshold checks | Manual comparison in Word | 20 min |
| Client review cycle | "AUC number does not match" | +1 day |

#### With Contexta

```python
# All evidence recorded at training time
snapshot = ctx.get_run_snapshot(run_ref)
audit    = ctx.audit_reproducibility(run_ref)

# Threshold checks
THRESHOLDS = {"accuracy": 0.90, "auc": 0.93, "f1": 0.88, ...}
for metric, threshold in THRESHOLDS.items():
    value  = next(r.value for r in snapshot.records if r.key == metric)
    status = "PASS" if value >= threshold else "FAIL"
    print(f"  {metric:<12} {value:.4f}  (>= {threshold})  [{status}]")

# Formal document
report = ctx.build_snapshot_report(run_ref)
```

The certificate assembles in under 12 seconds. Every number is backed by a recorded
`MetricRecord` — not estimated from memory. Client review cycles shrink because the numbers
are reproducible.

**Key APIs:** `EnvironmentSnapshot`, `StructuredEventRecord`, `get_run_snapshot`, `audit_reproducibility`, `build_snapshot_report`

---

## Running the examples

Each script is self-contained and requires no external services:

```bash
uv run python examples/case_studies/case01_scattered_experiments.py
uv run python examples/case_studies/case06_compliance_audit.py
# ... etc.
```

To run all twelve at once:

```bash
for f in examples/case_studies/case*.py; do
    echo "=== $f ==="
    uv run python "$f"
    echo
done
```

## See also

- [Getting Started](./getting-started.md) — first run in 5 minutes
- [Core Concepts](./core-concepts.md) — Run, Stage, Record, Deployment model
- [Tools and Surfaces](./tools-and-surfaces.md) — which API to use and when
- [Adapters](./adapters.md) — OpenTelemetry and MLflow bridges
