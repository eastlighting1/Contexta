# Case Studies

Real-world scenarios that show how Contexta replaces manual processes — Slack checklists, grep-through-logs archaeology, and estimated audit answers — with programmatic observability.

Each script is self-contained and runs with `uv run python examples/case_studies/<script>.py`.

---

## Group 1: ML / Experiment Tracking

| # | Script | Persona | Problem |
|---|--------|---------|---------|
| 01 | `case01_scattered_experiments.py` | MLE (Priya) | 8 HPO runs in separate notebooks — no way to compare or find the best one |
| 02 | `case02_performance_regression.py` | MLE (James) | Model accuracy dropped after a library upgrade; root cause unclear |

**APIs shown:** `select_best_run`, `build_multi_run_report`, `compare_runs`, `compare_environments`, `audit_reproducibility`

---

## Group 2: Production Monitoring

| # | Script | Persona | Problem |
|---|--------|---------|---------|
| 03 | `case03_silent_pipeline_failure.py` | MLE / Data Engineer | Pipeline exits 0 for 3 days; silent DegradedRecords hidden in validate stage |
| 04 | `case04_deployment_traceability.py` | MLE (Carlos) | CTR drop on Monday; no link from deployed `.pkl` to training run, metrics, or dataset |

**APIs shown:** `diagnose_run`, `get_run_snapshot`, `traverse_lineage`, `compare_runs`, `list_deployments`

---

## Group 3: MLOps / Deployment

| # | Script | Persona | Problem |
|---|--------|---------|---------|
| 05 | `case05_deployment_gate.py` | MLOps Engineer | Slack checklist caught 0 of 3 historical deployment failures |
| 06 | `case06_compliance_audit.py` | Solutions Architect (Elena) | Regulator audit requires evidence; team spent 2 days estimating answers |

**APIs shown:** `diagnose_run`, `get_run_snapshot`, `compare_runs`, `audit_reproducibility`, `compare_environments`, `build_snapshot_report`

---

## Group 4: Data Engineering

| # | Script | Persona | Problem |
|---|--------|---------|---------|
| 07 | `case07_batch_job_monitoring.py` | Data Engineer (David) | Nightly ETL exits 0 but silently truncates a column; no alert fires |
| 08 | `case08_upstream_contamination.py` | MLE + Data Engineer | Vendor API schema change 3 weeks ago contaminated 4 training runs undetected |

**APIs shown:** `BatchExecution`, `DegradedRecord`, `diagnose_run`, `compare_runs`, `select_best_run`

---

## Group 5: AI / LLM Engineering

| # | Script | Persona | Problem |
|---|--------|---------|---------|
| 09 | `case09_llm_per_prompt_evaluation.py` | AI Engineer (Mia) | RAG eval suite passes aggregate threshold; 3 specific prompts are broken |
| 10 | `case10_rag_pipeline_decomposition.py` | AI Engineer | 4-stage RAG pipeline produces poor answers; unclear which stage is failing |

**APIs shown:** `SampleObservation`, per-sample `MetricRecord`, `get_run_snapshot`, `compare_runs`, `diagnose_run`

---

## Group 6: Team / Delivery

| # | Script | Persona | Problem |
|---|--------|---------|---------|
| 11 | `case11_project_history_onboarding.py` | Team Lead (Alex) | New engineer joins; no single place to see project history and performance trend |
| 12 | `case12_delivery_quality_certificate.py` | FDE (Tom) | Enterprise client requires a formal model quality certificate for procurement |

**APIs shown:** `list_runs`, `list_deployments`, `build_multi_run_report`, `select_best_run`, `build_snapshot_report`, `EnvironmentSnapshot`

---

## Running all cases

```bash
for f in examples/case_studies/case*.py; do
    echo "=== $f ==="
    uv run python "$f"
    echo
done
```
