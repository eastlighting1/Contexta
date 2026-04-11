"""TST-006: payload/json serialize tests."""

import json

import pytest

from contexta.common.errors import SerializationError, ValidationError
from contexta.contract.models.context import DeploymentExecution, Project, Run
from contexta.contract.models.records import (
    MetricPayload,
    MetricRecord,
    RecordEnvelope,
    StructuredEventPayload,
    StructuredEventRecord,
)
from contexta.contract.serialization import (
    deserialize_deployment_execution,
    deserialize_metric_record,
    deserialize_project,
    deserialize_run,
    deserialize_structured_event_record,
    to_json,
    to_payload,
)


TS = "2024-01-01T00:00:00Z"
TS2 = "2024-01-01T01:00:00Z"


def _make_project():
    return Project(project_ref="project:my-proj", name="My Project", created_at=TS)


def _make_run():
    return Run(
        run_ref="run:my-proj.run-01",
        project_ref="project:my-proj",
        name="Run 1",
        status="open",
        started_at=TS,
    )


def _make_event_record():
    envelope = RecordEnvelope(
        record_ref="record:my-proj.run-01.ev-1",
        run_ref="run:my-proj.run-01",
        record_type="event",
        observed_at=TS,
        recorded_at=TS,
        producer_ref="contexta.test",
        completeness_marker="complete",
        degradation_marker="none",
    )
    payload = StructuredEventPayload(event_key="test.event", level="info", message="hello")
    return StructuredEventRecord(envelope=envelope, payload=payload)


def _make_metric_record():
    envelope = RecordEnvelope(
        record_ref="record:my-proj.run-01.m-1",
        run_ref="run:my-proj.run-01",
        record_type="metric",
        observed_at=TS,
        recorded_at=TS,
        producer_ref="contexta.test",
        completeness_marker="complete",
        degradation_marker="none",
    )
    payload = MetricPayload(metric_key="loss", value=0.3, value_type="float", aggregation_scope="run")
    return MetricRecord(envelope=envelope, payload=payload)


# ---------------------------------------------------------------------------
# to_payload / to_json
# ---------------------------------------------------------------------------

class TestToPayload:
    def test_project_roundtrip(self):
        p = _make_project()
        payload = to_payload(p)
        assert payload["name"] == "My Project"
        assert payload["project_ref"] == "project:my-proj"

    def test_to_json_is_valid_json_string(self):
        p = _make_project()
        json_str = to_json(p)
        parsed = json.loads(json_str)
        assert parsed["name"] == "My Project"

    def test_non_finite_float_raises(self):
        import math
        with pytest.raises(SerializationError):
            to_payload({"value": math.inf})

    def test_mapping_keys_must_be_strings(self):
        with pytest.raises(SerializationError):
            to_payload({1: "value"})


# ---------------------------------------------------------------------------
# deserialize_project / deserialize_run
# ---------------------------------------------------------------------------

class TestDeserializeProject:
    def test_roundtrip(self):
        p = _make_project()
        payload = to_payload(p)
        restored = deserialize_project(payload)
        assert str(restored.project_ref) == str(p.project_ref)
        assert restored.name == p.name

    def test_from_json_string(self):
        p = _make_project()
        json_str = to_json(p)
        restored = deserialize_project(json.loads(json_str))
        assert restored.name == "My Project"

    def test_missing_required_field_raises(self):
        from contexta.common.errors import SerializationError
        payload = to_payload(_make_project())
        del payload["name"]
        with pytest.raises((ValidationError, KeyError, TypeError, SerializationError)):
            deserialize_project(payload)


class TestDeserializeRun:
    def test_roundtrip(self):
        r = _make_run()
        payload = to_payload(r)
        restored = deserialize_run(payload)
        assert str(restored.run_ref) == str(r.run_ref)
        assert restored.status == "open"


class TestDeserializeDeployment:
    def test_roundtrip(self):
        deployment = DeploymentExecution(
            deployment_execution_ref="deployment:my-proj.recommendation-api",
            project_ref="project:my-proj",
            deployment_name="recommendation-api",
            status="open",
            started_at=TS,
            run_ref="run:my-proj.run-01",
            artifact_ref="artifact:my-proj.run-01.model",
        )
        payload = to_payload(deployment)
        restored = deserialize_deployment_execution(payload)
        assert str(restored.deployment_execution_ref) == "deployment:my-proj.recommendation-api"
        assert str(restored.run_ref) == "run:my-proj.run-01"


# ---------------------------------------------------------------------------
# deserialize_structured_event_record / deserialize_metric_record
# ---------------------------------------------------------------------------

class TestDeserializeRecords:
    def test_event_record_roundtrip(self):
        r = _make_event_record()
        payload = to_payload(r)
        restored = deserialize_structured_event_record(payload)
        assert restored.payload.event_key == "test.event"
        assert restored.payload.level == "info"

    def test_metric_record_roundtrip(self):
        r = _make_metric_record()
        payload = to_payload(r)
        restored = deserialize_metric_record(payload)
        assert restored.payload.metric_key == "loss"
        assert restored.payload.value == pytest.approx(0.3)
