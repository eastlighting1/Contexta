"""MLflowSink demo — requires mlflow.

Install the optional extra first:

    pip install 'contexta[mlflow]'
    # or:
    uv pip install 'contexta[mlflow]'

Then run from the repository root:

    uv run python examples/adapters/mlflow_sink_demo.py

What this demo does:
- Uses an in-memory MLflow tracking store (no server required)
- Captures MetricRecords and a StructuredEventRecord through MLflowSink
- Reads back the logged data from MLflow and prints it to confirm the bridge
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# --- Dependency check (friendly error before deep import) ---
try:
    import mlflow  # noqa: F401
except ImportError:
    print(
        "mlflow is not installed.\n"
        "Install it with:  pip install 'contexta[mlflow]'\n",
        file=sys.stderr,
    )
    sys.exit(1)

import mlflow

from contexta import Contexta
from contexta.adapters.mlflow import MLflowSink
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    MetricPayload,
    MetricRecord,
    Project,
    RecordEnvelope,
    Run,
    StructuredEventPayload,
    StructuredEventRecord,
)


PROJECT_NAME = "mlflow-demo"
RUN_NAME = "run-01"
RUN_REF = f"run:{PROJECT_NAME}.{RUN_NAME}"


def main() -> None:
    workspace = Path(tempfile.mkdtemp(prefix="contexta-mlflow-")) / ".contexta"
    mlflow_dir = Path(tempfile.mkdtemp(prefix="mlflow-"))

    # In-memory tracking (no MLflow server needed)
    mlflow.set_tracking_uri(mlflow_dir.as_uri())
    mlflow.set_experiment(PROJECT_NAME)

    with mlflow.start_run(run_name=RUN_NAME) as mlflow_run:
        mlflow_run_id = mlflow_run.info.run_id

        sink = MLflowSink(run_id=mlflow_run_id, name="mlflow")

        ctx = Contexta(
            config=UnifiedConfig(
                project_name=PROJECT_NAME,
                workspace=WorkspaceConfig(root_path=workspace),
            ),
            sinks=[sink],
        )
        store = ctx.metadata_store

        try:
            store.projects.put_project(
                Project(
                    project_ref=f"project:{PROJECT_NAME}",
                    name=PROJECT_NAME,
                    created_at="2025-01-01T00:00:00Z",
                )
            )
            store.runs.put_run(
                Run(
                    run_ref=RUN_REF,
                    project_ref=f"project:{PROJECT_NAME}",
                    name=RUN_NAME,
                    status="completed",
                    started_at="2025-01-01T00:00:00Z",
                    ended_at="2025-01-01T00:05:00Z",
                )
            )

            # Log metrics across two steps
            for step, (loss, acc) in enumerate([(0.52, 0.81), (0.38, 0.89)]):
                for idx, (key, val) in enumerate(
                    [("loss", loss), ("accuracy", acc)]
                ):
                    ctx.record_store.append(
                        MetricRecord(
                            envelope=RecordEnvelope(
                                record_ref=f"record:{PROJECT_NAME}.{RUN_NAME}.m{step * 2 + idx:04d}",
                                record_type="metric",
                                recorded_at=f"2025-01-01T00:0{step + 1}:00Z",
                                observed_at=f"2025-01-01T00:0{step + 1}:00Z",
                                producer_ref="contexta.mlflow-demo",
                                run_ref=RUN_REF,
                                completeness_marker="complete",
                                degradation_marker="none",
                            ),
                            payload=MetricPayload(
                                metric_key=key,
                                value=val,
                                value_type="float64",
                                tags={"split": "train"},
                            ),
                        )
                    )

            # Log an event as an MLflow tag
            ctx.record_store.append(
                StructuredEventRecord(
                    envelope=RecordEnvelope(
                        record_ref=f"record:{PROJECT_NAME}.{RUN_NAME}.e0001",
                        record_type="event",
                        recorded_at="2025-01-01T00:04:00Z",
                        observed_at="2025-01-01T00:04:00Z",
                        producer_ref="contexta.mlflow-demo",
                        run_ref=RUN_REF,
                        completeness_marker="complete",
                        degradation_marker="none",
                    ),
                    payload=StructuredEventPayload(
                        event_key="training.complete",
                        level="info",
                        message="Training finished — best loss=0.38",
                        origin_marker="explicit_capture",
                    ),
                )
            )

        finally:
            store.close()

    # Read back from MLflow to verify
    client = mlflow.tracking.MlflowClient()
    run_data = client.get_run(mlflow_run_id).data

    loss_history = client.get_metric_history(mlflow_run_id, "loss")
    acc_history = client.get_metric_history(mlflow_run_id, "accuracy")

    print(f"MLflow run id:    {mlflow_run_id}")
    print(f"Loss values:      {[m.value for m in loss_history]}")
    print(f"Accuracy values:  {[m.value for m in acc_history]}")
    print(f"Tags set:")
    for k, v in sorted(run_data.tags.items()):
        if k.startswith("contexta."):
            print(f"  {k} = {v!r}")
    print(f"\nWorkspace:        {workspace}")


if __name__ == "__main__":
    main()
