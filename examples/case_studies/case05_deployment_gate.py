"""Case Study 05 — Automated Deployment Gate
Persona: MLOps Engineer / Forward Deployed Engineer

THE SITUATION
=============
The team deploys models via a Slack checklist thread: "Did you check metrics?
Did you compare with previous version? Did you validate the data?" People
reply "yes" and the team lead approves. After Case 04's CTR incident (a model
slipped through with a different dataset version), the team lead decided this
manual process is not reliable.

Three deployment failures in the past quarter:
- March: deployed with evaluation metrics from the wrong stage
- April: deployed run-c with dataset v2025-03-31 (caused CTR drop — Case 04)
- May: no metrics at all in the run (evaluate stage was skipped)

This demo shows how a programmatic pre-deployment gate replaces the Slack
checklist — it checks diagnostics, required metrics, and regression against
the previous deployment automatically.
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    DeploymentExecution,
    MetricPayload,
    MetricRecord,
    Project,
    RecordEnvelope,
    Run,
    StageExecution,
)

PROJECT_NAME = "product-ranker"
REQUIRED_METRICS = ["accuracy", "auc", "f1"]
REGRESSION_THRESHOLD = 0.02   # allow at most 2% drop vs previous deploy
_rid = 0


def _next_rid() -> str:
    global _rid
    _rid += 1
    return f"r{_rid:04d}"


def _make_run(
    store: Any,
    record_store: Any,
    run_name: str,
    accuracy: float,
    auc: float,
    f1: float,
    has_evaluate_stage: bool = True,
    started_at: str = "2025-05-01T09:00:00Z",
    ended_at: str = "2025-05-01T11:00:00Z",
) -> str:
    run_ref = f"run:{PROJECT_NAME}.{run_name}"
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
    stage_ref = f"stage:{PROJECT_NAME}.{run_name}.evaluate"
    if has_evaluate_stage:
        store.stages.put_stage_execution(
            StageExecution(
                stage_execution_ref=stage_ref,
                run_ref=run_ref,
                stage_name="evaluate",
                status="completed",
                started_at=started_at,
                ended_at=ended_at,
                order_index=0,
            )
        )
        for key, val in [("accuracy", accuracy), ("auc", auc), ("f1", f1)]:
            record_store.append(
                MetricRecord(
                    envelope=RecordEnvelope(
                        record_ref=f"record:{PROJECT_NAME}.{run_name}.{_next_rid()}",
                        record_type="metric",
                        recorded_at=ended_at,
                        observed_at=ended_at,
                        producer_ref="contexta.case05",
                        run_ref=run_ref,
                        stage_execution_ref=stage_ref,
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
    return run_ref


@dataclass
class GateResult:
    passed: bool
    run_id: str
    checks: list[tuple[str, bool, str]]   # (check_name, passed, detail)

    def print_report(self) -> None:
        status = "PASS" if self.passed else "FAIL"
        print(f"\n  Pre-deployment gate for '{self.run_id}': [{status}]")
        for name, ok, detail in self.checks:
            icon = "  [OK]  " if ok else "  [NG]  "
            print(f"    {icon}  [{name}] {detail}")


def pre_deployment_gate(ctx: Contexta, candidate_run_id: str, previous_deploy_run_id: str | None) -> GateResult:
    """Run all pre-deployment checks programmatically."""
    checks: list[tuple[str, bool, str]] = []

    # --- Check 1: no error-level diagnostics ---
    diag = ctx.diagnose_run(candidate_run_id)
    errors = [i for i in diag.issues if i.severity == "error"]
    warnings = [i for i in diag.issues if i.severity == "warning"]
    if errors:
        checks.append(("diagnostics", False,
                        f"{len(errors)} error(s): {', '.join(i.code for i in errors)}"))
    else:
        checks.append(("diagnostics", True,
                        f"clean ({len(warnings)} warning(s))"))

    # --- Check 2: all required metrics present ---
    snapshot = ctx.get_run_snapshot(candidate_run_id)
    obs_keys = {o.key for o in snapshot.records if o.record_type == "metric"}
    missing = [m for m in REQUIRED_METRICS if m not in obs_keys]
    if missing:
        checks.append(("required_metrics", False,
                        f"missing: {missing}"))
    else:
        vals = {o.key: o.value for o in snapshot.records if o.record_type == "metric"}
        summary = ", ".join(f"{k}={vals[k]:.4f}" for k in REQUIRED_METRICS if k in vals)
        checks.append(("required_metrics", True, summary))

    # --- Check 3: no regression vs previous deployment ---
    if previous_deploy_run_id is not None:
        comparison = ctx.compare_runs(previous_deploy_run_id, candidate_run_id)
        regressions = []
        for sc in comparison.stage_comparisons:
            for delta in sc.metric_deltas:
                if delta.metric_key in REQUIRED_METRICS and delta.left_value is not None and delta.right_value is not None:
                    # positive change_ratio means right < left (regression for higher-is-better)
                    change = (delta.right_value - delta.left_value) / max(abs(delta.left_value), 1e-9)
                    if change < -REGRESSION_THRESHOLD:
                        regressions.append(
                            f"{delta.metric_key}: {delta.left_value:.4f}->{delta.right_value:.4f} ({change:+.1%})"
                        )
        if regressions:
            checks.append(("regression_check", False,
                            f"regression detected: {'; '.join(regressions)}"))
        else:
            checks.append(("regression_check", True,
                            f"no significant regression vs previous deploy (threshold={REGRESSION_THRESHOLD:.0%})"))
    else:
        checks.append(("regression_check", True, "no previous deployment — skipped"))

    passed = all(ok for _, ok, _ in checks)
    return GateResult(passed=passed, run_id=candidate_run_id, checks=checks)


def run_example(workspace: Path | str | None = None) -> dict[str, Any]:
    if workspace is None:
        workspace = Path(tempfile.mkdtemp(prefix="contexta-case05-")) / ".contexta"

    ctx = Contexta(
        config=UnifiedConfig(
            project_name=PROJECT_NAME,
            workspace=WorkspaceConfig(root_path=Path(workspace)),
        )
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

        # ── Scenario A: safe baseline (previous production model) ────────────
        prev_run_ref = _make_run(
            store, ctx.record_store, "baseline-v1",
            accuracy=0.893, auc=0.927, f1=0.881,
            started_at="2025-04-28T09:00:00Z",
            ended_at="2025-04-28T11:00:00Z",
        )
        store.deployments.put_deployment_execution(
            DeploymentExecution(
                deployment_execution_ref=f"deployment:{PROJECT_NAME}.prod-v1",
                project_ref=f"project:{PROJECT_NAME}",
                deployment_name="prod-v1",
                status="completed",
                started_at="2025-04-28T12:00:00Z",
                ended_at="2025-04-28T12:10:00Z",
                run_ref=prev_run_ref,
                order_index=0,
            )
        )

        print("=" * 60)
        print("CASE STUDY 05: Automated Deployment Gate")
        print("=" * 60)
        print()
        # ── Scenario B: GOOD candidate — should pass ────────────────────────
        print("── Scenario B: Good candidate (slight improvement) ──")
        good_run_ref = _make_run(
            store, ctx.record_store, "candidate-v2-good",
            accuracy=0.901, auc=0.933, f1=0.889,
            started_at="2025-05-05T09:00:00Z",
            ended_at="2025-05-05T11:00:00Z",
        )
        gate_good = pre_deployment_gate(ctx, good_run_ref, prev_run_ref)
        gate_good.print_report()

        # ── Scenario C: MISSING METRICS — should fail ───────────────────────
        print()
        print("── Scenario C: Evaluate stage was skipped (May incident replay) ──")
        no_eval_run_ref = _make_run(
            store, ctx.record_store, "candidate-v3-no-eval",
            accuracy=0.0, auc=0.0, f1=0.0,
            has_evaluate_stage=False,
            started_at="2025-05-06T09:00:00Z",
            ended_at="2025-05-06T11:00:00Z",
        )
        gate_no_eval = pre_deployment_gate(ctx, no_eval_run_ref, prev_run_ref)
        gate_no_eval.print_report()

        # ── Scenario D: REGRESSION — accuracy dropped 5% ────────────────────
        print()
        print("── Scenario D: Regression candidate (accuracy -5%) ──")
        regressed_run_ref = _make_run(
            store, ctx.record_store, "candidate-v4-regressed",
            accuracy=0.841, auc=0.891, f1=0.859,
            started_at="2025-05-07T09:00:00Z",
            ended_at="2025-05-07T11:00:00Z",
        )
        gate_regressed = pre_deployment_gate(ctx, regressed_run_ref, prev_run_ref)
        gate_regressed.print_report()

        print()
        print("Gate results summary:")
        results = [
            ("candidate-v2-good",      gate_good.passed),
            ("candidate-v3-no-eval",   gate_no_eval.passed),
            ("candidate-v4-regressed", gate_regressed.passed),
        ]
        for name, ok in results:
            print(f"  {'PASS' if ok else 'FAIL'}  {name}")

        return {
            "good_passed": gate_good.passed,
            "no_eval_passed": gate_no_eval.passed,
            "regressed_passed": gate_regressed.passed,
        }

    finally:
        store.close()


def main() -> None:
    run_example()


if __name__ == "__main__":
    main()
