"""Quickstart 03: NLP - DistilBERT Fine-tuning for Sentiment Classification.

Purpose:
    Shows HPO comparison of two learning rates using Contexta. Two runs
    (bert-lr2e5 and bert-lr5e5) are compared with multi-run report.

Note:
    First run downloads ~250MB model from HuggingFace (distilbert-base-uncased).
    Subsequent runs use the cached model.

Contexta features demonstrated:
    - MetricRecord per epoch (train-loss, val-loss, val-accuracy)
    - StructuredEventRecord for dataset registration
    - EnvironmentSnapshot
    - compare_runs (finetune stage + evaluate stage)
    - compare_environments
    - select_best_run
    - build_multi_run_report

Dependencies:
    torch, transformers, numpy, contexta

Run:
    uv run python examples/quickstart/qs03_bert_finetuning.py
"""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import transformers
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    EnvironmentSnapshot,
    MetricPayload,
    MetricRecord,
    Project,
    RecordEnvelope,
    Run,
    StageExecution,
    StructuredEventPayload,
    StructuredEventRecord,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_NAME = "bert-sentiment"
WORKSPACE = Path(__file__).parent / ".contexta" / PROJECT_NAME
MODEL_ID = "distilbert-base-uncased"
NUM_EPOCHS = 3
BATCH_SIZE = 8

_rid = 0


def _next_rid() -> str:
    global _rid
    _rid += 1
    return f"r{_rid:05d}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Synthetic sentiment dataset (60 samples, binary labels)
# ---------------------------------------------------------------------------
TEXTS = [
    "This product is excellent and works perfectly.",
    "Amazing quality, exceeded all my expectations.",
    "Highly recommend this to everyone I know.",
    "Best purchase I have made this year by far.",
    "Fantastic experience, will definitely buy again.",
    "Outstanding performance and great value for money.",
    "Absolutely love this, works exactly as described.",
    "Great product, very happy with my purchase.",
    "Superb quality and arrived quickly, very pleased.",
    "Wonderful item, exactly what I was looking for.",
    "Really impressive, five stars without hesitation.",
    "Perfect fit and excellent craftsmanship throughout.",
    "Incredible value, blew my expectations out of the water.",
    "Could not be happier with this product overall.",
    "Delightful experience from ordering to delivery.",
    "Top quality product, works flawlessly every time.",
    "Very satisfied, this is exactly what I needed.",
    "Brilliant product, highly recommended to all buyers.",
    "Love everything about this, a truly great buy.",
    "Exceptional product that delivers on every promise.",
    "Superb in every way, I am genuinely impressed.",
    "Great quality item, fast shipping, very happy.",
    "Very pleased with this purchase, works great.",
    "Outstanding item, perfect condition, fast delivery.",
    "Excellent build quality and easy to use daily.",
    "Perfect purchase, arrived fast and as described.",
    "Loved it from the start, highly recommend this.",
    "Brilliant value for money, very good quality.",
    "This exceeded expectations, very well made item.",
    "Absolutely fantastic product, could not fault it.",
    "Terrible product, broke after just one day.",
    "Very disappointed, does not work as advertised.",
    "Waste of money, poor quality and bad design.",
    "Not what I expected at all, very dissatisfied.",
    "Returned immediately, completely unusable product.",
    "Horrible experience, customer service was useless.",
    "Broke within a week, definitely not worth buying.",
    "Very poor quality, would not recommend this item.",
    "Defective product, packaging was damaged on arrival.",
    "Extremely disappointing, fails to do basic functions.",
    "Awful product, nothing like the description given.",
    "Complete waste of time and money, avoid this.",
    "Bad quality materials, fell apart after minimal use.",
    "Really unhappy with this purchase, very poor build.",
    "Does not work at all, absolute rubbish product.",
    "Regret buying this, terrible quality for the price.",
    "Overpriced and underperforming, not worth a penny.",
    "Poorly made and uncomfortable, returning immediately.",
    "Dreadful item, nothing like the photos shown online.",
    "Frustrated and annoyed, this product is garbage.",
    "Cheap and nasty, fell apart on first use today.",
    "Complete disaster, the worst product I have tried.",
    "Abysmal quality, totally useless for any purpose.",
    "Junk product, do not waste your hard earned money.",
    "Very bad experience, would give zero stars if able.",
    "Falling apart already, cannot believe the poor build.",
    "Shoddy workmanship, clearly not tested before sale.",
    "Disappointed beyond belief, this is just plain awful.",
    "Unacceptable quality for this price, avoid it.",
    "Nothing works as described, total disappointment.",
    "Lousy product all round, I deeply regret buying.",
]
LABELS = [1] * 30 + [0] * 30


# ---------------------------------------------------------------------------
# Dataset class
# ---------------------------------------------------------------------------
class SentimentDataset(Dataset):
    def __init__(self, encodings: dict[str, torch.Tensor], labels: list[int]) -> None:
        self.encodings = encodings
        self.labels = labels

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        item = {k: v[idx] for k, v in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


# ---------------------------------------------------------------------------
# Training helpers
# ---------------------------------------------------------------------------
def train_one_epoch(model: Any, loader: DataLoader, optimizer: Any, device: torch.device) -> float:
    model.train()
    total_loss = 0.0
    for batch in loader:
        optimizer.zero_grad()
        outputs = model(
            input_ids=batch["input_ids"].to(device),
            attention_mask=batch["attention_mask"].to(device),
            labels=batch["labels"].to(device),
        )
        outputs.loss.backward()
        optimizer.step()
        total_loss += outputs.loss.item()
    return total_loss / len(loader)


def eval_epoch(model: Any, loader: DataLoader, device: torch.device) -> tuple[float, float]:
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    with torch.no_grad():
        for batch in loader:
            outputs = model(
                input_ids=batch["input_ids"].to(device),
                attention_mask=batch["attention_mask"].to(device),
                labels=batch["labels"].to(device),
            )
            total_loss += outputs.loss.item()
            preds = outputs.logits.argmax(dim=-1)
            correct += (preds == batch["labels"].to(device)).sum().item()
            total += batch["labels"].size(0)
    return total_loss / len(loader), correct / total


def compute_eval_metrics(model: Any, loader: DataLoader, device: torch.device) -> dict[str, float]:
    model.eval()
    all_preds: list[int] = []
    all_targets: list[int] = []
    with torch.no_grad():
        for batch in loader:
            logits = model(
                input_ids=batch["input_ids"].to(device),
                attention_mask=batch["attention_mask"].to(device),
            ).logits
            all_preds.extend(logits.argmax(dim=-1).tolist())
            all_targets.extend(batch["labels"].tolist())

    acc = sum(p == t for p, t in zip(all_preds, all_targets)) / len(all_targets)
    f1s, precs, recs = [], [], []
    for c in [0, 1]:
        tp = sum(1 for p, t in zip(all_preds, all_targets) if p == c and t == c)
        fp = sum(1 for p, t in zip(all_preds, all_targets) if p == c and t != c)
        fn = sum(1 for p, t in zip(all_preds, all_targets) if p != c and t == c)
        pr = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rc = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * pr * rc / (pr + rc) if (pr + rc) > 0 else 0.0
        precs.append(pr)
        recs.append(rc)
        f1s.append(f1)
    return {
        "accuracy": float(acc),
        "f1": float(np.mean(f1s)),
        "precision": float(np.mean(precs)),
        "recall": float(np.mean(recs)),
    }


# ---------------------------------------------------------------------------
# Finetune one run and log everything to Contexta
# ---------------------------------------------------------------------------
def finetune_and_log(
    run_name: str,
    learning_rate: float,
    train_loader: DataLoader,
    val_loader: DataLoader,
    test_loader: DataLoader,
    project_ref: str,
    ctx: Any,
    store: Any,
    device: torch.device,
) -> None:
    run_ref = f"run:{PROJECT_NAME}.{run_name}"
    stage_tok_ref = f"stage:{PROJECT_NAME}.{run_name}.tokenize"
    stage_fine_ref = f"stage:{PROJECT_NAME}.{run_name}.finetune"
    stage_eval_ref = f"stage:{PROJECT_NAME}.{run_name}.evaluate"
    env_ref = f"environment:{PROJECT_NAME}.{run_name}.env-snapshot"

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

    # ---- Stage: tokenize ----
    tok_start = _now()
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=stage_tok_ref,
            run_ref=run_ref,
            stage_name="tokenize",
            status="completed",
            started_at=tok_start,
            ended_at=tok_start,
            order_index=0,
        )
    )
    ctx.record_store.append(
        StructuredEventRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                record_type="event",
                recorded_at=tok_start,
                observed_at=tok_start,
                producer_ref="contexta.qs03",
                run_ref=run_ref,
                stage_execution_ref=stage_tok_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=StructuredEventPayload(
                event_key="dataset.registered",
                level="info",
                message="Synthetic sentiment dataset -- 60 samples, binary labels",
                attributes={"model": MODEL_ID, "n_samples": "60", "n_classes": "2"},
                origin_marker="explicit_capture",
            ),
        )
    )

    # ---- Stage: finetune ----
    fine_start = _now()
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=stage_fine_ref,
            run_ref=run_ref,
            stage_name="finetune",
            status="completed",
            started_at=fine_start,
            ended_at=fine_start,
            order_index=1,
        )
    )

    model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID, num_labels=2)
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=0.01)

    print(f"  Finetuning {run_name} (lr={learning_rate}) ...")
    for epoch in range(1, NUM_EPOCHS + 1):
        train_loss = train_one_epoch(model, train_loader, optimizer, device)
        val_loss, val_acc = eval_epoch(model, val_loader, device)
        print(f"    Epoch {epoch}/{NUM_EPOCHS}  train-loss={train_loss:.4f}  "
              f"val-loss={val_loss:.4f}  val-acc={val_acc:.4f}")

        ts = _now()
        for mkey, mval in [
            (f"epoch-{epoch}-train-loss", train_loss),
            (f"epoch-{epoch}-val-loss", val_loss),
            (f"epoch-{epoch}-val-accuracy", val_acc),
        ]:
            ctx.record_store.append(
                MetricRecord(
                    envelope=RecordEnvelope(
                        record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                        record_type="metric",
                        recorded_at=ts,
                        observed_at=ts,
                        producer_ref="contexta.qs03",
                        run_ref=run_ref,
                        stage_execution_ref=stage_fine_ref,
                        completeness_marker="complete",
                        degradation_marker="none",
                    ),
                    payload=MetricPayload(metric_key=mkey, value=float(mval), value_type="float64"),
                )
            )

    # ---- Stage: evaluate ----
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

    eval_metrics = compute_eval_metrics(model, test_loader, device)
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
    for mkey, mval in eval_metrics.items():
        ctx.record_store.append(
            MetricRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                    record_type="metric",
                    recorded_at=eval_end,
                    observed_at=eval_end,
                    producer_ref="contexta.qs03",
                    run_ref=run_ref,
                    stage_execution_ref=stage_eval_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=MetricPayload(metric_key=mkey, value=float(mval), value_type="float64"),
            )
        )

    print(f"  {run_name}: accuracy={eval_metrics['accuracy']:.4f}  f1={eval_metrics['f1']:.4f}")

    # ---- Environment ----
    python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    store.environments.put_environment_snapshot(
        EnvironmentSnapshot(
            environment_snapshot_ref=env_ref,
            run_ref=run_ref,
            captured_at=eval_end,
            python_version=python_ver,
            platform=platform.system().lower(),
            packages={
                "torch": torch.__version__,
                "transformers": transformers.__version__,
                "numpy": np.__version__,
            },
        )
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
from typing import Any


def main() -> None:
    print("=" * 60)
    print("QS03: DistilBERT Fine-tuning - HPO LR Comparison")
    print("=" * 60)

    ctx = Contexta(
        config=UnifiedConfig(
            project_name=PROJECT_NAME,
            workspace=WorkspaceConfig(root_path=WORKSPACE),
        )
    )
    store = ctx.metadata_store

    device = torch.device("cpu")

    # ---- Tokenize data once ----
    print("\nLoading tokenizer and tokenizing data ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

    n = len(TEXTS)
    split = int(n * 0.8)
    train_texts, test_texts = TEXTS[:split], TEXTS[split:]
    train_labels, test_labels = LABELS[:split], LABELS[split:]
    val_texts, val_labels = train_texts[:8], train_labels[:8]
    actual_train_texts, actual_train_labels = train_texts[8:], train_labels[8:]

    def tokenize(texts: list[str]) -> dict[str, torch.Tensor]:
        return tokenizer(texts, padding=True, truncation=True, max_length=64, return_tensors="pt")

    train_loader = DataLoader(
        SentimentDataset(tokenize(actual_train_texts), actual_train_labels),
        batch_size=BATCH_SIZE,
        shuffle=True,
    )
    val_loader = DataLoader(SentimentDataset(tokenize(val_texts), val_labels), batch_size=BATCH_SIZE)
    test_loader = DataLoader(SentimentDataset(tokenize(test_texts), test_labels), batch_size=BATCH_SIZE)

    project_ref = f"project:{PROJECT_NAME}"
    store.projects.put_project(
        Project(project_ref=project_ref, name=PROJECT_NAME, created_at=_now())
    )

    # ---- Run A: lr=2e-5 ----
    run_a_ref = f"run:{PROJECT_NAME}.bert-lr2e5"
    print("\nRun A: bert-lr2e5")
    finetune_and_log(
        run_name="bert-lr2e5",
        learning_rate=2e-5,
        train_loader=train_loader,
        val_loader=val_loader,
        test_loader=test_loader,
        project_ref=project_ref,
        ctx=ctx,
        store=store,
        device=device,
    )

    # ---- Run B: lr=5e-5 ----
    run_b_ref = f"run:{PROJECT_NAME}.bert-lr5e5"
    print("\nRun B: bert-lr5e5")
    finetune_and_log(
        run_name="bert-lr5e5",
        learning_rate=5e-5,
        train_loader=train_loader,
        val_loader=val_loader,
        test_loader=test_loader,
        project_ref=project_ref,
        ctx=ctx,
        store=store,
        device=device,
    )

    # ---- Analysis ----
    print("\n--- Analysis ---")

    comparison = ctx.compare_runs(run_a_ref, run_b_ref)
    print("\nRun comparison (finetune stage - epoch-3 metrics):")
    for sc in comparison.stage_comparisons:
        if sc.stage_name == "finetune":
            for d in sc.metric_deltas:
                if "epoch-3" in d.metric_key and d.left_value is not None and d.right_value is not None:
                    print(f"  {d.metric_key:<32} lr2e5={d.left_value:.4f}  lr5e5={d.right_value:.4f}  delta={d.delta:+.4f}")

    print("\nRun comparison (evaluate stage):")
    for sc in comparison.stage_comparisons:
        if sc.stage_name == "evaluate":
            for d in sc.metric_deltas:
                if d.left_value is not None and d.right_value is not None:
                    print(f"  {d.metric_key:<14} lr2e5={d.left_value:.4f}  lr5e5={d.right_value:.4f}  delta={d.delta:+.4f}")

    env_diff = ctx.compare_environments(run_a_ref, run_b_ref)
    print(f"\nEnvironment comparison:")
    print(f"  python_version_changed: {env_diff.python_version_changed}")
    if env_diff.changed_packages:
        for chg in env_diff.changed_packages:
            print(f"  package '{chg.key}': {chg.left_value} -> {chg.right_value}")
    else:
        print("  changed_packages: none (environments identical)")

    best_ref = ctx.select_best_run([run_a_ref, run_b_ref], "f1", stage_name="evaluate")
    best_name = best_ref.split(".")[-1] if best_ref else "unknown"
    print(f"\nBest run (f1, evaluate): {best_name}")

    multi_report = ctx.build_multi_run_report([run_a_ref, run_b_ref])
    print(f"\nMulti-run report: {multi_report.title}")
    for sec in multi_report.sections:
        print(f"  - {sec.title}")

    store.close()


if __name__ == "__main__":
    main()
