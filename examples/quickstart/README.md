# Quickstart Examples

End-to-end examples showing Contexta observability integrated into real ML/DL workflows.
Each script runs a complete pipeline — data → train → evaluate → analyse — and can be used
directly as a starting template.

## Choose your starting point

| File | Framework | Use case | External download |
|------|-----------|----------|-------------------|
| `qs01_sklearn_tabular.py` | scikit-learn | Tabular classification, model comparison | None |
| `qs02_pytorch_cnn.py` | PyTorch | Image classification, training loop | None (synthetic data) |
| `qs03_bert_finetuning.py` | PyTorch + HuggingFace Transformers | NLP fine-tuning, HPO comparison | ~250 MB (DistilBERT) |
| `qs04_llm_evaluation.py` | vLLM (OpenAI alternative in comments) | RAG pipeline, per-prompt evaluation | Model of your choice |

## What every example demonstrates

Each script covers the full observability cycle:

1. **Contract** — define `Project`, `Run`, `StageExecution` structure before training starts
2. **Collect** — log `MetricRecord`, `StructuredEventRecord`, `DegradedRecord` during training
3. **Environment** — capture `EnvironmentSnapshot` (framework versions, Python version)
4. **Analyse** — `compare_runs`, `diagnose_run`, `get_run_snapshot`, `build_*_report`

---

## QS01 — Classical ML: SVM vs Random Forest

```bash
uv run python examples/quickstart/qs01_sklearn_tabular.py
```

**Pipeline**: UCI Wine Quality dataset → StandardScaler → 5-fold CV → test evaluation → comparison → deployment

**Contexta integration points**:
- `StructuredEventRecord` on the preprocess stage — dataset registration
- `MetricRecord` per CV fold (5 folds × 2 runs = 10 fold records) — training transparency
- `MetricRecord` on evaluate stage — accuracy, f1, precision, recall
- `EnvironmentSnapshot` — scikit-learn + numpy versions
- `compare_runs` — side-by-side evaluate-stage delta table
- `select_best_run` — programmatic winner selection
- `diagnose_run` — pre-deploy health check
- `build_snapshot_report` — formal experiment document
- `DeploymentExecution` — register which run went to production

**Key output**:
```
Run comparison (evaluate stage):
  accuracy   svm=0.9722  rf=1.0000  delta=+0.0278
  f1         svm=0.9720  rf=1.0000  delta=+0.0280

Best run: rf-experiment
Deployment 'prod-v1' registered for run: rf-experiment
```

---

## QS02 — Deep Learning: CNN Training Loop

```bash
uv run python examples/quickstart/qs02_pytorch_cnn.py
```

**Pipeline**: Synthetic CIFAR-like tensors (800 train / 100 val / 100 test, 3×32×32, 10 classes) → 3-layer CNN → 15 epochs → overfitting detection → evaluation

**Contexta integration points**:
- `MetricRecord` per epoch × 3 metrics (train-loss, val-loss, val-accuracy) — full learning curve stored
- `DegradedRecord` (category=`verification`, severity=`warning`) — fired once when val-loss fails to improve for 3 consecutive epochs
- `EnvironmentSnapshot` — torch + numpy versions
- `diagnose_run` — surfaces the overfitting warning
- `get_run_snapshot` — extract epoch val-loss curve for post-training inspection
- `audit_reproducibility` — confirms environment was captured
- `build_snapshot_report`

**Key output**:
```
[WARNING] val-loss has not improved for 3 consecutive epochs (epoch 7)

Diagnostics issues:
  [warning] degraded_record: degraded record detected for val_loss_not_improving
```

**Adapting to your model**: replace `SimpleCNN` and the synthetic data with your own model and `DataLoader`. The Contexta instrumentation inside the epoch loop stays the same.

---

## QS03 — NLP: DistilBERT Fine-tuning

```bash
uv run python examples/quickstart/qs03_bert_finetuning.py
```

> First run downloads ~250 MB (DistilBERT) from HuggingFace. Subsequent runs use the cache.

**Pipeline**: 60-sentence inline synthetic sentiment dataset → tokenize → fine-tune DistilBERT × 2 learning rates (2e-5, 5e-5), 3 epochs each → comparison

**Contexta integration points**:
- Two runs with identical stage structure — HPO pattern
- `MetricRecord` per epoch (train-loss, val-loss, val-accuracy) for both runs
- `EnvironmentSnapshot` — torch + transformers versions
- `compare_runs` — finetune stage + evaluate stage deltas between the two LRs
- `compare_environments` — confirms both runs share the same environment
- `select_best_run` — best LR by f1
- `build_multi_run_report` — HPO summary report across both runs

**Key output**:
```
Compare finetune stage (lr2e5 vs lr5e5):
  epoch-3-val-accuracy  0.XXX -> 0.XXX  delta=+/-X.XXX

Best run: bert-lr2e5 (or bert-lr5e5)
Multi-run report: "Multi-Run Comparison Report: ..."
```

**Adapting to your dataset**: replace `TEXTS` / `LABELS` with your own data or add a HuggingFace dataset loader. The Contexta instrumentation in the training loop stays the same.

---

## QS04 — LLM/RAG: Per-Prompt Evaluation

```bash
uv run python examples/quickstart/qs04_llm_evaluation.py
```

> Requires vLLM on Linux/WSL with a compatible GPU.
> For the OpenAI API alternative, see comments near `generate_answer` in the script.

**Pipeline**: 24 test prompts across 8 knowledge categories → keyword-overlap retrieval → vLLM generation → per-prompt scoring → aggregate analysis

**Contexta integration points**:
- `SampleObservation` per prompt — each prompt is a trackable unit
- `MetricRecord` per sample × 3 metrics (relevance, faithfulness, answer-length)
- `MetricRecord` aggregate — mean-relevance, mean-faithfulness, mean-latency-ms at stage level
- `EnvironmentSnapshot` — vllm + torch versions
- `get_run_snapshot` — filter sample-level records to find failing prompts (relevance < 0.3)
- `diagnose_run` + `build_snapshot_report`

**Key output**:
```
Per-prompt quality:
  prompt-01  [python      ]  relevance=0.42  faithfulness=0.31  length=28  OK
  prompt-07  [escalation  ]  relevance=0.08  faithfulness=0.12  length=15  FAIL
  ...

Failing prompts (relevance < 0.3): 3
```

**Switching to OpenAI**: uncomment the OpenAI block near `generate_answer` and comment out the vLLM block. The Contexta instrumentation is identical for both backends.

---

## Observability elements at a glance

| Element | QS01 | QS02 | QS03 | QS04 |
|---------|------|------|------|------|
| `MetricRecord` — training metrics | CV folds | Per epoch | Per epoch | Aggregate |
| `MetricRecord` — eval metrics | accuracy/f1/... | accuracy/f1/... | accuracy/f1/... | relevance/faithfulness/... |
| `MetricRecord` — per sample | — | — | — | Per prompt |
| `StructuredEventRecord` | Dataset version | Dataset version | Dataset version | Pipeline registration |
| `DegradedRecord` | — | Overfitting | — | — |
| `EnvironmentSnapshot` | sklearn versions | torch versions | transformers versions | vllm versions |
| `SampleObservation` | — | — | — | Per prompt |
| `compare_runs` | SVM vs RF | — | lr2e5 vs lr5e5 | — |
| `build_multi_run_report` | — | — | HPO report | — |
| `build_snapshot_report` | Pre-deploy doc | Experiment doc | — | Eval doc |
| `DeploymentExecution` | Best model | — | — | — |

---

## Legacy examples

The original `verified_quickstart.py` and `runtime_capture_preview.py` are kept for
regression coverage (`tests/e2e/test_quickstart_examples.py`). Use the `qs0*` scripts
for new work.
