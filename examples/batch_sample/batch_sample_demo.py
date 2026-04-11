"""Batch, Sample, and Deployment demo for Contexta.

Demonstrates:
- Creating a run with a training stage
- Logging multiple batch executions across two epochs
- Attaching sample observations to a batch
- Registering a deployment execution linked to the run
- Querying batches, samples, and deployments via ctx API
- Building a snapshot report that includes all three sections
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    BatchExecution,
    DeploymentExecution,
    MetricPayload,
    MetricRecord,
    Project,
    RecordEnvelope,
    Run,
    SampleObservation,
    StageExecution,
)


PROJECT_NAME = "batch-demo"
RUN_NAME = "run-01"
RUN_REF = f"run:{PROJECT_NAME}.{RUN_NAME}"
STAGE_REF = f"stage:{PROJECT_NAME}.{RUN_NAME}.train"


def _put_metric(ctx: Contexta, key: str, value: float, idx: int) -> None:
    ctx.record_store.append(
        MetricRecord(
            envelope=RecordEnvelope(
                record_ref=f"record:{PROJECT_NAME}.{RUN_NAME}.m{idx:04d}",
                record_type="metric",
                recorded_at="2025-01-01T00:03:00Z",
                observed_at="2025-01-01T00:03:00Z",
                producer_ref="contexta.batch-demo",
                run_ref=RUN_REF,
                completeness_marker="complete",
                degradation_marker="none",
            ),
            payload=MetricPayload(
                metric_key=key,
                value=value,
                value_type="float64",
            ),
        )
    )


def run_example(workspace: Path | str | None = None) -> dict[str, Any]:
    if workspace is None:
        workspace = Path(tempfile.mkdtemp(prefix="contexta-batch-")) / ".contexta"

    ctx = Contexta(
        config=UnifiedConfig(
            project_name=PROJECT_NAME,
            workspace=WorkspaceConfig(root_path=Path(workspace)),
        )
    )
    store = ctx.metadata_store

    try:
        # --- Project / Run / Stage ---
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
                ended_at="2025-01-01T00:10:00Z",
            )
        )
        store.stages.put_stage_execution(
            StageExecution(
                stage_execution_ref=STAGE_REF,
                run_ref=RUN_REF,
                stage_name="train",
                status="completed",
                started_at="2025-01-01T00:01:00Z",
                ended_at="2025-01-01T00:09:00Z",
                order_index=0,
            )
        )

        # --- Batch executions (two epochs) ---
        for epoch in range(2):
            batch_ref = f"batch:{PROJECT_NAME}.{RUN_NAME}.train.epoch-{epoch}"
            store.batches.put_batch_execution(
                BatchExecution(
                    batch_execution_ref=batch_ref,
                    run_ref=RUN_REF,
                    stage_execution_ref=STAGE_REF,
                    batch_name=f"epoch-{epoch}",
                    status="completed",
                    started_at=f"2025-01-01T00:0{epoch + 1}:00Z",
                    ended_at=f"2025-01-01T00:0{epoch + 2}:00Z",
                    order_index=epoch,
                )
            )

            # Attach sample observations to each batch (batch-scoped: use stage ref for 4-component sample)
            for s in range(3):
                sample_name = f"s{epoch}-{s:03d}"
                store.samples.put_sample_observation(
                    SampleObservation(
                        sample_observation_ref=f"sample:{PROJECT_NAME}.{RUN_NAME}.train.{sample_name}",
                        run_ref=RUN_REF,
                        stage_execution_ref=STAGE_REF,
                        sample_name=sample_name,
                        observed_at=f"2025-01-01T00:0{epoch + 1}:30Z",
                    )
                )

        # --- Metrics ---
        _put_metric(ctx, "loss", 0.52, 0)
        _put_metric(ctx, "loss", 0.38, 1)
        _put_metric(ctx, "accuracy", 0.81, 2)
        _put_metric(ctx, "accuracy", 0.89, 3)

        # --- Deployment linked to this run ---
        store.deployments.put_deployment_execution(
            DeploymentExecution(
                deployment_execution_ref=f"deployment:{PROJECT_NAME}.model-v1",
                project_ref=f"project:{PROJECT_NAME}",
                deployment_name="model-v1",
                status="completed",
                started_at="2025-01-01T00:09:30Z",
                ended_at="2025-01-01T00:10:00Z",
                run_ref=RUN_REF,
            )
        )

        # --- Query ---
        batches = ctx.list_batches(RUN_REF)
        samples = ctx.list_samples(RUN_REF)
        deployments = ctx.list_deployments(PROJECT_NAME)
        snapshot = ctx.get_run_snapshot(RUN_REF)
        report = ctx.build_snapshot_report(RUN_REF)

        return {
            "workspace": str(workspace),
            "run_ref": RUN_REF,
            "batch_count": len(batches),
            "sample_count": len(samples),
            "deployment_count": len(deployments),
            "snapshot_batch_count": len(snapshot.batches),
            "snapshot_deployment_count": len(snapshot.deployments),
            "report_sections": [s.title for s in report.sections],
        }

    finally:
        store.close()


def main() -> None:
    result = run_example()

    print(f"Workspace:           {result['workspace']}")
    print(f"Run ref:             {result['run_ref']}")
    print(f"Batches logged:      {result['batch_count']}")
    print(f"Samples logged:      {result['sample_count']}")
    print(f"Deployments:         {result['deployment_count']}")
    print(f"Snapshot batches:    {result['snapshot_batch_count']}")
    print(f"Snapshot deploys:    {result['snapshot_deployment_count']}")
    print(f"Report sections:     {', '.join(result['report_sections'])}")


if __name__ == "__main__":
    main()
