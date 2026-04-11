"""TST-020: Contexta unified facade public method smoke tests."""

from __future__ import annotations

import pytest

from contexta.interpretation.reports.models import ReportDocument


# ---------------------------------------------------------------------------
# Query methods
# ---------------------------------------------------------------------------

class TestFacadeQuery:
    def test_list_projects(self, ctx_with_repo):
        projects = ctx_with_repo.list_projects()
        assert "my-proj" in projects

    def test_list_runs_all(self, ctx_with_repo):
        runs = ctx_with_repo.list_runs()
        assert len(runs) == 2

    def test_list_runs_by_project(self, ctx_with_repo):
        runs = ctx_with_repo.list_runs("my-proj")
        assert len(runs) == 2

    def test_list_runs_unknown_project(self, ctx_with_repo):
        runs = ctx_with_repo.list_runs("nonexistent")
        assert len(runs) == 0

    def test_list_runs_with_limit(self, ctx_with_repo):
        from contexta.interpretation import RunListQuery
        runs = ctx_with_repo.list_runs(query=RunListQuery(limit=1))
        assert len(runs) == 1

    def test_get_run_snapshot(self, ctx_with_repo):
        snapshot = ctx_with_repo.get_run_snapshot("my-proj.run-01")
        assert snapshot is not None
        assert snapshot.run.run_id == "my-proj.run-01"

    def test_get_run_snapshot_includes_stages(self, ctx_with_repo):
        snapshot = ctx_with_repo.get_run_snapshot("my-proj.run-01")
        assert len(snapshot.stages) >= 1

    def test_get_run_snapshot_includes_deployments(self, ctx_with_repo):
        snapshot = ctx_with_repo.get_run_snapshot("my-proj.run-01")
        assert len(snapshot.deployments) >= 1

    def test_get_run_snapshot_includes_artifacts(self, ctx_with_repo):
        snapshot = ctx_with_repo.get_run_snapshot("my-proj.run-01")
        assert len(snapshot.artifacts) >= 1

    def test_get_run_snapshot_missing_raises(self, ctx_with_repo):
        from contexta.common.errors import InterpretationError
        with pytest.raises(InterpretationError):
            ctx_with_repo.get_run_snapshot("nonexistent.run")


# ---------------------------------------------------------------------------
# Comparison methods
# ---------------------------------------------------------------------------

class TestFacadeCompare:
    def test_compare_runs(self, ctx_with_repo):
        comparison = ctx_with_repo.compare_runs("my-proj.run-01", "my-proj.run-02")
        assert comparison is not None
        assert comparison.left_run_id == "my-proj.run-01"
        assert comparison.right_run_id == "my-proj.run-02"

    def test_compare_runs_has_stage_comparisons(self, ctx_with_repo):
        comparison = ctx_with_repo.compare_runs("my-proj.run-01", "my-proj.run-02")
        assert hasattr(comparison, "stage_comparisons")

    def test_compare_multiple_runs(self, ctx_with_repo):
        result = ctx_with_repo.compare_multiple_runs(["my-proj.run-01", "my-proj.run-02"])
        assert result is not None

    def test_select_best_run(self, ctx_with_repo):
        best = ctx_with_repo.select_best_run(
            ["my-proj.run-01", "my-proj.run-02"],
            metric_key="loss",
            higher_is_better=False,
        )
        assert best is not None
        assert best in ("my-proj.run-01", "my-proj.run-02")


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

class TestFacadeDiagnostics:
    def test_diagnose_run(self, ctx_with_repo):
        result = ctx_with_repo.diagnose_run("my-proj.run-01")
        assert result is not None

    def test_diagnose_run_has_issues(self, ctx_with_repo):
        result = ctx_with_repo.diagnose_run("my-proj.run-01")
        assert hasattr(result, "issues")


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------

class TestFacadeLineage:
    def test_traverse_lineage(self, ctx_with_repo):
        traversal = ctx_with_repo.traverse_lineage("my-proj.run-01")
        assert traversal is not None

    def test_traverse_lineage_with_direction(self, ctx_with_repo):
        traversal = ctx_with_repo.traverse_lineage(
            "artifact:my-proj.run-01.model",
            direction="inbound",
            max_depth=2,
        )
        assert traversal is not None


# ---------------------------------------------------------------------------
# Trend methods
# ---------------------------------------------------------------------------

class TestFacadeTrend:
    def test_get_metric_trend(self, ctx_with_repo):
        trend = ctx_with_repo.get_metric_trend("loss", project_name="my-proj")
        assert trend is not None
        assert trend.metric_key == "loss"

    def test_get_metric_trend_has_points(self, ctx_with_repo):
        trend = ctx_with_repo.get_metric_trend("loss", project_name="my-proj")
        assert len(trend.points) >= 1

    def test_get_step_series(self, ctx_with_repo):
        series = ctx_with_repo.get_step_series("my-proj.run-01", "loss")
        assert series is not None

    def test_get_stage_duration_trend(self, ctx_with_repo):
        trend = ctx_with_repo.get_stage_duration_trend("train", project_name="my-proj")
        assert trend is not None

    def test_get_artifact_size_trend(self, ctx_with_repo):
        trend = ctx_with_repo.get_artifact_size_trend("checkpoint", project_name="my-proj")
        assert trend is not None


# ---------------------------------------------------------------------------
# Report builder methods
# ---------------------------------------------------------------------------

class TestFacadeReports:
    def test_build_snapshot_report(self, ctx_with_repo):
        doc = ctx_with_repo.build_snapshot_report("my-proj.run-01")
        assert isinstance(doc, ReportDocument)
        assert "my-proj.run-01" in doc.title

    def test_build_snapshot_report_has_sections(self, ctx_with_repo):
        doc = ctx_with_repo.build_snapshot_report("my-proj.run-01")
        assert len(doc.sections) >= 1

    def test_build_run_report(self, ctx_with_repo):
        doc = ctx_with_repo.build_run_report("my-proj.run-01", "my-proj.run-02")
        assert isinstance(doc, ReportDocument)

    def test_build_project_summary_report(self, ctx_with_repo):
        doc = ctx_with_repo.build_project_summary_report("my-proj")
        assert isinstance(doc, ReportDocument)
        assert "my-proj" in doc.title

    def test_build_trend_report(self, ctx_with_repo):
        doc = ctx_with_repo.build_trend_report("loss", project_name="my-proj")
        assert isinstance(doc, ReportDocument)

    def test_build_multi_run_report(self, ctx_with_repo):
        doc = ctx_with_repo.build_multi_run_report(["my-proj.run-01", "my-proj.run-02"])
        assert isinstance(doc, ReportDocument)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

class TestFacadeReportRendering:
    def test_snapshot_report_to_markdown(self, ctx_with_repo):
        doc = ctx_with_repo.build_snapshot_report("my-proj.run-01")
        md = doc.to_markdown()
        assert isinstance(md, str)
        assert len(md) > 0

    def test_snapshot_report_to_html(self, ctx_with_repo):
        doc = ctx_with_repo.build_snapshot_report("my-proj.run-01")
        html = doc.to_html()
        assert "<" in html and ">" in html  # contains HTML tags

    def test_snapshot_report_to_json(self, ctx_with_repo):
        doc = ctx_with_repo.build_snapshot_report("my-proj.run-01")
        data = doc.to_json()
        assert isinstance(data, dict)
        assert "title" in data

    def test_snapshot_report_to_csv(self, ctx_with_repo):
        doc = ctx_with_repo.build_snapshot_report("my-proj.run-01")
        csv_text = doc.to_csv()
        assert isinstance(csv_text, str)
