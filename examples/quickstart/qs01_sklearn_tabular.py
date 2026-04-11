"""Quickstart 01: Classical ML - SVM vs Random Forest on Wine Quality Classification.

Purpose:
    Shows a full train -> evaluate -> compare -> deploy cycle using Contexta
    observability integrated into a scikit-learn tabular ML workflow.

Contexta features demonstrated:
    - Project / Run / StageExecution / DeploymentExecution registration
    - MetricRecord (CV fold metrics, evaluation metrics)
    - StructuredEventRecord (dataset registration)
    - EnvironmentSnapshot
    - compare_runs, select_best_run, diagnose_run
    - build_snapshot_report
    - DeploymentExecution for best run

Dependencies:
    scikit-learn, numpy, contexta

Run:
    uv run python examples/quickstart/qs01_sklearn_tabular.py
"""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import sklearn
from sklearn.datasets import load_wine
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    DeploymentExecution,
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
PROJECT_NAME = "wine-quality-clf"
WORKSPACE = Path(__file__).parent / ".contexta" / PROJECT_NAME

_rid = 0


def _next_rid() -> str:
    global _rid
    _rid += 1
    return f"r{_rid:05d}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Model definition and helpers
# ---------------------------------------------------------------------------
def train_and_log(
    model: Any,
    run_name: str,
    X_train: Any,
    X_test: Any,
    y_train: Any,
    y_test: Any,
    ctx: Any,
    store: Any,
) -> None:
    """Train one model, log CV fold metrics and eval metrics to Contexta."""
    project_ref = f"project:{PROJECT_NAME}"
    run_ref = f"run:{PROJECT_NAME}.{run_name}"
    stage_pre_ref = f"stage:{PROJECT_NAME}.{run_name}.preprocess"
    stage_train_ref = f"stage:{PROJECT_NAME}.{run_name}.train"
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
                producer_ref="contexta.qs01",
                run_ref=run_ref,
                stage_execution_ref=stage_pre_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=StructuredEventPayload(
                event_key="dataset.registered",
                level="info",
                message="UCI Wine dataset -- 178 samples, 13 features, 3 classes",
                attributes={"source": "sklearn.datasets", "n_samples": "178", "n_features": "13"},
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

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    fold_scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="f1_weighted")
    train_end = _now()

    for fold_i, fold_score in enumerate(fold_scores, start=1):
        ctx.record_store.append(
            MetricRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                    record_type="metric",
                    recorded_at=train_end,
                    observed_at=train_end,
                    producer_ref="contexta.qs01",
                    run_ref=run_ref,
                    stage_execution_ref=stage_train_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=MetricPayload(
                    metric_key=f"cv-f1-fold-{fold_i}",
                    value=float(fold_score),
                    value_type="float64",
                ),
            )
        )
    ctx.record_store.append(
        MetricRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                record_type="metric",
                recorded_at=train_end,
                observed_at=train_end,
                producer_ref="contexta.qs01",
                run_ref=run_ref,
                stage_execution_ref=stage_train_ref,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=MetricPayload(
                metric_key="cv-mean-f1",
                value=float(fold_scores.mean()),
                value_type="float64",
            ),
        )
    )

    model.fit(X_train, y_train)

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

    y_pred = model.predict(X_test)
    eval_metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred, average="weighted")),
        "precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
    }
    eval_end = _now()

    # Register run now that we have both start and end times
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
                    producer_ref="contexta.qs01",
                    run_ref=run_ref,
                    stage_execution_ref=stage_eval_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=MetricPayload(
                    metric_key=mkey,
                    value=mval,
                    value_type="float64",
                ),
            )
        )

    print(f"  {run_name}: CV f1={fold_scores.mean():.4f}  "
          f"test accuracy={eval_metrics['accuracy']:.4f}  f1={eval_metrics['f1']:.4f}")

    # ---- Environment ----
    python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    store.environments.put_environment_snapshot(
        EnvironmentSnapshot(
            environment_snapshot_ref=env_ref,
            run_ref=run_ref,
            captured_at=eval_end,
            python_version=python_ver,
            platform=platform.system().lower(),
            packages={"scikit-learn": sklearn.__version__, "numpy": np.__version__},
        )
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 60)
    print("QS01: SVM vs Random Forest - Wine Quality Classification")
    print("=" * 60)

    ctx = Contexta(
        config=UnifiedConfig(
            project_name=PROJECT_NAME,
            workspace=WorkspaceConfig(root_path=WORKSPACE),
        )
    )
    store = ctx.metadata_store

    # ---- Data ----
    wine = load_wine()
    X, y = wine.data, wine.target
    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train_raw)
    X_test = scaler.transform(X_test_raw)

    store.projects.put_project(
        Project(
            project_ref=f"project:{PROJECT_NAME}",
            name=PROJECT_NAME,
            created_at=_now(),
        )
    )

    # ---- Run A: SVM baseline ----
    svm_run_ref = f"run:{PROJECT_NAME}.svm-baseline"
    print("\nTraining Run A: svm-baseline ...")
    train_and_log(
        model=SVC(kernel="rbf", C=1.0, random_state=42),
        run_name="svm-baseline",
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
        ctx=ctx,
        store=store,
    )

    # ---- Run B: Random Forest ----
    rf_run_ref = f"run:{PROJECT_NAME}.rf-experiment"
    print("\nTraining Run B: rf-experiment ...")
    train_and_log(
        model=RandomForestClassifier(n_estimators=100, random_state=42),
        run_name="rf-experiment",
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
        ctx=ctx,
        store=store,
    )

    # ---- Analysis ----
    print("\n--- Analysis ---")

    comparison = ctx.compare_runs(svm_run_ref, rf_run_ref)
    print("\nRun comparison (evaluate stage):")
    for sc in comparison.stage_comparisons:
        if sc.stage_name == "evaluate":
            for d in sc.metric_deltas:
                if d.left_value is not None and d.right_value is not None:
                    print(f"  {d.metric_key:<14} svm={d.left_value:.4f}  rf={d.right_value:.4f}  delta={d.delta:+.4f}")

    best_ref = ctx.select_best_run([svm_run_ref, rf_run_ref], "f1", stage_name="evaluate")
    best_name = best_ref.split(".")[-1] if best_ref else "unknown"
    print(f"\nBest run (f1, evaluate): {best_name}")

    diag = ctx.diagnose_run(best_ref)
    if diag.issues:
        print("\nDiagnostics issues:")
        for issue in diag.issues:
            print(f"  [{issue.severity}] {issue.code}: {issue.summary}")
    else:
        print("\nDiagnostics: no issues found.")

    report = ctx.build_snapshot_report(best_ref)
    print(f"\nSnapshot report: {report.title}")
    for sec in report.sections:
        print(f"  - {sec.title}")

    # ---- Deploy best model ----
    deploy_ref = f"deployment:{PROJECT_NAME}.prod-v1"
    store.deployments.put_deployment_execution(
        DeploymentExecution(
            deployment_execution_ref=deploy_ref,
            project_ref=f"project:{PROJECT_NAME}",
            deployment_name="prod-v1",
            status="completed",
            started_at=_now(),
            ended_at=_now(),
            run_ref=best_ref,
            order_index=0,
        )
    )
    print(f"\nDeployment 'prod-v1' registered for run: {best_name}")

    store.close()


if __name__ == "__main__":
    main()
