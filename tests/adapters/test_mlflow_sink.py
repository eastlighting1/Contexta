"""EXT-022: MLflowSink unit tests — no real mlflow package required.

A fake mlflow module is injected into sys.modules so the lazy _load_mlflow
helper resolves without the package being installed.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, call

import pytest

from contexta.contract import (
    DegradedPayload,
    DegradedRecord,
    MetricPayload,
    MetricRecord,
    RecordEnvelope,
    StructuredEventPayload,
    StructuredEventRecord,
)
from contexta.capture.results import PayloadFamily

# ---------------------------------------------------------------------------
# Fake mlflow module
# ---------------------------------------------------------------------------

def _make_fake_mlflow():
    fake = types.ModuleType("mlflow")
    fake.log_metric = MagicMock()
    fake.set_tag = MagicMock()
    return fake


@pytest.fixture()
def fake_mlflow(monkeypatch):
    mod = _make_fake_mlflow()
    monkeypatch.setitem(sys.modules, "mlflow", mod)
    return mod


# ---------------------------------------------------------------------------
# Envelope / payload factories (same patterns as test_otel_sink.py)
# ---------------------------------------------------------------------------

_NOW = "2025-01-01T00:00:00Z"
_RUN_REF = "run:test-proj.run-01"
_RECORD_REF = "record:test-proj.run-01.ev-001"
_STAGE_REF = "stage:test-proj.run-01.train"


def _envelope(**kwargs):
    defaults = dict(
        record_ref=_RECORD_REF,
        record_type="event",
        recorded_at=_NOW,
        observed_at=_NOW,
        producer_ref="contexta.test",
        run_ref=_RUN_REF,
        completeness_marker="complete",
        degradation_marker="none",
    )
    defaults.update(kwargs)
    return RecordEnvelope(**defaults)


def _metric_record(*, metric_key="loss", value=0.5, unit=None, tags=None, stage_ref=None):
    env = _envelope(record_type="metric", stage_execution_ref=stage_ref)
    payload = MetricPayload(
        metric_key=metric_key,
        value=value,
        value_type="float",
        unit=unit,
        aggregation_scope="step",
        subject_ref=None,
        slice_ref=None,
        tags=tags or {},
        summary_basis=None,
    )
    return MetricRecord(envelope=env, payload=payload)


def _event_record(*, event_key="ctx.checkpoint", level="info", message="done", stage_ref=None):
    env = _envelope(record_type="event", stage_execution_ref=stage_ref)
    payload = StructuredEventPayload(
        event_key=event_key,
        level=level,
        message=message,
        subject_ref=None,
        attributes={},
        origin_marker="explicit_capture",
    )
    return StructuredEventRecord(envelope=env, payload=payload)


def _degraded_record(*, issue_key="ctx.nan", category="capture", severity="error"):
    env = _envelope(record_type="degraded", degradation_marker="partial_failure")
    payload = DegradedPayload(
        issue_key=issue_key,
        category=category,
        severity=severity,
        summary="issue detected",
        subject_ref=None,
        origin_marker="explicit_capture",
        attributes=None,
    )
    return DegradedRecord(envelope=env, payload=payload)


# ---------------------------------------------------------------------------
# Construction / dependency guard
# ---------------------------------------------------------------------------

class TestMLflowSinkConstruction:

    def test_construction_succeeds_with_fake_mlflow(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink(name="mlflow-test")
        assert sink.name == "mlflow-test"

    def test_construction_raises_dependency_error_without_mlflow(self, monkeypatch):
        monkeypatch.delitem(sys.modules, "mlflow", raising=False)
        from contexta.common.errors import DependencyError
        from contexta.adapters.mlflow._sink import MLflowSink as _MLflowSink
        with pytest.raises(DependencyError) as exc_info:
            _MLflowSink()
        assert exc_info.value.code == "mlflow_not_ready"

    def test_supports_record_family(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        assert sink.supports(PayloadFamily.RECORD)

    def test_does_not_support_context_family(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        assert not sink.supports(PayloadFamily.CONTEXT)

    def test_default_run_id_is_none(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        assert sink._run_id is None

    def test_explicit_run_id_stored(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink(run_id="abc123")
        assert sink._run_id == "abc123"


# ---------------------------------------------------------------------------
# Metric export
# ---------------------------------------------------------------------------

class TestMLflowSinkMetricExport:

    def test_metric_calls_log_metric(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        record = _metric_record(metric_key="loss", value=0.42)
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        fake_mlflow.log_metric.assert_called_once_with("loss", 0.42)

    def test_metric_value_cast_to_float(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        record = _metric_record(value=1)
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        value_arg = fake_mlflow.log_metric.call_args[0][1]
        assert isinstance(value_arg, float)

    def test_metric_with_explicit_run_id(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink(run_id="run-xyz")
        record = _metric_record(metric_key="accuracy", value=0.9)
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        fake_mlflow.log_metric.assert_called_once_with("accuracy", 0.9, run_id="run-xyz")

    def test_metric_logs_run_ref_tag_once(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        record = _metric_record()
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        # run_ref tag must have been set
        tag_calls = {c[0][0]: c[0][1] for c in fake_mlflow.set_tag.call_args_list}
        assert tag_calls.get("contexta.run_ref") == _RUN_REF

    def test_metric_run_ref_tag_written_only_once(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        for _ in range(5):
            sink.capture(family=PayloadFamily.RECORD, payload=_metric_record())
        run_ref_calls = [
            c for c in fake_mlflow.set_tag.call_args_list
            if c[0][0] == "contexta.run_ref"
        ]
        assert len(run_ref_calls) == 1

    def test_metric_unit_tag_written_once(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        for _ in range(3):
            sink.capture(family=PayloadFamily.RECORD, payload=_metric_record(unit="ms"))
        unit_tag_calls = [
            c for c in fake_mlflow.set_tag.call_args_list
            if c[0][0] == "contexta.metric_unit.loss"
        ]
        assert len(unit_tag_calls) == 1
        assert unit_tag_calls[0][0][1] == "ms"

    def test_metric_no_unit_tag_when_unit_none(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        sink.capture(family=PayloadFamily.RECORD, payload=_metric_record(unit=None))
        tag_keys = [c[0][0] for c in fake_mlflow.set_tag.call_args_list]
        assert not any(k.startswith("contexta.metric_unit.") for k in tag_keys)

    def test_metric_tags_written_with_prefix(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        record = _metric_record(tags={"split": "train", "epoch": "5"})
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        tag_calls = {c[0][0]: c[0][1] for c in fake_mlflow.set_tag.call_args_list}
        assert tag_calls.get("contexta.tag.split") == "train"
        assert tag_calls.get("contexta.tag.epoch") == "5"

    def test_metric_stage_ref_tag_when_present(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        record = _metric_record(stage_ref=_STAGE_REF)
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        tag_calls = {c[0][0]: c[0][1] for c in fake_mlflow.set_tag.call_args_list}
        assert tag_calls.get("contexta.stage_ref") == _STAGE_REF

    def test_metric_no_stage_ref_tag_when_absent(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        record = _metric_record(stage_ref=None)
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        tag_keys = [c[0][0] for c in fake_mlflow.set_tag.call_args_list]
        assert "contexta.stage_ref" not in tag_keys

    def test_metric_capture_returns_success(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        receipt = sink.capture(family=PayloadFamily.RECORD, payload=_metric_record())
        assert receipt.status.value == "SUCCESS"

    def test_multiple_different_metrics_each_logged(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        sink.capture(family=PayloadFamily.RECORD, payload=_metric_record(metric_key="loss", value=0.5))
        sink.capture(family=PayloadFamily.RECORD, payload=_metric_record(metric_key="accuracy", value=0.9))
        logged_keys = [c[0][0] for c in fake_mlflow.log_metric.call_args_list]
        assert "loss" in logged_keys
        assert "accuracy" in logged_keys


# ---------------------------------------------------------------------------
# Event export
# ---------------------------------------------------------------------------

class TestMLflowSinkEventExport:

    def test_event_sets_tag_with_event_key(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        record = _event_record(event_key="epoch.end", message="epoch 1 complete")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        tag_calls = {c[0][0]: c[0][1] for c in fake_mlflow.set_tag.call_args_list}
        assert tag_calls.get("contexta.event.epoch.end") == "epoch 1 complete"

    def test_event_level_tag_written(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        record = _event_record(event_key="train.start", level="info")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        tag_calls = {c[0][0]: c[0][1] for c in fake_mlflow.set_tag.call_args_list}
        assert tag_calls.get("contexta.event_level.train.start") == "info"

    def test_event_message_truncated_to_5000_chars(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        long_message = "x" * 10_000
        record = _event_record(message=long_message)
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        tag_calls = {c[0][0]: c[0][1] for c in fake_mlflow.set_tag.call_args_list}
        event_val = tag_calls.get("contexta.event.ctx.checkpoint", "")
        assert len(event_val) <= 5000

    def test_event_logs_run_ref_tag(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        sink.capture(family=PayloadFamily.RECORD, payload=_event_record())
        tag_calls = {c[0][0]: c[0][1] for c in fake_mlflow.set_tag.call_args_list}
        assert "contexta.run_ref" in tag_calls

    def test_event_capture_returns_success(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        receipt = sink.capture(family=PayloadFamily.RECORD, payload=_event_record())
        assert receipt.status.value == "SUCCESS"

    def test_event_with_explicit_run_id(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink(run_id="my-run")
        record = _event_record(event_key="done")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        # All set_tag calls should include run_id kwarg
        for c in fake_mlflow.set_tag.call_args_list:
            assert c[1].get("run_id") == "my-run"


# ---------------------------------------------------------------------------
# Degraded export
# ---------------------------------------------------------------------------

class TestMLflowSinkDegradedExport:

    def test_degraded_sets_tag_with_issue_key(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        record = _degraded_record(issue_key="ctx.nan", category="capture", severity="error")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        tag_calls = {c[0][0]: c[0][1] for c in fake_mlflow.set_tag.call_args_list}
        assert tag_calls.get("contexta.degraded.ctx.nan") == "capture:error"

    def test_degraded_tag_value_format(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        record = _degraded_record(category="store", severity="warning")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        tag_calls = {c[0][0]: c[0][1] for c in fake_mlflow.set_tag.call_args_list}
        val = tag_calls.get("contexta.degraded.ctx.nan", "")
        assert val == "store:warning"

    def test_degraded_run_ref_tag_written(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        sink.capture(family=PayloadFamily.RECORD, payload=_degraded_record())
        tag_calls = {c[0][0]: c[0][1] for c in fake_mlflow.set_tag.call_args_list}
        assert tag_calls.get("contexta.degraded_run_ref") == _RUN_REF

    def test_degraded_capture_returns_success(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        receipt = sink.capture(family=PayloadFamily.RECORD, payload=_degraded_record())
        assert receipt.status.value == "SUCCESS"

    def test_degraded_with_explicit_run_id(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink(run_id="run-abc")
        record = _degraded_record()
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        for c in fake_mlflow.set_tag.call_args_list:
            assert c[1].get("run_id") == "run-abc"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestMLflowSinkEdgeCases:

    def test_unsupported_family_returns_success_skipped(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink = MLflowSink()
        receipt = sink.capture(family=PayloadFamily.CONTEXT, payload=object())
        assert receipt.status.value == "SUCCESS"
        fake_mlflow.log_metric.assert_not_called()
        fake_mlflow.set_tag.assert_not_called()

    def test_unknown_record_type_returns_success_skipped(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink

        class Unrecognised:
            pass

        sink = MLflowSink()
        receipt = sink.capture(family=PayloadFamily.RECORD, payload=Unrecognised())
        assert receipt.status.value == "SUCCESS"
        fake_mlflow.log_metric.assert_not_called()

    def test_mlflow_adapter_exports_mlflow_sink(self, fake_mlflow):
        import contexta.adapters.mlflow as mlflow_adapter
        assert mlflow_adapter.__all__ == ["MLflowSink"]
        assert hasattr(mlflow_adapter, "MLflowSink")

    def test_tag_write_cache_isolated_per_instance(self, fake_mlflow):
        from contexta.adapters.mlflow import MLflowSink
        sink1 = MLflowSink()
        sink2 = MLflowSink()
        record = _metric_record()
        sink1.capture(family=PayloadFamily.RECORD, payload=record)
        sink2.capture(family=PayloadFamily.RECORD, payload=record)
        # Both sinks should have written the run_ref tag independently
        run_ref_calls = [
            c for c in fake_mlflow.set_tag.call_args_list
            if c[0][0] == "contexta.run_ref"
        ]
        assert len(run_ref_calls) == 2
