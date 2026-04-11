"""Case Study 12: Delivery Quality Certificate - Tom's Story.

Tom is a Forward Deployed Engineer who delivers trained models to B2B
enterprise clients. His current delivery is a fraud detection model for
FinanceBank Corp, a regulated financial institution.

THE SITUATION
=============
FinanceBank Corp's procurement team has a strict vendor evaluation
process. Before accepting any AI model, they require a signed
"Model Quality Certificate" from the vendor that documents:

  1. What training data version was used?
  2. What are the evaluation metrics (exact numbers, not estimates)?
  3. What was the training environment (Python version, key packages)?
  4. Did the model pass the agreed quality thresholds?
     - accuracy    >= 0.90
     - auc         >= 0.93
     - f1          >= 0.88
     - precision   >= 0.87
     - recall      >= 0.86
  5. An overall PASS or FAIL decision.

Without observability tooling, Tom assembles this document manually from
training logs, requirements.txt, and notebook outputs -- a process that
takes 3-4 hours and is error-prone. If any metric is wrong, the client
returns it for correction, adding days to the timeline.

This demo shows how Tom produces the full quality certificate
programmatically in seconds, with all evidence backed by recorded
observations rather than manual compilation.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

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


PROJECT_NAME = "fraud-detection-financebank"

# Quality thresholds agreed with the client
QUALITY_THRESHOLDS: dict[str, float] = {
    "accuracy":  0.90,
    "auc":       0.93,
    "f1":        0.88,
    "precision": 0.87,
    "recall":    0.86,
}

CLIENT_NAME = "FinanceBank Corp"
MODEL_NAME = "FraudShield v2.1"
DELIVERY_DATE = "2025-04-11"

_REC_COUNTER = 0


def _next_rid() -> str:
    global _REC_COUNTER
    _REC_COUNTER += 1
    return f"r{_REC_COUNTER:05d}"


def run_example(workspace: Path | str | None = None) -> dict[str, Any]:
    """Create one run with full environment snapshot and produce a quality certificate."""

    if workspace is None:
        root = Path(tempfile.mkdtemp(prefix="contexta-case12-"))
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
    print("CASE STUDY 12: Delivery Quality Certificate")
    print("=" * 60)
    print()
    store = ctx.metadata_store
    try:
        store.projects.put_project(
            Project(
                project_ref=f"project:{PROJECT_NAME}",
                name=PROJECT_NAME,
                created_at="2025-03-01T00:00:00Z",
                description=f"Fraud detection model for {CLIENT_NAME}",
            )
        )

        run_name = "fraud-model-v2-1"
        run_ref = f"run:{PROJECT_NAME}.{run_name}"
        started_at = "2025-04-08T09:00:00Z"
        ended_at = "2025-04-08T15:00:00Z"

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

        train_ref = f"stage:{PROJECT_NAME}.{run_name}.train"
        eval_ref = f"stage:{PROJECT_NAME}.{run_name}.evaluate"

        store.stages.put_stage_execution(
            StageExecution(
                stage_execution_ref=train_ref,
                run_ref=run_ref,
                stage_name="train",
                status="completed",
                started_at=started_at,
                ended_at="2025-04-08T13:00:00Z",
                order_index=0,
            )
        )
        store.stages.put_stage_execution(
            StageExecution(
                stage_execution_ref=eval_ref,
                run_ref=run_ref,
                stage_name="evaluate",
                status="completed",
                started_at="2025-04-08T13:00:00Z",
                ended_at=ended_at,
                order_index=1,
            )
        )

        # Evaluation metrics
        eval_metrics: dict[str, float] = {
            "accuracy":  0.934,
            "auc":       0.961,
            "f1":        0.922,
            "precision": 0.917,
            "recall":    0.928,
        }
        record_store = ctx.record_store
        obs_ts = ended_at
        for key, val in eval_metrics.items():
            record_store.append(
                MetricRecord(
                    envelope=RecordEnvelope(
                        record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                        record_type="metric",
                        recorded_at=obs_ts,
                        observed_at=obs_ts,
                        producer_ref="contexta.case12",
                        run_ref=run_ref,
                        stage_execution_ref=eval_ref,
                        completeness_marker="complete",
                        degradation_marker="none",
                    ),
                    payload=MetricPayload(
                        metric_key=key,
                        value=val,
                        value_type="float64",
                    ),
                )
            )

        # Dataset version event (answers client Q1)
        dataset_version = "fraud-transactions-2025q1-v3"
        record_store.append(
            StructuredEventRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                    record_type="event",
                    recorded_at=started_at,
                    observed_at=started_at,
                    producer_ref="contexta.case12",
                    run_ref=run_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=StructuredEventPayload(
                    event_key="training.dataset-registered",
                    level="info",
                    message=f"Training dataset version: {dataset_version}",
                    attributes={
                        "dataset_version": dataset_version,
                        "record_count": 2_400_000,
                        "date_range": "2024-01-01 to 2025-03-31",
                    },
                    origin_marker="explicit_capture",
                ),
            )
        )

        # Environment snapshot (answers client Q3)
        env_packages = {
            "scikit-learn": "1.4.0",
            "xgboost": "2.0.3",
            "pandas": "2.2.1",
            "numpy": "1.26.4",
            "imbalanced-learn": "0.12.0",
            "shap": "0.45.0",
        }
        store.environments.put_environment_snapshot(
            EnvironmentSnapshot(
                environment_snapshot_ref=f"environment:{PROJECT_NAME}.{run_name}.snap",
                run_ref=run_ref,
                captured_at=started_at,
                python_version="3.11.8",
                platform="linux",
                packages=env_packages,
                environment_variables={},
            )
        )

        # ------------------------------------------------------------------
        # Produce the quality certificate
        # ------------------------------------------------------------------


        snap = ctx.get_run_snapshot(run_ref)
        metric_recs = [r for r in snap.records if r.record_type == "metric"]
        event_recs = [r for r in snap.records if r.record_type == "event"]
        audit = ctx.audit_reproducibility(run_ref)

        dataset_event = next(
            (e for e in event_recs if e.key == "training.dataset-registered"), None
        )
        if dataset_event:
            attributes = dataset_event.payload.get("attributes") or {}
            dataset_version_recorded = (
                attributes.get("dataset_version")
                or dataset_event.payload.get("dataset_version")
                or dataset_event.message
            )
        else:
            dataset_version_recorded = "N/A"

        # Check each metric against thresholds
        metric_results: dict[str, tuple[float, float, bool]] = {}
        for key, threshold in QUALITY_THRESHOLDS.items():
            recorded_val = next((r.value for r in metric_recs if r.key == key), None)
            if recorded_val is not None:
                passed = recorded_val >= threshold
                metric_results[key] = (recorded_val, threshold, passed)

        overall_pass = all(passed for _, _, passed in metric_results.values())
        overall_label = "PASS" if overall_pass else "FAIL"

        # Print certificate
        print("=" * 60)
        print("  MODEL QUALITY CERTIFICATE")
        print("=" * 60)
        print(f"  Client:         {CLIENT_NAME}")
        print(f"  Model:          {MODEL_NAME}")
        print(f"  Delivery Date:  {DELIVERY_DATE}")
        print(f"  Run ID:         {run_ref}")
        print()
        print("  TRAINING DATA")
        print(f"  Dataset Version: {dataset_version_recorded}")
        print()
        print("  ENVIRONMENT")
        print(f"  Python:          {audit.python_version}")
        print(f"  Platform:        {audit.platform}")
        print(f"  Packages logged: {audit.package_count}")
        print(f"  Repro Status:    {audit.reproducibility_status}")
        print()
        print("  QUALITY THRESHOLDS")
        print(f"  {'Metric':<14} {'Value':<10} {'Threshold':<12} {'Result'}")
        print("  " + "-" * 46)
        for key in sorted(metric_results.keys()):
            val, threshold, passed = metric_results[key]
            result_label = "PASS" if passed else "FAIL"
            print(f"  {key:<14} {val:<10.4f} {threshold:<12.4f} {result_label}")
        print()
        print(f"  OVERALL RESULT:  {overall_label}")
        print("=" * 60)
        print()

        # build_snapshot_report as the formal audit document
        snapshot_report = ctx.build_snapshot_report(run_ref)
        print(f"Formal snapshot report: '{snapshot_report.title}'")
        print("  Sections:")
        for section in snapshot_report.sections:
            print(f"    - {section.title}")
        print()
        print("Tom's delivery time: 12 seconds (not 3-4 hours).")
        print("All metrics backed by recorded evidence -- no manual compilation.")

        return {
            "client": CLIENT_NAME,
            "model": MODEL_NAME,
            "dataset_version": dataset_version_recorded,
            "python_version": audit.python_version,
            "metrics_checked": len(metric_results),
            "metrics_passed": sum(1 for _, _, p in metric_results.values() if p),
            "overall_result": overall_label,
            "report_title": snapshot_report.title,
        }
    finally:
        store.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Case Study 12: Delivery Quality Certificate")
    parser.add_argument("--workspace", type=Path, default=None)
    args = parser.parse_args()
    run_example(args.workspace)


if __name__ == "__main__":
    main()
