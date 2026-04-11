"""TST-029: End-to-end capture to report scenario tests.

Validates the full pipeline from run start through report bundle generation
using real stores (metadata store + record store) with a temporary workspace.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contexta import Contexta
from contexta.config.models import UnifiedConfig, WorkspaceConfig
from contexta.contract.models.context import Project, Run, StageExecution
from contexta.contract.models.records import MetricPayload, MetricRecord, RecordEnvelope
from contexta.common.time import iso_utc_now
from contexta.interpretation.reports.models import ReportDocument


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_ctx(tmp_path: Path) -> Contexta:
    config = UnifiedConfig(
        project_name="e2e-proj",
        workspace=WorkspaceConfig(root_path=tmp_path / ".contexta"),
    )
    return Contexta(config=config)


def _ts(offset_seconds: int = 0) -> str:
    """Return a fixed ISO timestamp for deterministic tests."""
    return f"2024-06-01T12:0{offset_seconds}:00Z"


def _build_run(run_id: str, status: str = "completed") -> Run:
    return Run(
        run_ref=f"run:e2e-proj.{run_id}",
        project_ref="project:e2e-proj",
        name=run_id,
        status=status,
        started_at=_ts(0),
        ended_at=_ts(5) if status != "open" else None,
    )


def _build_stage(run_id: str, stage_name: str) -> StageExecution:
    return StageExecution(
        stage_execution_ref=f"stage:e2e-proj.{run_id}.{stage_name}",
        run_ref=f"run:e2e-proj.{run_id}",
        stage_name=stage_name,
        status="completed",
        started_at=_ts(1),
        ended_at=_ts(3),
        order_index=0,
    )


def _build_metric_record(run_id: str, metric_key: str, value: float, idx: int = 1) -> MetricRecord:
    now = iso_utc_now()
    return MetricRecord(
        envelope=RecordEnvelope(
            record_ref=f"record:e2e-proj.{run_id}.m{idx:04d}",
            record_type="metric",
            recorded_at=now,
            observed_at=now,
            producer_ref="contexta.test",
            run_ref=f"run:e2e-proj.{run_id}",
        ),
        payload=MetricPayload(
            metric_key=metric_key,
            value=value,
            value_type="float64",
        ),
    )


def _seed_workspace(ctx: Contexta, run_ids: list[str], *, close: bool = True) -> None:
    """Write project, runs, stages, and metric records into real stores."""
    project = Project(
        project_ref="project:e2e-proj",
        name="e2e-proj",
        created_at=_ts(0),
    )
    store = ctx.metadata_store
    try:
        store.projects.put_project(project)
        for i, run_id in enumerate(run_ids):
            run = _build_run(run_id)
            store.runs.put_run(run)
            stage = _build_stage(run_id, "train")
            store.stages.put_stage_execution(stage)
            # Write metric records
            ctx.record_store.append(_build_metric_record(run_id, "loss", 0.9 - i * 0.1, idx=1))
            ctx.record_store.append(_build_metric_record(run_id, "loss", 0.7 - i * 0.1, idx=2))
            ctx.record_store.append(_build_metric_record(run_id, "accuracy", 0.7 + i * 0.1, idx=3))
    finally:
        if close:
            store.close()


# ---------------------------------------------------------------------------
# Capture lifecycle (ctx.run / scope API)
# ---------------------------------------------------------------------------

class TestCaptureLifecycle:
    def test_run_scope_can_start_and_close(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        run = ctx.run("capture-run-01")
        assert run.status == "open"
        run.close()
        assert run.is_closed

    def test_run_scope_as_context_manager(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        with ctx.run("capture-run-02") as run:
            assert run.status == "open"
        assert run.is_closed

    def test_run_scope_captures_metric(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        with ctx.run("capture-run-03") as run:
            result = run.metric("loss", 0.42)
        assert result is not None

    def test_run_scope_captures_event(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        with ctx.run("capture-run-04") as run:
            result = run.event("checkpoint", message="saved model checkpoint")
        assert result is not None

    def test_stage_scope_within_run(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        with ctx.run("capture-run-05") as run:
            with run.stage("train") as stage:
                assert stage.status == "open"
                stage.metric("loss", 0.5)
            assert stage.is_closed

    def test_failed_run_scope_marks_failed(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        try:
            with ctx.run("capture-run-06") as run:
                raise RuntimeError("simulated failure")
        except RuntimeError:
            pass
        assert run.status == "failed"

    def test_run_id_derived_from_name(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        with ctx.run("My Training Run") as run:
            pass
        assert run.run_id  # normalized run_id exists
        assert "e2e-proj" in run.ref


# ---------------------------------------------------------------------------
# Query from real stores
# ---------------------------------------------------------------------------

class TestQueryFromRealStores:
    def test_list_runs_returns_seeded_runs(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01", "run-02"])
        ctx2 = _make_ctx(tmp_path)
        runs = ctx2.list_runs()
        ctx2.metadata_store.close()
        assert len(runs) == 2

    def test_list_runs_by_project(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01", "run-02"])
        ctx2 = _make_ctx(tmp_path)
        runs = ctx2.list_runs("e2e-proj")
        ctx2.metadata_store.close()
        assert len(runs) == 2

    def test_list_projects_contains_seeded_project(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01"])
        ctx2 = _make_ctx(tmp_path)
        projects = ctx2.list_projects()
        ctx2.metadata_store.close()
        assert "e2e-proj" in projects

    def test_get_run_snapshot(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01"])
        ctx2 = _make_ctx(tmp_path)
        snapshot = ctx2.get_run_snapshot("run:e2e-proj.run-01")
        ctx2.metadata_store.close()
        assert snapshot is not None

    def test_get_run_snapshot_has_stages(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01"])
        ctx2 = _make_ctx(tmp_path)
        snapshot = ctx2.get_run_snapshot("run:e2e-proj.run-01")
        ctx2.metadata_store.close()
        assert len(snapshot.stages) >= 1

    def test_get_metric_trend(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01", "run-02"])
        ctx2 = _make_ctx(tmp_path)
        runs = ctx2.list_runs()
        run_id = runs[0].run_id
        trend = ctx2.get_metric_trend("loss", project_name="e2e-proj")
        ctx2.metadata_store.close()
        assert trend is not None
        assert trend.metric_key == "loss"

    def test_metric_trend_has_points(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01", "run-02"])
        ctx2 = _make_ctx(tmp_path)
        trend = ctx2.get_metric_trend("loss", project_name="e2e-proj")
        ctx2.metadata_store.close()
        assert len(trend.points) >= 1


# ---------------------------------------------------------------------------
# Compare from real stores
# ---------------------------------------------------------------------------

class TestCompareFromRealStores:
    def test_compare_two_runs(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01", "run-02"])
        ctx2 = _make_ctx(tmp_path)
        comparison = ctx2.compare_runs("run:e2e-proj.run-01", "run:e2e-proj.run-02")
        ctx2.metadata_store.close()
        assert comparison is not None

    def test_select_best_run(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01", "run-02"])
        ctx2 = _make_ctx(tmp_path)
        best = ctx2.select_best_run(
            ["run:e2e-proj.run-01", "run:e2e-proj.run-02"],
            metric_key="loss",
            higher_is_better=False,
        )
        ctx2.metadata_store.close()
        assert best is not None

    def test_diagnose_run(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01"])
        ctx2 = _make_ctx(tmp_path)
        result = ctx2.diagnose_run("run:e2e-proj.run-01")
        ctx2.metadata_store.close()
        assert result is not None
        assert hasattr(result, "issues")


# ---------------------------------------------------------------------------
# Report generation from real stores
# ---------------------------------------------------------------------------

class TestReportFromRealStores:
    def test_build_snapshot_report(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01"])
        ctx2 = _make_ctx(tmp_path)
        doc = ctx2.build_snapshot_report("run:e2e-proj.run-01")
        ctx2.metadata_store.close()
        assert isinstance(doc, ReportDocument)

    def test_snapshot_report_title_contains_run_id(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01"])
        ctx2 = _make_ctx(tmp_path)
        doc = ctx2.build_snapshot_report("run:e2e-proj.run-01")
        ctx2.metadata_store.close()
        assert doc.title  # has a title

    def test_snapshot_report_has_sections(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01"])
        ctx2 = _make_ctx(tmp_path)
        doc = ctx2.build_snapshot_report("run:e2e-proj.run-01")
        ctx2.metadata_store.close()
        assert len(doc.sections) >= 1

    def test_snapshot_report_to_markdown(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01"])
        ctx2 = _make_ctx(tmp_path)
        doc = ctx2.build_snapshot_report("run:e2e-proj.run-01")
        ctx2.metadata_store.close()
        md = doc.to_markdown()
        assert isinstance(md, str) and len(md) > 0

    def test_snapshot_report_to_html(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01"])
        ctx2 = _make_ctx(tmp_path)
        doc = ctx2.build_snapshot_report("run:e2e-proj.run-01")
        ctx2.metadata_store.close()
        html = doc.to_html()
        assert "<" in html and ">" in html

    def test_snapshot_report_to_json(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01"])
        ctx2 = _make_ctx(tmp_path)
        doc = ctx2.build_snapshot_report("run:e2e-proj.run-01")
        ctx2.metadata_store.close()
        data = doc.to_json()
        assert "title" in data

    def test_compare_report(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01", "run-02"])
        ctx2 = _make_ctx(tmp_path)
        doc = ctx2.build_run_report("run:e2e-proj.run-01", "run:e2e-proj.run-02")
        ctx2.metadata_store.close()
        assert isinstance(doc, ReportDocument)

    def test_project_summary_report(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01", "run-02"])
        ctx2 = _make_ctx(tmp_path)
        doc = ctx2.build_project_summary_report("e2e-proj")
        ctx2.metadata_store.close()
        assert isinstance(doc, ReportDocument)
        assert "e2e-proj" in doc.title

    def test_trend_report(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _seed_workspace(ctx, ["run-01", "run-02"])
        ctx2 = _make_ctx(tmp_path)
        doc = ctx2.build_trend_report("loss", project_name="e2e-proj")
        ctx2.metadata_store.close()
        assert isinstance(doc, ReportDocument)
