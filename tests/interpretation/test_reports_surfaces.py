"""TST-019: report builder, HTML render, CSV export tests."""

from __future__ import annotations

import csv
import io

import pytest

from contexta.interpretation.diagnostics.service import DiagnosticsService
from contexta.interpretation.query.service import QueryService
from contexta.interpretation.reports.builder import ReportBuilder
from contexta.interpretation.reports.models import ReportDocument, ReportSection
from contexta.interpretation.query.models import EvidenceLink


# ---------------------------------------------------------------------------
# ReportDocument model
# ---------------------------------------------------------------------------

class TestReportDocument:
    def test_minimal_valid(self):
        doc = ReportDocument(
            title="My Report",
            sections=(
                ReportSection(title="Summary", body="Run completed."),
            ),
        )
        assert doc.title == "My Report"
        assert len(doc.sections) == 1

    def test_to_json(self):
        doc = ReportDocument(
            title="Test",
            sections=(ReportSection(title="S1", body="Body"),),
        )
        j = doc.to_json()
        assert j["title"] == "Test"
        assert len(j["sections"]) == 1

    def test_to_markdown(self):
        doc = ReportDocument(
            title="Report",
            sections=(ReportSection(title="Section A", body="Details here."),),
        )
        md = doc.to_markdown()
        assert "# Report" in md
        assert "## Section A" in md
        assert "Details here." in md

    def test_to_html(self):
        doc = ReportDocument(
            title="HTML Report",
            sections=(ReportSection(title="A", body="<script>xss</script>"),),
        )
        html = doc.to_html()
        assert "<article>" in html
        assert "<h1>HTML Report</h1>" in html
        assert "<script>xss</script>" not in html  # should be escaped
        assert "&lt;script&gt;" in html

    def test_to_html_with_evidence_links(self):
        doc = ReportDocument(
            title="R",
            sections=(
                ReportSection(
                    title="S",
                    body="body",
                    evidence_links=(EvidenceLink(kind="run", ref="run:proj.r1", label="R1"),),
                ),
            ),
        )
        html = doc.to_html()
        assert "R1" in html
        assert "<ul>" in html

    def test_sections_immutable_tuple(self):
        doc = ReportDocument(title="X", sections=[])  # type: ignore[arg-type]
        assert isinstance(doc.sections, tuple)


# ---------------------------------------------------------------------------
# ReportSection
# ---------------------------------------------------------------------------

class TestReportSection:
    def test_title_stripped(self):
        s = ReportSection(title="  Title  ", body="body")
        assert s.title == "Title"

    def test_body_stripped(self):
        s = ReportSection(title="T", body="  text  ")
        assert s.body == "text"

    def test_to_dict(self):
        s = ReportSection(title="T", body="B")
        d = s.to_dict()
        assert d["title"] == "T"
        assert d["body"] == "B"
        assert "evidence_links" in d


# ---------------------------------------------------------------------------
# ReportBuilder
# ---------------------------------------------------------------------------

class TestReportBuilder:
    def test_build_snapshot_report(self, mock_repo):
        query_svc = QueryService(mock_repo)
        diagnostics_svc = DiagnosticsService(query_svc)
        builder = ReportBuilder()

        snapshot = query_svc.get_run_snapshot("my-proj.run-01")
        diagnostics = diagnostics_svc.diagnose_run("my-proj.run-01")
        doc = builder.build_snapshot_report(snapshot, diagnostics)
        assert doc is not None
        assert isinstance(doc, ReportDocument)
        assert doc.title != ""

    def test_build_snapshot_report_has_sections(self, mock_repo):
        query_svc = QueryService(mock_repo)
        diagnostics_svc = DiagnosticsService(query_svc)
        builder = ReportBuilder()

        snapshot = query_svc.get_run_snapshot("my-proj.run-01")
        diagnostics = diagnostics_svc.diagnose_run("my-proj.run-01")
        doc = builder.build_snapshot_report(snapshot, diagnostics)
        assert len(doc.sections) >= 1

    def test_build_run_report(self, mock_repo):
        from contexta.interpretation.compare.service import CompareService
        query_svc = QueryService(mock_repo)
        diagnostics_svc = DiagnosticsService(query_svc)
        compare_svc = CompareService(query_svc)
        builder = ReportBuilder()

        comparison = compare_svc.compare_runs("my-proj.run-01", "my-proj.run-02")
        diagnostics = diagnostics_svc.diagnose_run("my-proj.run-01")
        doc = builder.build_run_report(comparison, diagnostics)
        assert doc is not None
        assert isinstance(doc, ReportDocument)

    def test_build_project_summary_report(self, mock_repo):
        builder = ReportBuilder()
        from contexta.interpretation.repositories import RunRecord
        runs = tuple(
            RunRecord(run_id=f"my-proj.run-0{i}", project_name="my-proj", name=f"Run {i}", status="completed")
            for i in range(3)
        )
        doc = builder.build_project_summary_report("my-proj", runs=runs)
        assert doc is not None

    def test_build_trend_report(self, mock_repo):
        from contexta.interpretation.trend.service import TrendService
        query_svc = QueryService(mock_repo)
        trend_svc = TrendService(query_svc)
        builder = ReportBuilder()
        trend = trend_svc.get_metric_trend("loss", project_name="my-proj")
        doc = builder.build_trend_report(trend)
        assert doc is not None


# ---------------------------------------------------------------------------
# HTML renderer smoke tests
# ---------------------------------------------------------------------------

def _make_ctx_with_repo(mock_repo, tmp_path):
    """Create a Contexta instance with the mock repository injected."""
    from contexta.api.client import Contexta
    from contexta.config.models import UnifiedConfig, WorkspaceConfig
    from contexta.interpretation.query.service import QueryService

    config = UnifiedConfig(
        project_name="my-proj",
        workspace=WorkspaceConfig(root_path=tmp_path / ".contexta"),
    )
    ctx = Contexta(config=config)
    ctx._repository = mock_repo
    ctx._query_service = QueryService(mock_repo)
    return ctx


class TestHtmlRendererSmoke:
    def test_render_run_list_html(self, mock_repo, tmp_path):
        """Smoke test that the HTML renderer produces output with key section IDs."""
        from contexta.surfaces.html.renderer import render_html_run_list

        ctx = _make_ctx_with_repo(mock_repo, tmp_path)
        html = render_html_run_list(ctx)
        assert "runs-table" in html
        assert "run-list-summary" in html


# ---------------------------------------------------------------------------
# CSV export smoke tests
# ---------------------------------------------------------------------------

class TestCsvExportSmoke:
    def test_export_run_list_csv(self, mock_repo, tmp_path):
        from contexta.surfaces.export.csv import export_run_list_csv

        ctx = _make_ctx_with_repo(mock_repo, tmp_path)
        csv_output = export_run_list_csv(ctx)
        assert csv_output is not None
        reader = csv.DictReader(io.StringIO(csv_output))
        rows = list(reader)
        assert len(rows) >= 1
        assert "run_id" in reader.fieldnames
        assert "status" in reader.fieldnames

    def test_export_trend_csv(self, mock_repo, tmp_path):
        from contexta.surfaces.export.csv import export_trend_csv

        ctx = _make_ctx_with_repo(mock_repo, tmp_path)
        csv_output = export_trend_csv(ctx, "loss", project_name="my-proj")
        assert csv_output is not None
        assert "metric_key" in csv_output or "run_id" in csv_output


# ---------------------------------------------------------------------------
# EXT-017: ReportBuilder batch/deployment/sample sections
# ---------------------------------------------------------------------------

class TestReportBuilderExtendedSections:
    def test_snapshot_report_has_batches_section(self, mock_repo):
        from contexta.interpretation.query.service import QueryService
        from contexta.interpretation.diagnostics.service import DiagnosticsService
        from contexta.interpretation.reports.builder import ReportBuilder
        query_svc = QueryService(mock_repo)
        snapshot = query_svc.get_run_snapshot("my-proj.run-01")
        diagnostics = DiagnosticsService(query_svc).diagnose_run("my-proj.run-01")
        doc = ReportBuilder().build_snapshot_report(snapshot, diagnostics)
        titles = {section.title for section in doc.sections}
        assert "Batches" in titles

    def test_snapshot_report_has_deployments_section(self, mock_repo):
        from contexta.interpretation.query.service import QueryService
        from contexta.interpretation.diagnostics.service import DiagnosticsService
        from contexta.interpretation.reports.builder import ReportBuilder
        query_svc = QueryService(mock_repo)
        snapshot = query_svc.get_run_snapshot("my-proj.run-01")
        diagnostics = DiagnosticsService(query_svc).diagnose_run("my-proj.run-01")
        doc = ReportBuilder().build_snapshot_report(snapshot, diagnostics)
        titles = {section.title for section in doc.sections}
        assert "Deployments" in titles

    def test_snapshot_report_has_samples_section(self, mock_repo):
        from contexta.interpretation.query.service import QueryService
        from contexta.interpretation.diagnostics.service import DiagnosticsService
        from contexta.interpretation.reports.builder import ReportBuilder
        query_svc = QueryService(mock_repo)
        snapshot = query_svc.get_run_snapshot("my-proj.run-01")
        diagnostics = DiagnosticsService(query_svc).diagnose_run("my-proj.run-01")
        doc = ReportBuilder().build_snapshot_report(snapshot, diagnostics)
        titles = {section.title for section in doc.sections}
        assert "Samples" in titles

    def test_batches_section_lists_batch_names(self, mock_repo):
        from contexta.interpretation.query.service import QueryService
        from contexta.interpretation.diagnostics.service import DiagnosticsService
        from contexta.interpretation.reports.builder import ReportBuilder
        query_svc = QueryService(mock_repo)
        snapshot = query_svc.get_run_snapshot("my-proj.run-01")
        diagnostics = DiagnosticsService(query_svc).diagnose_run("my-proj.run-01")
        doc = ReportBuilder().build_snapshot_report(snapshot, diagnostics)
        batch_section = next(s for s in doc.sections if s.title == "Batches")
        if snapshot.batches:
            assert snapshot.batches[0].name in batch_section.body
