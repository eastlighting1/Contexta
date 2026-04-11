"""EXT-020: OTelSink unit tests — no real opentelemetry-api required.

Fake OTel modules are injected into sys.modules so the lazy _load_otel_*
helpers resolve without the package being installed.
"""

from __future__ import annotations

import sys
import types
import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

from contexta.contract import (
    DegradedPayload,
    DegradedRecord,
    MetricPayload,
    MetricRecord,
    RecordEnvelope,
    StructuredEventPayload,
    StructuredEventRecord,
    TraceSpanPayload,
    TraceSpanRecord,
)
from contexta.capture.results import PayloadFamily

# ---------------------------------------------------------------------------
# Fake OTel helpers
# ---------------------------------------------------------------------------

def _make_fake_otel_modules():
    """Build minimal fake opentelemetry.trace and opentelemetry.metrics."""

    # --- opentelemetry.trace ---
    fake_trace = types.ModuleType("opentelemetry.trace")

    class _SpanKind:
        INTERNAL = "INTERNAL"
        CLIENT = "CLIENT"
        PRODUCER = "PRODUCER"
        SERVER = "SERVER"
        CONSUMER = "CONSUMER"

    class _StatusCode:
        OK = "OK"
        ERROR = "ERROR"
        UNSET = "UNSET"

    fake_trace.SpanKind = _SpanKind
    fake_trace.StatusCode = _StatusCode

    # Default current span (non-recording stub)
    class _NoopSpan:
        def add_event(self, name, *, attributes=None):
            self._last_event = (name, attributes)
        def set_status(self, code):
            self._last_status = code
        def end(self):
            self._ended = True

    _current_span = _NoopSpan()
    fake_trace.get_current_span = lambda: _current_span

    # Default global provider is never used when we pass providers directly
    fake_trace.get_tracer_provider = lambda: None

    # --- opentelemetry.metrics ---
    fake_metrics = types.ModuleType("opentelemetry.metrics")
    fake_metrics.get_meter_provider = lambda: None

    # --- opentelemetry (parent package) ---
    fake_otel = types.ModuleType("opentelemetry")

    return fake_otel, fake_trace, fake_metrics, _current_span


@pytest.fixture()
def otel_modules(monkeypatch):
    """Inject fake OTel modules into sys.modules and restore on teardown."""
    fake_otel, fake_trace, fake_metrics, current_span = _make_fake_otel_modules()

    monkeypatch.setitem(sys.modules, "opentelemetry", fake_otel)
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", fake_trace)
    monkeypatch.setitem(sys.modules, "opentelemetry.metrics", fake_metrics)

    return {"trace": fake_trace, "metrics": fake_metrics, "current_span": current_span}


# ---------------------------------------------------------------------------
# Fake providers + tracer/meter
# ---------------------------------------------------------------------------

def _make_fake_tracer():
    """Return a fake tracer whose start_span records the last call."""
    tracer = MagicMock()
    span = MagicMock()
    tracer.start_span.return_value = span
    return tracer, span


def _make_fake_meter():
    """Return a fake meter whose create_histogram returns a histogram mock."""
    meter = MagicMock()
    histogram = MagicMock()
    meter.create_histogram.return_value = histogram
    return meter, histogram


def _make_fake_provider(tracer=None, meter=None):
    tracer_provider = MagicMock()
    tracer_provider.get_tracer.return_value = tracer
    meter_provider = MagicMock()
    meter_provider.get_meter.return_value = meter
    return tracer_provider, meter_provider


# ---------------------------------------------------------------------------
# Envelope / payload factories
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


def _span_record(*, span_kind="operation", status="ok", attrs=None, stage_ref=None):
    env = _envelope(record_type="span", stage_execution_ref=stage_ref)
    payload = TraceSpanPayload(
        span_id=str(uuid.uuid4()),
        trace_id=str(uuid.uuid4()),
        parent_span_id=None,
        span_name="test.span",
        started_at=_NOW,
        ended_at=_NOW,
        status=status,
        span_kind=span_kind,
        attributes=attrs or {},
        linked_refs=None,
    )
    return TraceSpanRecord(envelope=env, payload=payload)


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


def _event_record(*, event_key="my.event", level="info", message="hello", stage_ref=None):
    env = _envelope(record_type="event", stage_execution_ref=stage_ref)
    payload = StructuredEventPayload(
        event_key=event_key,
        level=level,
        message=message,
        subject_ref=None,
        attributes={"extra": "1"},
        origin_marker="explicit_capture",
    )
    return StructuredEventRecord(envelope=env, payload=payload)


def _degraded_record(*, issue_key="ctx.nan", category="capture", severity="error", stage_ref=None):
    env = _envelope(record_type="degraded", stage_execution_ref=stage_ref, degradation_marker="partial_failure")
    payload = DegradedPayload(
        issue_key=issue_key,
        category=category,
        severity=severity,
        summary="NaN detected",
        subject_ref=None,
        origin_marker="explicit_capture",
        attributes=None,
    )
    return DegradedRecord(envelope=env, payload=payload)


# ---------------------------------------------------------------------------
# Construction / dependency guard tests
# ---------------------------------------------------------------------------

class TestOTelSinkConstruction:

    def test_construction_succeeds_with_fake_otel(self, otel_modules):
        from contexta.adapters.otel import OTelSink
        sink = OTelSink(service_name="svc", name="otel-test")
        assert sink.name == "otel-test"

    def test_construction_raises_dependency_error_without_otel(self, monkeypatch):
        # Ensure modules are not present
        monkeypatch.delitem(sys.modules, "opentelemetry.trace", raising=False)
        monkeypatch.delitem(sys.modules, "opentelemetry.metrics", raising=False)
        monkeypatch.delitem(sys.modules, "opentelemetry", raising=False)
        from contexta.common.errors import DependencyError
        from contexta.adapters.otel._sink import OTelSink as _OTelSink
        with pytest.raises(DependencyError) as exc_info:
            _OTelSink()
        assert exc_info.value.code == "otel_api_not_ready"

    def test_supports_record_family(self, otel_modules):
        from contexta.adapters.otel import OTelSink
        sink = OTelSink()
        assert sink.supports(PayloadFamily.RECORD)

    def test_does_not_support_context_family(self, otel_modules):
        from contexta.adapters.otel import OTelSink
        sink = OTelSink()
        assert not sink.supports(PayloadFamily.CONTEXT)


# ---------------------------------------------------------------------------
# Span export
# ---------------------------------------------------------------------------

class TestOTelSinkSpanExport:

    def _sink_with_tracer(self, otel_modules):
        from contexta.adapters.otel import OTelSink
        tracer, span = _make_fake_tracer()
        tracer_provider, _ = _make_fake_provider(tracer=tracer)
        _, meter_provider = _make_fake_provider(meter=MagicMock())
        sink = OTelSink(tracer_provider=tracer_provider, meter_provider=meter_provider)
        return sink, tracer, span

    def test_span_calls_start_span(self, otel_modules):
        sink, tracer, span = self._sink_with_tracer(otel_modules)
        record = _span_record()
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        tracer.start_span.assert_called_once()
        call_kwargs = tracer.start_span.call_args
        assert call_kwargs[0][0] == "test.span" or call_kwargs[1].get("name") == "test.span" or call_kwargs[0][0] == "test.span"

    def test_span_name_passed_correctly(self, otel_modules):
        sink, tracer, span = self._sink_with_tracer(otel_modules)
        record = _span_record()
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        name_arg = tracer.start_span.call_args[0][0]
        assert name_arg == "test.span"

    def test_span_attributes_contain_run_ref(self, otel_modules):
        sink, tracer, span = self._sink_with_tracer(otel_modules)
        record = _span_record()
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        attrs = tracer.start_span.call_args[1]["attributes"]
        assert attrs["contexta.run_ref"] == _RUN_REF

    def test_span_attributes_contain_record_ref(self, otel_modules):
        sink, tracer, span = self._sink_with_tracer(otel_modules)
        record = _span_record()
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        attrs = tracer.start_span.call_args[1]["attributes"]
        assert attrs["contexta.record_ref"] == _RECORD_REF

    def test_span_stage_ref_included_when_present(self, otel_modules):
        sink, tracer, span = self._sink_with_tracer(otel_modules)
        record = _span_record(stage_ref=_STAGE_REF)
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        attrs = tracer.start_span.call_args[1]["attributes"]
        assert attrs["contexta.stage_ref"] == _STAGE_REF

    def test_span_stage_ref_absent_when_none(self, otel_modules):
        sink, tracer, span = self._sink_with_tracer(otel_modules)
        record = _span_record(stage_ref=None)
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        attrs = tracer.start_span.call_args[1]["attributes"]
        assert "contexta.stage_ref" not in attrs

    def test_span_kind_operation_maps_to_internal(self, otel_modules):
        sink, tracer, span = self._sink_with_tracer(otel_modules)
        record = _span_record(span_kind="operation")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        kind_arg = tracer.start_span.call_args[1]["kind"]
        assert kind_arg == "INTERNAL"

    def test_span_kind_io_maps_to_client(self, otel_modules):
        sink, tracer, span = self._sink_with_tracer(otel_modules)
        record = _span_record(span_kind="io")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        kind_arg = tracer.start_span.call_args[1]["kind"]
        assert kind_arg == "CLIENT"

    def test_span_kind_process_maps_to_producer(self, otel_modules):
        sink, tracer, span = self._sink_with_tracer(otel_modules)
        record = _span_record(span_kind="process")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        kind_arg = tracer.start_span.call_args[1]["kind"]
        assert kind_arg == "PRODUCER"

    def test_span_status_ok_calls_set_status_ok(self, otel_modules):
        sink, tracer, span = self._sink_with_tracer(otel_modules)
        record = _span_record(status="ok")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        span.set_status.assert_called_once_with("OK")

    def test_span_status_error_calls_set_status_error(self, otel_modules):
        sink, tracer, span = self._sink_with_tracer(otel_modules)
        record = _span_record(status="error")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        span.set_status.assert_called_once_with("ERROR")

    def test_span_end_is_called(self, otel_modules):
        sink, tracer, span = self._sink_with_tracer(otel_modules)
        record = _span_record()
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        span.end.assert_called_once()

    def test_capture_returns_success_receipt(self, otel_modules):
        sink, tracer, span = self._sink_with_tracer(otel_modules)
        record = _span_record()
        receipt = sink.capture(family=PayloadFamily.RECORD, payload=record)
        assert receipt.status.value == "SUCCESS"

    def test_span_custom_attributes_prefixed(self, otel_modules):
        sink, tracer, span = self._sink_with_tracer(otel_modules)
        record = _span_record(attrs={"model": "gpt4", "step": "100"})
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        attrs = tracer.start_span.call_args[1]["attributes"]
        assert attrs["contexta.span.model"] == "gpt4"
        assert attrs["contexta.span.step"] == "100"


# ---------------------------------------------------------------------------
# Metric export
# ---------------------------------------------------------------------------

class TestOTelSinkMetricExport:

    def _sink_with_meter(self, otel_modules):
        from contexta.adapters.otel import OTelSink
        meter, histogram = _make_fake_meter()
        _, meter_provider = _make_fake_provider(meter=meter)
        tracer, _ = _make_fake_tracer()
        tracer_provider, _ = _make_fake_provider(tracer=tracer)
        sink = OTelSink(tracer_provider=tracer_provider, meter_provider=meter_provider)
        return sink, meter, histogram

    def test_metric_creates_histogram(self, otel_modules):
        sink, meter, histogram = self._sink_with_meter(otel_modules)
        record = _metric_record()
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        meter.create_histogram.assert_called_once()
        name_arg = meter.create_histogram.call_args[1].get("name") or meter.create_histogram.call_args[0][0]
        assert name_arg == "contexta.loss"

    def test_metric_instrument_name_prefixed(self, otel_modules):
        sink, meter, histogram = self._sink_with_meter(otel_modules)
        record = _metric_record(metric_key="accuracy")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        name_arg = meter.create_histogram.call_args[1]["name"]
        assert name_arg == "contexta.accuracy"

    def test_metric_records_float_value(self, otel_modules):
        sink, meter, histogram = self._sink_with_meter(otel_modules)
        record = _metric_record(value=0.314)
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        histogram.record.assert_called_once()
        value_arg = histogram.record.call_args[0][0]
        assert value_arg == pytest.approx(0.314)

    def test_metric_unit_defaults_to_one(self, otel_modules):
        sink, meter, histogram = self._sink_with_meter(otel_modules)
        record = _metric_record(unit=None)
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        unit_arg = meter.create_histogram.call_args[1]["unit"]
        assert unit_arg == "1"

    def test_metric_unit_propagated_when_set(self, otel_modules):
        sink, meter, histogram = self._sink_with_meter(otel_modules)
        record = _metric_record(unit="ms")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        unit_arg = meter.create_histogram.call_args[1]["unit"]
        assert unit_arg == "ms"

    def test_metric_instrument_cached(self, otel_modules):
        sink, meter, histogram = self._sink_with_meter(otel_modules)
        record1 = _metric_record(metric_key="loss")
        record2 = _metric_record(metric_key="loss")
        sink.capture(family=PayloadFamily.RECORD, payload=record1)
        sink.capture(family=PayloadFamily.RECORD, payload=record2)
        # create_histogram only once despite two captures
        assert meter.create_histogram.call_count == 1
        assert histogram.record.call_count == 2

    def test_metric_attributes_contain_run_ref(self, otel_modules):
        sink, meter, histogram = self._sink_with_meter(otel_modules)
        record = _metric_record()
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        attrs = histogram.record.call_args[1]["attributes"]
        assert attrs["contexta.run_ref"] == _RUN_REF

    def test_metric_tags_prefixed(self, otel_modules):
        sink, meter, histogram = self._sink_with_meter(otel_modules)
        record = _metric_record(tags={"split": "train", "epoch": "5"})
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        attrs = histogram.record.call_args[1]["attributes"]
        assert attrs["contexta.tag.split"] == "train"
        assert attrs["contexta.tag.epoch"] == "5"

    def test_metric_capture_returns_success(self, otel_modules):
        sink, meter, histogram = self._sink_with_meter(otel_modules)
        record = _metric_record()
        receipt = sink.capture(family=PayloadFamily.RECORD, payload=record)
        assert receipt.status.value == "SUCCESS"


# ---------------------------------------------------------------------------
# Structured event export
# ---------------------------------------------------------------------------

class TestOTelSinkEventExport:

    def _sink(self, otel_modules):
        from contexta.adapters.otel import OTelSink
        tracer, _ = _make_fake_tracer()
        tracer_provider, _ = _make_fake_provider(tracer=tracer)
        meter, _ = _make_fake_meter()
        _, meter_provider = _make_fake_provider(meter=meter)
        sink = OTelSink(tracer_provider=tracer_provider, meter_provider=meter_provider)
        return sink

    def test_event_calls_add_event_on_current_span(self, otel_modules):
        sink = self._sink(otel_modules)
        current_span = otel_modules["current_span"]
        record = _event_record(event_key="ctx.checkpoint")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        assert current_span._last_event[0] == "ctx.checkpoint"

    def test_event_attributes_contain_level(self, otel_modules):
        sink = self._sink(otel_modules)
        current_span = otel_modules["current_span"]
        record = _event_record(level="warning", message="low mem")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        attrs = current_span._last_event[1]
        assert attrs["contexta.event_level"] == "warning"

    def test_event_attributes_contain_message(self, otel_modules):
        sink = self._sink(otel_modules)
        current_span = otel_modules["current_span"]
        record = _event_record(message="epoch done")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        attrs = current_span._last_event[1]
        assert attrs["contexta.event_message"] == "epoch done"

    def test_event_attributes_contain_run_ref(self, otel_modules):
        sink = self._sink(otel_modules)
        current_span = otel_modules["current_span"]
        record = _event_record()
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        attrs = current_span._last_event[1]
        assert attrs["contexta.run_ref"] == _RUN_REF

    def test_event_capture_returns_success(self, otel_modules):
        sink = self._sink(otel_modules)
        record = _event_record()
        receipt = sink.capture(family=PayloadFamily.RECORD, payload=record)
        assert receipt.status.value == "SUCCESS"


# ---------------------------------------------------------------------------
# Degraded export
# ---------------------------------------------------------------------------

class TestOTelSinkDegradedExport:

    def _sink(self, otel_modules):
        from contexta.adapters.otel import OTelSink
        tracer, _ = _make_fake_tracer()
        tracer_provider, _ = _make_fake_provider(tracer=tracer)
        meter, _ = _make_fake_meter()
        _, meter_provider = _make_fake_provider(meter=meter)
        sink = OTelSink(tracer_provider=tracer_provider, meter_provider=meter_provider)
        return sink

    def test_degraded_adds_event_named_contexta_degraded(self, otel_modules):
        sink = self._sink(otel_modules)
        current_span = otel_modules["current_span"]
        record = _degraded_record()
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        assert current_span._last_event[0] == "contexta.degraded"

    def test_degraded_attributes_contain_issue_key(self, otel_modules):
        sink = self._sink(otel_modules)
        current_span = otel_modules["current_span"]
        record = _degraded_record(issue_key="ctx.nan_values")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        attrs = current_span._last_event[1]
        assert attrs["contexta.issue_key"] == "ctx.nan_values"

    def test_degraded_attributes_contain_category(self, otel_modules):
        sink = self._sink(otel_modules)
        current_span = otel_modules["current_span"]
        record = _degraded_record(category="capture")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        attrs = current_span._last_event[1]
        assert attrs["contexta.degradation_category"] == "capture"

    def test_degraded_attributes_contain_severity(self, otel_modules):
        sink = self._sink(otel_modules)
        current_span = otel_modules["current_span"]
        record = _degraded_record(severity="warning")
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        attrs = current_span._last_event[1]
        assert attrs["contexta.severity"] == "warning"

    def test_degraded_attributes_contain_run_ref(self, otel_modules):
        sink = self._sink(otel_modules)
        current_span = otel_modules["current_span"]
        record = _degraded_record()
        sink.capture(family=PayloadFamily.RECORD, payload=record)
        attrs = current_span._last_event[1]
        assert attrs["contexta.run_ref"] == _RUN_REF

    def test_degraded_capture_returns_success(self, otel_modules):
        sink = self._sink(otel_modules)
        record = _degraded_record()
        receipt = sink.capture(family=PayloadFamily.RECORD, payload=record)
        assert receipt.status.value == "SUCCESS"


# ---------------------------------------------------------------------------
# Unsupported family / unknown record
# ---------------------------------------------------------------------------

class TestOTelSinkEdgeCases:

    def test_unsupported_family_returns_success_skipped(self, otel_modules):
        from contexta.adapters.otel import OTelSink
        sink = OTelSink()
        receipt = sink.capture(family=PayloadFamily.CONTEXT, payload=object())
        assert receipt.status.value == "SUCCESS"

    def test_unknown_record_type_returns_success_skipped(self, otel_modules):
        from contexta.adapters.otel import OTelSink

        class Unrecognised:
            pass

        sink = OTelSink()
        receipt = sink.capture(family=PayloadFamily.RECORD, payload=Unrecognised())
        assert receipt.status.value == "SUCCESS"
