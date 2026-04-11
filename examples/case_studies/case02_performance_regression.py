"""Case Study 02: Silent Performance Regression - James's Story.

James is an MLE responsible for a product-categorization model used in
an e-commerce search pipeline.  Last month the model sat at 0.91 accuracy.
This month, after a routine retrain, it dropped to 0.87.

The problem: the environment was not recorded.  Was it the new PyTorch
version?  A different numpy?  Different Python?  James cannot tell because
nothing was captured.  He has to diff two requirements.txt files manually
- if he can even find the old one.

This demo shows how Contexta's environment snapshot and comparison APIs
surface the exact diff in seconds: torch 2.0.0 -> 2.1.0 and a numpy
version change are immediately visible.
"""

from __future__ import annotations

import tempfile
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
)


PROJECT_NAME = "product-categorization"

_REC_COUNTER = 0


def _next_rid() -> str:
    global _REC_COUNTER
    _REC_COUNTER += 1
    return f"r{_REC_COUNTER:05d}"


def _create_run(
    store: Any,
    record_store: Any,
    project_name: str,
    run_name: str,
    accuracy: float,
    precision: float,
    recall: float,
    started_at: str,
    ended_at: str,
) -> str:
    run_ref   = f"run:{project_name}.{run_name}"
    stage_ref = f"stage:{project_name}.{run_name}.train"

    store.runs.put_run(
        Run(
            run_ref=run_ref,
            project_ref=f"project:{project_name}",
            name=run_name,
            status="completed",
            started_at=started_at,
            ended_at=ended_at,
        )
    )
    store.stages.put_stage_execution(
        StageExecution(
            stage_execution_ref=stage_ref,
            run_ref=run_ref,
            stage_name="train",
            status="completed",
            started_at=started_at,
            ended_at=ended_at,
            order_index=0,
        )
    )

    for key, val in [("accuracy", accuracy), ("precision", precision), ("recall", recall)]:
        record_store.append(
            MetricRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{project_name}.{run_name}.{_next_rid()}",
                    record_type="metric",
                    recorded_at=ended_at,
                    observed_at=ended_at,
                    producer_ref="contexta.case02",
                    run_ref=run_ref,
                    stage_execution_ref=stage_ref,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=MetricPayload(
                    metric_key=key,
                    value=val,
                    value_type="float64",
                    aggregation_scope="run",
                ),
            )
        )

    return run_ref


def _capture_environment(
    store: Any,
    project_name: str,
    run_name: str,
    run_ref: str,
    python_version: str,
    platform: str,
    packages: dict[str, str],
    captured_at: str,
) -> None:
    """Store an environment snapshot linked to the run."""
    if not hasattr(store, "environments"):
        return

    # environment_snapshot_ref must add exactly one component to run_ref
    env_ref = f"environment:{project_name}.{run_name}.snapshot"
    store.environments.put_environment_snapshot(
        EnvironmentSnapshot(
            environment_snapshot_ref=env_ref,
            run_ref=run_ref,
            captured_at=captured_at,
            python_version=python_version,
            platform=platform,
            packages=packages,
            environment_variables={},
        )
    )


def run_example(workspace: Path | str | None = None) -> dict[str, Any]:
    """Create two runs representing last month vs this month, then diff them."""

    if workspace is None:
        root = Path(tempfile.mkdtemp(prefix="contexta-case02-"))
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
    print("CASE STUDY 02: Silent Performance Regression")
    print("=" * 60)
    print()
    store = ctx.metadata_store
    try:
        store.projects.put_project(
            Project(
                project_ref=f"project:{PROJECT_NAME}",
                name=PROJECT_NAME,
                created_at="2025-02-01T00:00:00Z",
                description="E-commerce product categorization model",
            )
        )

        # Last month: stable environment, high accuracy
        last_month_ref = _create_run(
            store,
            ctx.record_store,
            PROJECT_NAME,
            "last-month",
            accuracy=0.91,
            precision=0.893,
            recall=0.908,
            started_at="2025-02-15T08:00:00Z",
            ended_at="2025-02-15T10:30:00Z",
        )
        _capture_environment(
            store,
            PROJECT_NAME,
            "last-month",
            last_month_ref,
            python_version="3.11.0",
            platform="linux",
            packages={
                "torch": "2.0.0",
                "numpy": "1.24.0",
                "scikit-learn": "1.2.2",
                "transformers": "4.28.0",
                "pandas": "1.5.3",
            },
            captured_at="2025-02-15T08:01:00Z",
        )

        # This month: torch bumped, numpy changed, accuracy dropped
        this_month_ref = _create_run(
            store,
            ctx.record_store,
            PROJECT_NAME,
            "this-month",
            accuracy=0.87,
            precision=0.851,
            recall=0.872,
            started_at="2025-03-15T08:00:00Z",
            ended_at="2025-03-15T10:45:00Z",
        )
        _capture_environment(
            store,
            PROJECT_NAME,
            "this-month",
            this_month_ref,
            python_version="3.11.0",
            platform="linux",
            packages={
                "torch": "2.1.0",       # upgraded - potential culprit
                "numpy": "1.26.4",      # also changed
                "scikit-learn": "1.2.2",
                "transformers": "4.28.0",
                "pandas": "1.5.3",
            },
            captured_at="2025-03-15T08:01:00Z",
        )

        # -------------------------------------------------------------------
        # With Contexta: surface the regression in three steps
        # -------------------------------------------------------------------


        # Step 1: metric comparison
        comparison = ctx.compare_runs(last_month_ref, this_month_ref)
        print("Step 1 - Metric comparison (last-month vs this-month):")
        for sc in comparison.stage_comparisons:
            for delta in sc.metric_deltas:
                if delta.left_value is None or delta.right_value is None or delta.delta is None:
                    continue
                direction = "+" if delta.delta >= 0 else ""
                flag = " <-- REGRESSION" if delta.metric_key == "accuracy" and delta.delta < 0 else ""
                ratio_str = f"{delta.change_ratio:+.1%}" if delta.change_ratio is not None else "n/a"
                print(f"  {delta.metric_key:<12} {delta.left_value:.4f} -> {delta.right_value:.4f}  "
                      f"delta={direction}{delta.delta:.4f}  ratio={ratio_str}{flag}")
        print()

        # Step 2: environment diff
        env_diff = ctx.compare_environments(last_month_ref, this_month_ref)
        print("Step 2 - Environment diff:")
        if env_diff.python_version_changed:
            print("  Python version changed!")
        else:
            print("  Python version: unchanged (3.11.0)")
        if env_diff.changed_packages:
            print("  Changed packages (potential root causes):")
            for change in env_diff.changed_packages:
                print(f"    {change.key}: {change.left_value} -> {change.right_value}  <-- investigate")
        else:
            print("  No package changes detected (environment snapshot missing or identical).")
        if env_diff.added_packages:
            print("  Added packages:")
            for change in env_diff.added_packages:
                print(f"    + {change.key}: {change.right_value}")
        print()

        # Step 3: reproducibility audit on the regressed run
        audit = ctx.audit_reproducibility(this_month_ref)
        print("Step 3 - Reproducibility audit for this-month run:")
        print(f"  Status:          {audit.reproducibility_status}")
        print(f"  Python version:  {audit.python_version}")
        print(f"  Platform:        {audit.platform}")
        print(f"  Packages logged: {audit.package_count}")
        print()

        if env_diff.changed_packages:
            suspects = [c.key for c in env_diff.changed_packages]
            print(f"Root cause hypothesis: packages changed - {suspects}")
            print("Next action: pin torch==2.0.0 and re-run to confirm.")
        else:
            print("No environment data found. Record environments to enable root-cause analysis.")

        return {
            "last_month_run_id": last_month_ref,
            "this_month_run_id": this_month_ref,
            "accuracy_delta": round(0.87 - 0.91, 4),
            "changed_packages": [c.key for c in env_diff.changed_packages],
            "python_version_changed": env_diff.python_version_changed,
            "reproducibility_status": audit.reproducibility_status,
        }
    finally:
        store.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Case Study 02: Performance Regression")
    parser.add_argument("--workspace", type=Path, default=None)
    args = parser.parse_args()
    run_example(args.workspace)


if __name__ == "__main__":
    main()
