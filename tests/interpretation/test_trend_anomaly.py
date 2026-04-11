"""TST-018: trend, aggregate, baseline, anomaly tests."""

from __future__ import annotations

import pytest

from contexta.interpretation.anomaly.service import AnomalyPolicy, AnomalyService
from contexta.interpretation.aggregation.service import AggregationService
from contexta.interpretation.query.service import QueryService
from contexta.interpretation.trend.service import TrendPolicy, TrendService


# ---------------------------------------------------------------------------
# TrendService
# ---------------------------------------------------------------------------

class TestTrendService:
    def test_get_metric_trend(self, mock_repo):
        query_svc = QueryService(mock_repo)
        svc = TrendService(query_svc)
        trend = svc.get_metric_trend(
            "loss",
            project_name="my-proj",
        )
        assert trend is not None

    def test_metric_trend_has_points(self, mock_repo):
        query_svc = QueryService(mock_repo)
        svc = TrendService(query_svc)
        trend = svc.get_metric_trend("loss", project_name="my-proj")
        assert hasattr(trend, "points")

    def test_get_stage_duration_trend(self, mock_repo):
        query_svc = QueryService(mock_repo)
        svc = TrendService(query_svc)
        trend = svc.get_stage_duration_trend("train", project_name="my-proj")
        assert trend is not None

    def test_get_artifact_size_trend(self, mock_repo):
        query_svc = QueryService(mock_repo)
        svc = TrendService(query_svc)
        trend = svc.get_artifact_size_trend("checkpoint", project_name="my-proj")
        assert trend is not None

    def test_trend_policy_defaults(self):
        policy = TrendPolicy()
        assert policy.default_window_runs > 0

    def test_trend_policy_invalid_window(self):
        from contexta.common.errors import ValidationError
        with pytest.raises(ValidationError):
            TrendPolicy(default_window_runs=0)

    def test_trend_policy_invalid_aggregation(self):
        from contexta.common.errors import ValidationError
        with pytest.raises(ValidationError):
            TrendPolicy(metric_aggregation="median")

    def test_get_step_series(self, mock_repo):
        query_svc = QueryService(mock_repo)
        svc = TrendService(query_svc)
        series = svc.get_step_series(
            "my-proj.run-01",
            "loss",
        )
        assert series is not None


# ---------------------------------------------------------------------------
# AggregationService
# ---------------------------------------------------------------------------

class TestAggregationService:
    def test_aggregate_metric_for_run(self, mock_repo):
        svc = AggregationService(QueryService(mock_repo))
        result = svc.aggregate_metric("loss", project_name="my-proj")
        assert result is not None

    def test_aggregate_metric_has_value(self, mock_repo):
        svc = AggregationService(QueryService(mock_repo))
        result = svc.aggregate_metric("loss", project_name="my-proj")
        assert hasattr(result, "mean")

    def test_aggregate_by_stage(self, mock_repo):
        svc = AggregationService(QueryService(mock_repo))
        result = svc.aggregate_by_stage(project_name="my-proj")
        assert result is not None

    def test_run_status_distribution(self, mock_repo):
        svc = AggregationService(QueryService(mock_repo))
        dist = svc.run_status_distribution(project_name="my-proj")
        assert dist is not None


# ---------------------------------------------------------------------------
# AnomalyService
# ---------------------------------------------------------------------------

class TestAnomalyService:
    def test_detect_anomalies_with_baseline(self, mock_repo):
        from contexta.interpretation.anomaly.models import MetricBaseline
        query_svc = QueryService(mock_repo)
        svc = AnomalyService(query_svc, min_baseline_runs=1)
        baseline = MetricBaseline(
            metric_key="loss",
            mean=0.5,
            std=0.1,
            p5=0.3,
            p95=0.7,
            computed_from_n_runs=2,
        )
        result = svc.detect_anomalies("my-proj.run-02", baseline=baseline)
        assert result is not None

    def test_anomaly_result_has_fields(self, mock_repo):
        from contexta.interpretation.anomaly.models import MetricBaseline
        query_svc = QueryService(mock_repo)
        svc = AnomalyService(query_svc, min_baseline_runs=1)
        baseline = MetricBaseline(
            metric_key="loss", mean=0.5, std=0.1, p5=0.3, p95=0.7, computed_from_n_runs=2
        )
        result = svc.detect_anomalies("my-proj.run-02", baseline=baseline)
        assert isinstance(result, tuple)

    def test_detect_anomalies_in_run(self, mock_repo):
        query_svc = QueryService(mock_repo)
        svc = AnomalyService(query_svc, min_baseline_runs=1)
        result = svc.detect_anomalies_in_run("my-proj.run-02")
        assert result is not None

    def test_anomaly_policy_defaults(self):
        policy = AnomalyPolicy()
        assert policy.z_score_threshold > 0

    def test_anomaly_policy_invalid_z_score(self):
        from contexta.common.errors import ValidationError
        with pytest.raises(ValidationError):
            AnomalyPolicy(z_score_threshold=0)

    def test_anomaly_policy_invalid_min_baseline(self):
        from contexta.common.errors import ValidationError
        with pytest.raises(ValidationError):
            AnomalyPolicy(min_baseline_runs=0)
