"""TST-008: event, emit_events, metric, emit_metrics tests."""

from __future__ import annotations

import pytest

from contexta.capture.models import EventEmission, MetricEmission
from contexta.common.errors import ValidationError
from contexta.config.models import UnifiedConfig, WorkspaceConfig


def _make_config(tmp_path):
    return UnifiedConfig(
        project_name="test-proj",
        workspace=WorkspaceConfig(root_path=tmp_path / ".contexta"),
    )


# ---------------------------------------------------------------------------
# EventEmission model
# ---------------------------------------------------------------------------

class TestEventEmission:
    def test_minimal_valid(self):
        e = EventEmission(key="train.start", message="Training started")
        assert e.key == "train.start"
        assert e.level == "info"

    def test_custom_level(self):
        e = EventEmission(key="err.occurred", message="Something failed", level="error")
        assert e.level == "error"

    def test_invalid_level_raises(self):
        with pytest.raises(ValidationError):
            EventEmission(key="x", message="y", level="verbose")

    def test_blank_key_raises(self):
        with pytest.raises(ValidationError):
            EventEmission(key="", message="y")

    def test_blank_message_raises(self):
        with pytest.raises(ValidationError):
            EventEmission(key="x", message="")

    def test_attributes_stored(self):
        e = EventEmission(key="x", message="y", attributes={"batch": 1})
        assert e.attributes["batch"] == 1


# ---------------------------------------------------------------------------
# MetricEmission model
# ---------------------------------------------------------------------------

class TestMetricEmission:
    def test_minimal_valid(self):
        m = MetricEmission(key="accuracy", value=0.95)
        assert m.key == "accuracy"
        assert m.value == 0.95

    def test_integer_value(self):
        m = MetricEmission(key="count", value=42)
        assert m.value == 42

    def test_blank_key_raises(self):
        with pytest.raises(ValidationError):
            MetricEmission(key="", value=0.5)

    def test_invalid_aggregation_scope(self):
        with pytest.raises(ValidationError):
            MetricEmission(key="loss", value=0.1, aggregation_scope="batch")

    def test_unit_stored(self):
        m = MetricEmission(key="size", value=1024, unit="bytes")
        assert m.unit == "bytes"


# ---------------------------------------------------------------------------
# capture_event via scope
# ---------------------------------------------------------------------------

class TestCaptureEvent:
    def test_event_capture_returns_result(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("run-a") as run:
            with run.stage("train") as stage:
                result = stage.event("epoch.end", message="Epoch 1 done")
                assert result is not None

    def test_event_capture_with_level(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("run-a") as run:
            result = run.event("run.started", message="started", level="info")
            assert result is not None

    def test_emit_events_batch(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("run-b") as run:
            emissions = [
                EventEmission(key="ev.one", message="first"),
                EventEmission(key="ev.two", message="second"),
            ]
            result = run.emit_events(emissions)
            assert result is not None

    def test_batch_scope_event_carries_batch_ref(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("run-batch-event") as run:
            with run.stage("train") as stage:
                with stage.batch("batch-0") as batch:
                    result = batch.event("batch.done", message="done")
                    payload = result.payload
                    assert str(payload.envelope.batch_execution_ref) == "batch:test-proj.run-batch-event.train.batch-0"
                    assert payload.payload.subject_ref == "batch:test-proj.run-batch-event.train.batch-0"

    def test_deployment_scope_event_carries_deployment_ref(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_deployment("recommendation-api", run_ref="run:test-proj.run-01") as deployment:
            result = deployment.event("deploy.done", message="done")
            payload = result.payload
            assert str(payload.envelope.deployment_execution_ref) == "deployment:test-proj.recommendation-api"
            assert payload.payload.subject_ref == "deployment:test-proj.recommendation-api"


# ---------------------------------------------------------------------------
# capture_metric via scope
# ---------------------------------------------------------------------------

class TestCaptureMetric:
    def test_metric_capture_returns_result(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("run-c") as run:
            with run.stage("train") as stage:
                result = stage.metric("loss", 0.42)
                assert result is not None

    def test_metric_at_run_scope(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("run-d") as run:
            result = run.metric("accuracy", 0.9, aggregation_scope="run")
            assert result is not None

    def test_emit_metrics_batch(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("run-e") as run:
            emissions = [
                MetricEmission(key="loss", value=0.3),
                MetricEmission(key="acc", value=0.95),
            ]
            result = run.emit_metrics(emissions)
            assert result is not None

    def test_batch_scope_metric_carries_batch_ref(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("run-batch-metric") as run:
            with run.stage("train") as stage:
                with stage.batch("batch-0") as batch:
                    result = batch.metric("loss", 0.42)
                    assert str(result.payload.envelope.batch_execution_ref) == "batch:test-proj.run-batch-metric.train.batch-0"

    def test_deployment_scope_metric_carries_deployment_ref(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_deployment("recommendation-api", run_ref="run:test-proj.run-01") as deployment:
            result = deployment.metric("latency", 12.5, aggregation_scope="run")
            assert str(result.payload.envelope.deployment_execution_ref) == "deployment:test-proj.recommendation-api"
