"""TST-005: validator success/failure cases."""

import pytest

from contexta.common.errors import ValidationError
from contexta.contract.models.context import DeploymentExecution, OperationContext, Project, Run, StageExecution
from contexta.contract.models.records import (
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
from contexta.contract.models.artifacts import ArtifactManifest
from contexta.contract.models.lineage import LineageEdge, ProvenanceRecord
from contexta.contract.validation import (
    validate_artifact_manifest,
    validate_degraded_record,
    validate_deployment_execution,
    validate_metric_record,
    validate_project,
    validate_run,
    validate_stage_execution,
    validate_structured_event_record,
    validate_trace_span_record,
)
from contexta.contract.validation.report import ValidationIssue, ValidationReport


TS = "2024-01-01T00:00:00Z"
TS2 = "2024-01-01T01:00:00Z"


# ---------------------------------------------------------------------------
# ValidationIssue
# ---------------------------------------------------------------------------

class TestValidationIssue:
    def test_valid_error(self):
        issue = ValidationIssue(code="err.code", path="$.field", message="Bad value", severity="error")
        assert issue.is_error

    def test_valid_warning(self):
        issue = ValidationIssue(code="warn.code", path="$", message="Note", severity="warning")
        assert not issue.is_error

    def test_blank_code_raises(self):
        with pytest.raises(ValidationError):
            ValidationIssue(code="", path="$", message="msg")

    def test_blank_path_raises(self):
        with pytest.raises(ValidationError):
            ValidationIssue(code="code", path="", message="msg")

    def test_blank_message_raises(self):
        with pytest.raises(ValidationError):
            ValidationIssue(code="code", path="$", message="")

    def test_invalid_severity_raises(self):
        with pytest.raises(ValidationError):
            ValidationIssue(code="code", path="$", message="msg", severity="critical")

    def test_with_prefix(self):
        issue = ValidationIssue(code="c", path="$.foo", message="msg")
        prefixed = issue.with_prefix("$.root")
        assert prefixed.path == "$.root.foo"

    def test_to_dict(self):
        issue = ValidationIssue(code="c", path="$", message="msg")
        d = issue.to_dict()
        assert d["code"] == "c"
        assert d["severity"] == "error"


# ---------------------------------------------------------------------------
# ValidationReport
# ---------------------------------------------------------------------------

class TestValidationReport:
    def test_ok_report(self):
        r = ValidationReport.ok()
        assert r.valid
        assert len(r.issues) == 0

    def test_from_issues_with_error_is_invalid(self):
        issue = ValidationIssue(code="c", path="$", message="bad")
        r = ValidationReport.from_issues([issue])
        assert not r.valid

    def test_from_issues_warning_only_is_valid(self):
        issue = ValidationIssue(code="c", path="$", message="note", severity="warning")
        r = ValidationReport.from_issues([issue])
        assert r.valid

    def test_errors_and_warnings_properties(self):
        err = ValidationIssue(code="e", path="$", message="err")
        warn = ValidationIssue(code="w", path="$", message="warn", severity="warning")
        r = ValidationReport.from_issues([err, warn])
        assert len(r.errors) == 1
        assert len(r.warnings) == 1

    def test_merge(self):
        r1 = ValidationReport.from_issues([ValidationIssue(code="e1", path="$", message="e1")])
        r2 = ValidationReport.from_issues([ValidationIssue(code="e2", path="$", message="e2")])
        merged = ValidationReport.merge(r1, r2)
        assert len(merged.issues) == 2

    def test_prefixed(self):
        r = ValidationReport.from_issues([ValidationIssue(code="c", path="$.foo", message="msg")])
        prefixed = r.prefixed("$.root")
        assert prefixed.issues[0].path == "$.root.foo"

    def test_raise_for_errors(self):
        r = ValidationReport.from_issues([ValidationIssue(code="c", path="$", message="bad")])
        with pytest.raises(ValidationError):
            r.raise_for_errors()

    def test_raise_for_errors_ok_no_raise(self):
        ValidationReport.ok().raise_for_errors()

    def test_to_dict(self):
        r = ValidationReport.ok()
        d = r.to_dict()
        assert d["valid"] is True
        assert d["issues"] == []


# ---------------------------------------------------------------------------
# validate_project
# ---------------------------------------------------------------------------

class TestValidateProject:
    def test_valid_project(self):
        p = Project(project_ref="project:my-proj", name="X", created_at=TS)
        report = validate_project(p)
        assert report.valid

    def test_schema_version_mismatch(self):
        p = Project(project_ref="project:my-proj", name="X", created_at=TS)
        # forcibly inject wrong schema version
        object.__setattr__(p, "schema_version", "0.9.0")
        report = validate_project(p)
        assert not report.valid
        assert any("schema_version" in issue.path for issue in report.issues)


# ---------------------------------------------------------------------------
# validate_run
# ---------------------------------------------------------------------------

class TestValidateRun:
    def test_valid_run(self):
        r = Run(
            run_ref="run:my-proj.run-01",
            project_ref="project:my-proj",
            name="R",
            status="open",
            started_at=TS,
        )
        report = validate_run(r)
        assert report.valid


class TestValidateDeploymentExecution:
    def test_valid_deployment(self):
        deployment = DeploymentExecution(
            deployment_execution_ref="deployment:my-proj.recommendation-api",
            project_ref="project:my-proj",
            deployment_name="recommendation-api",
            status="open",
            started_at=TS,
            run_ref="run:my-proj.run-01",
        )
        report = validate_deployment_execution(deployment)
        assert report.valid


# ---------------------------------------------------------------------------
# validate_structured_event_record
# ---------------------------------------------------------------------------

class TestValidateStructuredEventRecord:
    def test_valid_event(self):
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
        payload = StructuredEventPayload(event_key="test.event", level="info", message="ok")
        rec = StructuredEventRecord(envelope=envelope, payload=payload)
        report = validate_structured_event_record(rec)
        assert report.valid


# ---------------------------------------------------------------------------
# validate_metric_record
# ---------------------------------------------------------------------------

class TestValidateMetricRecord:
    def test_valid_metric(self):
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
        payload = MetricPayload(metric_key="accuracy", value=0.9, value_type="float", aggregation_scope="run")
        rec = MetricRecord(envelope=envelope, payload=payload)
        report = validate_metric_record(rec)
        assert report.valid
