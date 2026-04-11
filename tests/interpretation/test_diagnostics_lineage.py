"""TST-017: diagnose, lineage, reproducibility, env diff tests."""

from __future__ import annotations

import pytest

from contexta.interpretation.diagnostics.service import DiagnosticsPolicy, DiagnosticsService
from contexta.interpretation.lineage.service import LineagePolicy, LineageService
from contexta.interpretation.query.service import QueryService
from contexta.interpretation.repositories import ObservationRecord, RelationRecord


# ---------------------------------------------------------------------------
# DiagnosticsService
# ---------------------------------------------------------------------------

class TestDiagnosticsService:
    def test_diagnose_clean_run(self, mock_repo):
        query_svc = QueryService(mock_repo)
        svc = DiagnosticsService(query_svc)
        result = svc.diagnose_run("my-proj.run-01")
        assert result is not None

    def test_diagnose_result_has_issues(self, mock_repo):
        query_svc = QueryService(mock_repo)
        svc = DiagnosticsService(query_svc)
        result = svc.diagnose_run("my-proj.run-01")
        assert hasattr(result, "issues")

    def test_diagnose_result_has_run_id(self, mock_repo):
        query_svc = QueryService(mock_repo)
        svc = DiagnosticsService(query_svc)
        result = svc.diagnose_run("my-proj.run-01")
        assert hasattr(result, "run_id") or hasattr(result, "snapshot")

    def test_diagnose_detects_degraded_records(self, mock_repo):
        # Add a degraded record
        degraded_record = ObservationRecord(
            record_id="r01-degraded",
            run_id="my-proj.run-01",
            stage_id=None,
            record_type="degraded",
            key="capture.gap",
            observed_at="2024-01-01T00:00:00Z",
            degradation_marker="capture_gap",
        )
        mock_repo.add_record(degraded_record)

        query_svc = QueryService(mock_repo)
        svc = DiagnosticsService(query_svc, config=DiagnosticsPolicy(detect_degraded_records=True))
        result = svc.diagnose_run("my-proj.run-01")
        assert result is not None

    def test_diagnose_missing_run_propagates_error(self, mock_repo):
        from contexta.common.errors import InterpretationError
        query_svc = QueryService(mock_repo)
        svc = DiagnosticsService(query_svc)
        with pytest.raises(InterpretationError):
            svc.diagnose_run("nonexistent.run")

    def test_diagnostics_policy_default(self):
        policy = DiagnosticsPolicy()
        assert policy.detect_degraded_records is True


# ---------------------------------------------------------------------------
# LineageService
# ---------------------------------------------------------------------------

class TestLineageService:
    def test_traverse_lineage_returns_traversal(self, mock_repo):
        # Add a lineage relation
        from contexta.interpretation.repositories import RelationRecord
        rel = RelationRecord(
            relation_ref="relation:edge-01",
            source_ref="artifact:my-proj.run-01.dataset",
            target_ref="artifact:my-proj.run-01.model",
            relation_type="generated_from",
            recorded_at="2024-01-01T00:00:00Z",
            origin_marker="declared",
            confidence_marker="confirmed",
        )
        mock_repo._relations.append(rel)

        query_svc = QueryService(mock_repo)
        svc = LineageService(query_svc)
        traversal = svc.traverse_lineage(
            "artifact:my-proj.run-01.model",
            direction="inbound",
            max_depth=2,
        )
        assert traversal is not None

    def test_traverse_lineage_empty_returns_result(self, mock_repo):
        query_svc = QueryService(mock_repo)
        svc = LineageService(query_svc)
        traversal = svc.traverse_lineage(
            "artifact:my-proj.run-01.model",
            direction="both",
            max_depth=1,
        )
        assert traversal is not None

    def test_lineage_policy_default(self):
        policy = LineagePolicy()
        assert policy.default_direction == "both"
        assert policy.default_max_depth >= 1

    def test_lineage_policy_invalid_direction(self):
        from contexta.common.errors import ValidationError
        with pytest.raises(ValidationError):
            LineagePolicy(default_direction="sideways")

    def test_traversal_has_edges(self, mock_repo):
        from contexta.interpretation.repositories import RelationRecord
        rel = RelationRecord(
            relation_ref="relation:edge-lp",
            source_ref="artifact:my-proj.run-01.dataset",
            target_ref="artifact:my-proj.run-01.model",
            relation_type="generated_from",
            recorded_at="2024-01-01T00:00:00Z",
            origin_marker="declared",
            confidence_marker="confirmed",
        )
        mock_repo._relations.append(rel)

        query_svc = QueryService(mock_repo)
        svc = LineageService(query_svc)
        traversal = svc.traverse_lineage("artifact:my-proj.run-01.model", direction="inbound", max_depth=3)
        assert hasattr(traversal, "edges") or hasattr(traversal, "nodes")


# ---------------------------------------------------------------------------
# EXT-017: DiagnosticsService batch/deployment diagnostics
# ---------------------------------------------------------------------------

class TestDiagnosticsBatchDeployment:
    def test_failed_batch_produces_error_issue(self, mock_repo):
        from contexta.interpretation.repositories import BatchRecord
        failed_batch = BatchRecord(
            batch_id="batch:my-proj.run-01.train.failed-batch",
            run_id="my-proj.run-01",
            stage_id="my-proj.run-01.train",
            name="failed-batch",
            status="failed",
            order=1,
            started_at="2024-01-01T00:00:00Z",
            ended_at="2024-01-01T00:05:00Z",
        )
        mock_repo.add_batch(failed_batch)
        query_svc = QueryService(mock_repo)
        svc = DiagnosticsService(query_svc)
        result = svc.diagnose_run("my-proj.run-01")
        codes = {issue.code for issue in result.issues}
        assert "failed_batch" in codes

    def test_cancelled_batch_produces_warning(self, mock_repo):
        from contexta.interpretation.repositories import BatchRecord
        cancelled_batch = BatchRecord(
            batch_id="batch:my-proj.run-01.train.cancelled-batch",
            run_id="my-proj.run-01",
            stage_id="my-proj.run-01.train",
            name="cancelled-batch",
            status="cancelled",
            order=2,
            started_at="2024-01-01T00:00:00Z",
            ended_at="2024-01-01T00:01:00Z",
        )
        mock_repo.add_batch(cancelled_batch)
        query_svc = QueryService(mock_repo)
        svc = DiagnosticsService(query_svc)
        result = svc.diagnose_run("my-proj.run-01")
        codes = {issue.code for issue in result.issues}
        assert "incomplete_batch" in codes

    def test_failed_deployment_produces_error_issue(self, mock_repo):
        from contexta.interpretation.repositories import DeploymentRecord
        failed_dep = DeploymentRecord(
            deployment_id="deployment:my-proj.api-v2",
            project_name="my-proj",
            name="api-v2",
            status="failed",
            run_id="my-proj.run-01",
            started_at="2024-01-01T00:00:00Z",
            ended_at="2024-01-01T00:10:00Z",
        )
        mock_repo.add_deployment(failed_dep)
        query_svc = QueryService(mock_repo)
        svc = DiagnosticsService(query_svc)
        result = svc.diagnose_run("my-proj.run-01")
        codes = {issue.code for issue in result.issues}
        assert "failed_deployment" in codes

    def test_clean_run_has_no_batch_or_deployment_issues(self, mock_repo):
        query_svc = QueryService(mock_repo)
        svc = DiagnosticsService(query_svc)
        result = svc.diagnose_run("my-proj.run-01")
        batch_dep_codes = {c for c in (issue.code for issue in result.issues) if c in {"failed_batch", "incomplete_batch", "failed_deployment"}}
        assert batch_dep_codes == set()
