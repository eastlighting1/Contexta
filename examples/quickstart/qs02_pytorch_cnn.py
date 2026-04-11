"""Quickstart 02: Deep Learning - CNN Image Classifier Training Loop.

Purpose:
    Shows epoch-level metric tracking and overfitting detection via
    DegradedRecord in a PyTorch CNN training workflow. No external data
    download -- uses synthetic tensors that simulate CIFAR-like images.

Contexta features demonstrated:
    - MetricRecord per epoch (train-loss, val-loss, val-accuracy)
    - DegradedRecord for overfitting / val-loss stagnation detection
    - StructuredEventRecord for dataset registration
    - EnvironmentSnapshot
    - diagnose_run, get_run_snapshot (epoch val-loss curve)
    - audit_reproducibility
    - build_snapshot_report

Dependencies:
    torch, numpy, contexta

Run:
    uv run python examples/quickstart/qs02_pytorch_cnn.py
"""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    DegradedPayload,
    DegradedRecord,
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
PROJECT_NAME = "cnn-image-clf"
WORKSPACE = Path(__file__).parent / ".contexta" / PROJECT_NAME
NUM_EPOCHS = 15
BATCH_SIZE = 32
LEARNING_RATE = 1e-3

_rid = 0


def _next_rid() -> str:
    global _rid
    _rid += 1
    return f"r{_rid:05d}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Model definition
# ---------------------------------------------------------------------------
class SimpleCNN(nn.Module):
    def __init__(self, num_classes: int = 10) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Linear(64 * 8 * 8, 256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(x).view(x.size(0), -1))


# ---------------------------------------------------------------------------
# Training helpers
# ---------------------------------------------------------------------------
def train_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    device: torch.device,
) -> float:
    model.train()
    total_loss = 0.0
    for xb, yb in loader:
        xb, yb = xb.to(device), yb.to(device)
        optimizer.zero_grad()
        loss = criterion(model(xb), yb)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * len(xb)
    return total_loss / len(loader.dataset)


def eval_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, float]:
    model.eval()
    total_loss = 0.0
    correct = 0
    with torch.no_grad():
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            logits = model(xb)
            total_loss += criterion(logits, yb).item() * len(xb)
            correct += (logits.argmax(1) == yb).sum().item()
    n = len(loader.dataset)
    return total_loss / n, correct / n


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 60)
    print("QS02: CNN Training Loop with Overfitting Detection")
    print("=" * 60)

    ctx = Contexta(
        config=UnifiedConfig(
            project_name=PROJECT_NAME,
            workspace=WorkspaceConfig(root_path=WORKSPACE),
        )
    )
    store = ctx.metadata_store

    # ---- Synthetic data (CIFAR-like) ----
    torch.manual_seed(42)
    np.random.seed(42)

    X_all = torch.randn(1000, 3, 32, 32)
    y_all = torch.randint(0, 10, (1000,))
    train_loader = DataLoader(TensorDataset(X_all[:800], y_all[:800]), batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(TensorDataset(X_all[800:900], y_all[800:900]), batch_size=BATCH_SIZE)
    test_loader = DataLoader(TensorDataset(X_all[900:], y_all[900:]), batch_size=BATCH_SIZE)

    device = torch.device("cpu")
    model = SimpleCNN(num_classes=10).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

    run_name = "cnn-v1"
    run_ref = f"run:{PROJECT_NAME}.{run_name}"
    project_ref = f"project:{PROJECT_NAME}"
    stage_pre_ref = f"stage:{PROJECT_NAME}.{run_name}.preprocess"
    stage_train_ref = f"stage:{PROJECT_NAME}.{run_name}.train"
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

    # ---- Stage: preprocess ----
    pre_start = _now()
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=stage_pre_ref,
            run_ref=run_ref,
            stage_name="preprocess",
            status="completed",
            started_at=pre_start,
            ended_at=pre_start,
            order_index=0,
        )
    )
    ctx.record_store.append(
        StructuredEventRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                record_type="event",
                recorded_at=pre_start,
                observed_at=pre_start,
                producer_ref="contexta.qs02",
                run_ref=run_ref,
                stage_execution_ref=stage_pre_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=StructuredEventPayload(
                event_key="dataset.registered",
                level="info",
                message="Synthetic CIFAR-like dataset -- 1000 samples, 3x32x32, 10 classes",
                attributes={"source": "synthetic", "n_train": "800", "n_val": "100", "n_test": "100"},
                origin_marker="explicit_capture",
            ),
        )
    )

    # ---- Stage: train ----
    train_start = _now()
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=stage_train_ref,
            run_ref=run_ref,
            stage_name="train",
            status="completed",
            started_at=train_start,
            ended_at=train_start,
            order_index=1,
        )
    )

    print(f"\nTraining CNN for {NUM_EPOCHS} epochs ...")
    best_val_loss = float("inf")
    consecutive_no_improve = 0
    overfitting_flagged = False
    val_accuracies: list[float] = []

    for epoch in range(1, NUM_EPOCHS + 1):
        train_loss = train_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, val_acc = eval_epoch(model, val_loader, criterion, device)
        val_accuracies.append(val_acc)

        print(f"  Epoch {epoch:2d}/{NUM_EPOCHS}  train-loss={train_loss:.4f}  "
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
                        producer_ref="contexta.qs02",
                        run_ref=run_ref,
                        stage_execution_ref=stage_train_ref,
                        completeness_marker="complete",
                        degradation_marker="none",
                    ),
                    payload=MetricPayload(metric_key=mkey, value=float(mval), value_type="float64"),
                )
            )

        # Overfitting detection: val_loss stagnation
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            consecutive_no_improve = 0
        else:
            consecutive_no_improve += 1

        if consecutive_no_improve >= 3 and not overfitting_flagged:
            overfitting_flagged = True
            warn_ts = _now()
            ctx.record_store.append(
                DegradedRecord(
                    envelope=RecordEnvelope(
                        record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                        record_type="degraded",
                        recorded_at=warn_ts,
                        observed_at=warn_ts,
                        producer_ref="contexta.qs02",
                        run_ref=run_ref,
                        stage_execution_ref=stage_train_ref,
                        completeness_marker="complete",
                        degradation_marker="partial_failure",
                    ),
                    payload=DegradedPayload(
                        issue_key="val_loss_not_improving",
                        category="verification",
                        severity="warning",
                        summary="val-loss has not improved for 3 consecutive epochs",
                        attributes={"epoch": str(epoch), "consecutive_no_improve": "3"},
                        origin_marker="explicit_capture",
                    ),
                )
            )
            print(f"  [WARNING] val-loss has not improved for 3 consecutive epochs (epoch {epoch})")

    train_end = _now()

    # Summary train-stage metrics
    for mkey, mval in [
        ("mean-val-accuracy", float(np.mean(val_accuracies[-5:]))),
        ("best-val-accuracy", float(np.max(val_accuracies))),
    ]:
        ctx.record_store.append(
            MetricRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                    record_type="metric",
                    recorded_at=train_end,
                    observed_at=train_end,
                    producer_ref="contexta.qs02",
                    run_ref=run_ref,
                    stage_execution_ref=stage_train_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=MetricPayload(metric_key=mkey, value=mval, value_type="float64"),
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

    test_loss, test_acc = eval_epoch(model, test_loader, criterion, device)

    # Macro-averaged precision / recall / f1
    model.eval()
    all_preds: list[int] = []
    all_targets: list[int] = []
    with torch.no_grad():
        for xb, yb in test_loader:
            logits = model(xb.to(device))
            all_preds.extend(logits.argmax(1).tolist())
            all_targets.extend(yb.tolist())

    f1_per_class, prec_per_class, rec_per_class = [], [], []
    for c in range(10):
        tp = sum(1 for p, t in zip(all_preds, all_targets) if p == c and t == c)
        fp = sum(1 for p, t in zip(all_preds, all_targets) if p == c and t != c)
        fn = sum(1 for p, t in zip(all_preds, all_targets) if p != c and t == c)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        prec_per_class.append(prec)
        rec_per_class.append(rec)
        f1_per_class.append(f1)

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
    eval_metrics = {
        "accuracy": test_acc,
        "f1": float(np.mean(f1_per_class)),
        "precision": float(np.mean(prec_per_class)),
        "recall": float(np.mean(rec_per_class)),
    }
    for mkey, mval in eval_metrics.items():
        ctx.record_store.append(
            MetricRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                    record_type="metric",
                    recorded_at=eval_end,
                    observed_at=eval_end,
                    producer_ref="contexta.qs02",
                    run_ref=run_ref,
                    stage_execution_ref=stage_eval_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=MetricPayload(metric_key=mkey, value=float(mval), value_type="float64"),
            )
        )

    print(f"\nTest accuracy: {test_acc:.4f}  f1: {eval_metrics['f1']:.4f}")

    # ---- Environment ----
    python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    store.environments.put_environment_snapshot(
        EnvironmentSnapshot(
            environment_snapshot_ref=env_ref,
            run_ref=run_ref,
            captured_at=eval_end,
            python_version=python_ver,
            platform=platform.system().lower(),
            packages={"torch": torch.__version__, "numpy": np.__version__},
        )
    )

    # ---- Analysis ----
    print("\n--- Analysis ---")

    diag = ctx.diagnose_run(run_ref)
    if diag.issues:
        print("\nDiagnostics issues:")
        for issue in diag.issues:
            print(f"  [{issue.severity}] {issue.code}: {issue.summary}")
    else:
        print("\nDiagnostics: no issues.")

    snapshot = ctx.get_run_snapshot(run_ref)

    def _epoch_num(key: str) -> int:
        try:
            return int(key.split("-")[1])
        except (IndexError, ValueError):
            return 0

    val_loss_records = sorted(
        [r for r in snapshot.records if r.record_type == "metric" and "val-loss" in r.key and "epoch-" in r.key],
        key=lambda r: _epoch_num(r.key),
    )
    if val_loss_records:
        print("\nEpoch val-loss curve (first 5 and last 5):")
        display = val_loss_records[:5] + (["..."] if len(val_loss_records) > 10 else []) + val_loss_records[-5:]
        for item in display:
            if isinstance(item, str):
                print(f"  {item}")
            else:
                print(f"  {item.key:<32} {item.value:.4f}")

    repro = ctx.audit_reproducibility(run_ref)
    print(f"\nReproducibility audit:")
    print(f"  python:   {repro.python_version}")
    print(f"  platform: {repro.platform}")
    print(f"  packages: {repro.package_count}")
    print(f"  status:   {repro.reproducibility_status}")

    report = ctx.build_snapshot_report(run_ref)
    print(f"\nSnapshot report: {report.title}")
    for sec in report.sections:
        print(f"  - {sec.title}")

    store.close()


if __name__ == "__main__":
    main()
