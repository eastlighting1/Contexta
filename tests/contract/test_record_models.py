"""TST-003: event, metric, span, degraded model tests."""

import pytest

from contexta.common.errors import ValidationError
from contexta.contract.models.records import (
    COMPLETENESS_MARKERS,
    DEGRADED_CATEGORIES,
    DEGRADED_SEVERITIES,
    DEGRADATION_MARKERS,
    EVENT_LEVELS,
    METRIC_AGGREGATION_SCOPES,
    RECORD_TYPES,
    TRACE_SPAN_KINDS,
    TRACE_SPAN_STATUSES,
    CorrelationRefs,
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


TS = "2024-01-01T00:00:00Z"
TS2 = "2024-01-01T00:00:01Z"
PROJ = "project:my-proj"
RUN = "run:my-proj.run-01"
DEPLOYMENT = "deployment:my-proj.recommendation-api"
STAGE = "stage:my-proj.run-01.train"
BATCH = "batch:my-proj.run-01.train.batch-0"
OP = "op:my-proj.run-01.train.fit"


def _make_envelope(**overrides):
    defaults = dict(
        record_ref="record:my-proj.run-01.ev-1",
        run_ref=RUN,
        record_type="event",
        observed_at=TS,
        recorded_at=TS,
        producer_ref="contexta.test",
        completeness_marker="complete",
        degradation_marker="none",
    )
    defaults.update(overrides)
    return RecordEnvelope(**defaults)


# ---------------------------------------------------------------------------
# CorrelationRefs
# ---------------------------------------------------------------------------

class TestCorrelationRefs:
    def test_empty(self):
        c = CorrelationRefs()
        assert c.trace_id is None
        assert c.session_id is None

    def test_with_values(self):
        c = CorrelationRefs(trace_id="t1", session_id="s1")
        assert c.trace_id == "t1"

    def test_to_dict(self):
        c = CorrelationRefs(trace_id="t1")
        d = c.to_dict()
        assert d["trace_id"] == "t1"
        assert d["session_id"] is None


# ---------------------------------------------------------------------------
# RecordEnvelope
# ---------------------------------------------------------------------------

class TestRecordEnvelope:
    def test_minimal_valid(self):
        env = _make_envelope()
        assert env.record_type == "event"

    def test_invalid_record_type(self):
        with pytest.raises(ValidationError):
            _make_envelope(record_type="unknown_type")

    def test_invalid_completeness_marker(self):
        with pytest.raises(ValidationError):
            _make_envelope(completeness_marker="bad")

    def test_invalid_degradation_marker(self):
        with pytest.raises(ValidationError):
            _make_envelope(degradation_marker="bad_marker")

    def test_all_record_types_accepted(self):
        for rt in RECORD_TYPES:
            env = _make_envelope(record_type=rt)
            assert env.record_type == rt

    def test_to_dict_has_expected_keys(self):
        env = _make_envelope()
        d = env.to_dict()
        for key in ("record_ref", "run_ref", "record_type", "observed_at"):
            assert key in d

    def test_batch_ref_requires_stage_ref(self):
        with pytest.raises(ValidationError):
            _make_envelope(batch_execution_ref=BATCH)

    def test_batch_ref_must_share_stage_prefix(self):
        with pytest.raises(ValidationError):
            _make_envelope(
                stage_execution_ref=STAGE,
                batch_execution_ref="batch:my-proj.run-01.other.batch-0",
            )

    def test_batch_owned_operation_is_valid(self):
        env = _make_envelope(
            stage_execution_ref=STAGE,
            batch_execution_ref=BATCH,
            operation_context_ref="op:my-proj.run-01.train.batch-0.fit",
        )
        assert str(env.batch_execution_ref) == BATCH

    def test_deployment_ref_is_serialized(self):
        env = _make_envelope(deployment_execution_ref=DEPLOYMENT)
        assert str(env.deployment_execution_ref) == DEPLOYMENT
        assert env.to_dict()["deployment_execution_ref"] == DEPLOYMENT


# ---------------------------------------------------------------------------
# StructuredEventPayload / StructuredEventRecord
# ---------------------------------------------------------------------------

class TestStructuredEventRecord:
    def _make(self, **payload_overrides):
        envelope = _make_envelope(record_type="event")
        payload_defaults = dict(
            event_key="test.event",
            level="info",
            message="Something happened",
        )
        payload_defaults.update(payload_overrides)
        payload = StructuredEventPayload(**payload_defaults)
        return StructuredEventRecord(envelope=envelope, payload=payload)

    def test_valid_event(self):
        r = self._make()
        assert r.payload.event_key == "test.event"
        assert r.payload.level == "info"

    def test_invalid_level_raises(self):
        with pytest.raises(ValidationError):
            self._make(level="verbose")

    def test_all_levels_accepted(self):
        for level in EVENT_LEVELS:
            r = self._make(level=level)
            assert r.payload.level == level

    def test_to_dict_has_payload(self):
        r = self._make()
        d = r.to_dict()
        assert "payload" in d
        assert "envelope" in d


# ---------------------------------------------------------------------------
# MetricPayload / MetricRecord
# ---------------------------------------------------------------------------

class TestMetricRecord:
    def _make(self, **payload_overrides):
        envelope = _make_envelope(record_type="metric")
        payload_defaults = dict(
            metric_key="accuracy",
            value=0.95,
            value_type="float",
            aggregation_scope="run",
        )
        payload_defaults.update(payload_overrides)
        payload = MetricPayload(**payload_defaults)
        return MetricRecord(envelope=envelope, payload=payload)

    def test_valid_metric(self):
        r = self._make()
        assert r.payload.value == 0.95

    def test_invalid_aggregation_scope(self):
        with pytest.raises(ValidationError):
            self._make(aggregation_scope="bad_scope")

    def test_all_aggregation_scopes(self):
        for scope in METRIC_AGGREGATION_SCOPES:
            r = self._make(aggregation_scope=scope)
            assert r.payload.aggregation_scope == scope

    def test_to_dict_has_value(self):
        r = self._make()
        d = r.to_dict()
        assert d["payload"]["value"] == 0.95


# ---------------------------------------------------------------------------
# TraceSpanPayload / TraceSpanRecord
# ---------------------------------------------------------------------------

class TestTraceSpanRecord:
    def _make(self, **payload_overrides):
        envelope = _make_envelope(record_type="span")
        payload_defaults = dict(
            span_id="span-001",
            trace_id="trace-001",
            parent_span_id=None,
            span_name="train.forward",
            status="ok",
            span_kind="operation",
            started_at=TS,
            ended_at=TS2,
        )
        payload_defaults.update(payload_overrides)
        payload = TraceSpanPayload(**payload_defaults)
        return TraceSpanRecord(envelope=envelope, payload=payload)

    def test_valid_span(self):
        r = self._make()
        assert r.payload.status == "ok"

    def test_invalid_span_status_raises(self):
        with pytest.raises(ValidationError):
            self._make(status="pending")

    def test_invalid_span_kind_raises(self):
        with pytest.raises(ValidationError):
            self._make(span_kind="rpc")

    def test_all_span_statuses(self):
        for status in TRACE_SPAN_STATUSES:
            r = self._make(status=status)
            assert r.payload.status == status


# ---------------------------------------------------------------------------
# DegradedPayload / DegradedRecord
# ---------------------------------------------------------------------------

class TestDegradedRecord:
    def _make(self, **payload_overrides):
        envelope = _make_envelope(record_type="degraded", degradation_marker="capture_gap")
        payload_defaults = dict(
            issue_key="capture.gap",
            category="capture",
            severity="warning",
            summary="capture gap detected",
        )
        payload_defaults.update(payload_overrides)
        payload = DegradedPayload(**payload_defaults)
        return DegradedRecord(envelope=envelope, payload=payload)

    def test_valid_degraded(self):
        r = self._make()
        assert r.payload.category == "capture"

    def test_invalid_category_raises(self):
        with pytest.raises(ValidationError):
            self._make(category="unknown")

    def test_invalid_severity_raises(self):
        with pytest.raises(ValidationError):
            self._make(severity="info")

    def test_all_categories(self):
        for cat in DEGRADED_CATEGORIES:
            r = self._make(category=cat)
            assert r.payload.category == cat
