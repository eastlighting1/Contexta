"""TST-016: list_runs, snapshot, compare, multi-compare tests."""

from __future__ import annotations

import pytest

from contexta.common.errors import InterpretationError
from contexta.interpretation.query.filters import RunListQuery
from contexta.interpretation.query.service import QueryService
from contexta.interpretation.compare.service import CompareService


# ---------------------------------------------------------------------------
# QueryService
# ---------------------------------------------------------------------------

class TestQueryServiceListRuns:
    def test_list_projects(self, mock_repo):
        svc = QueryService(mock_repo)
        projects = svc.list_projects()
        assert "my-proj" in projects

    def test_list_all_runs(self, mock_repo):
        svc = QueryService(mock_repo)
        runs = svc.list_runs()
        assert len(runs) == 2

    def test_list_runs_by_project(self, mock_repo):
        svc = QueryService(mock_repo)
        runs = svc.list_runs("my-proj")
        assert len(runs) == 2

    def test_list_runs_unknown_project(self, mock_repo):
        svc = QueryService(mock_repo)
        runs = svc.list_runs("nonexistent")
        assert runs == ()

    def test_list_runs_with_query(self, mock_repo):
        svc = QueryService(mock_repo)
        query = RunListQuery(project_name="my-proj")
        runs = svc.list_runs(query=query)
        assert len(runs) >= 1

    def test_list_runs_with_limit(self, mock_repo):
        svc = QueryService(mock_repo)
        query = RunListQuery(limit=1)
        runs = svc.list_runs(query=query)
        assert len(runs) == 1

    def test_list_runs_with_offset(self, mock_repo):
        svc = QueryService(mock_repo)
        all_runs = svc.list_runs()
        query = RunListQuery(offset=1)
        offset_runs = svc.list_runs(query=query)
        assert len(offset_runs) == len(all_runs) - 1


class TestQueryServiceGetSnapshot:
    def test_get_run_snapshot(self, mock_repo):
        svc = QueryService(mock_repo)
        snapshot = svc.get_run_snapshot("my-proj.run-01")
        assert snapshot is not None
        assert snapshot.run.run_id == "my-proj.run-01"

    def test_snapshot_includes_stages(self, mock_repo):
        svc = QueryService(mock_repo)
        snapshot = svc.get_run_snapshot("my-proj.run-01")
        assert len(snapshot.stages) >= 1

    def test_snapshot_includes_deployments(self, mock_repo):
        svc = QueryService(mock_repo)
        snapshot = svc.get_run_snapshot("my-proj.run-01")
        assert len(snapshot.deployments) >= 1
        assert snapshot.deployments[0].run_id == "my-proj.run-01"

    def test_snapshot_includes_batches(self, mock_repo):
        svc = QueryService(mock_repo)
        snapshot = svc.get_run_snapshot("my-proj.run-01")
        assert len(snapshot.batches) >= 1
        assert snapshot.batches[0].stage_id == "my-proj.run-01.train"

    def test_snapshot_includes_samples(self, mock_repo):
        svc = QueryService(mock_repo)
        snapshot = svc.get_run_snapshot("my-proj.run-01")
        assert len(snapshot.samples) >= 1
        assert snapshot.samples[0].batch_id == "batch:my-proj.run-01.train.mini-batch-0"

    def test_snapshot_includes_artifacts(self, mock_repo):
        svc = QueryService(mock_repo)
        snapshot = svc.get_run_snapshot("my-proj.run-01")
        assert len(snapshot.artifacts) >= 1

    def test_get_missing_run_raises(self, mock_repo):
        svc = QueryService(mock_repo)
        with pytest.raises(InterpretationError, match="[Nn]ot [Ff]ound|not found"):
            svc.get_run_snapshot("nonexistent.run")


# ---------------------------------------------------------------------------
# CompareService
# ---------------------------------------------------------------------------

class TestCompareService:
    def test_compare_two_runs(self, mock_repo):
        svc = CompareService(QueryService(mock_repo))
        comparison = svc.compare_runs("my-proj.run-01", "my-proj.run-02")
        assert comparison is not None

    def test_comparison_has_metric_deltas(self, mock_repo):
        svc = CompareService(QueryService(mock_repo))
        comparison = svc.compare_runs("my-proj.run-01", "my-proj.run-02")
        assert hasattr(comparison, "metric_deltas") or hasattr(comparison, "stage_comparisons")

    def test_multi_compare(self, mock_repo):
        svc = CompareService(QueryService(mock_repo))
        result = svc.compare_multiple_runs(["my-proj.run-01", "my-proj.run-02"])
        assert result is not None

    def test_compare_same_run(self, mock_repo):
        svc = CompareService(QueryService(mock_repo))
        # Comparing a run with itself should not raise
        comparison = svc.compare_runs("my-proj.run-01", "my-proj.run-01")
        assert comparison is not None

    def test_best_run_selection(self, mock_repo):
        svc = CompareService(QueryService(mock_repo))
        best = svc.select_best_run(["my-proj.run-01", "my-proj.run-02"], metric_key="loss", higher_is_better=False)
        assert best is not None


# ---------------------------------------------------------------------------
# EXT-017: QueryService batch/sample/deployment query methods
# ---------------------------------------------------------------------------

class TestQueryServiceBatchSampleDeployment:
    def test_list_batches_returns_tuple(self, mock_repo):
        svc = QueryService(mock_repo)
        batches = svc.list_batches("my-proj.run-01")
        assert isinstance(batches, tuple)

    def test_list_batches_with_stage_filter(self, mock_repo):
        svc = QueryService(mock_repo)
        snapshot = svc.get_run_snapshot("my-proj.run-01")
        if snapshot.stages:
            stage_id = snapshot.stages[0].stage_id
            batches = svc.list_batches("my-proj.run-01", stage_id=stage_id)
            assert isinstance(batches, tuple)

    def test_list_samples_returns_tuple(self, mock_repo):
        svc = QueryService(mock_repo)
        samples = svc.list_samples("my-proj.run-01")
        assert isinstance(samples, tuple)

    def test_list_deployments_returns_tuple(self, mock_repo):
        svc = QueryService(mock_repo)
        deployments = svc.list_deployments()
        assert isinstance(deployments, tuple)

    def test_list_deployments_by_run_id(self, mock_repo):
        svc = QueryService(mock_repo)
        deployments = svc.list_deployments(run_id="my-proj.run-01")
        assert isinstance(deployments, tuple)

    def test_snapshot_includes_batches(self, mock_repo):
        svc = QueryService(mock_repo)
        snapshot = svc.get_run_snapshot("my-proj.run-01")
        assert hasattr(snapshot, "batches")
        assert isinstance(snapshot.batches, tuple)

    def test_snapshot_includes_samples(self, mock_repo):
        svc = QueryService(mock_repo)
        snapshot = svc.get_run_snapshot("my-proj.run-01")
        assert hasattr(snapshot, "samples")
        assert isinstance(snapshot.samples, tuple)

    def test_snapshot_includes_deployments(self, mock_repo):
        svc = QueryService(mock_repo)
        snapshot = svc.get_run_snapshot("my-proj.run-01")
        assert hasattr(snapshot, "deployments")
        assert isinstance(snapshot.deployments, tuple)
