"""Canonical record-family models for Contexta contract."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping, Sequence
import re

from ...common.errors import ValidationError
from ..extensions import ExtensionFieldSet, _freeze_json_value, _thaw_json_value
from ..refs import CORE_STABLE_REF_KINDS, StableRef, validate_core_stable_ref, validate_stable_ref_kind
from .context import (
    DEFAULT_CONTRACT_SCHEMA_VERSION,
    _coerce_ref,
    _normalize_extensions,
    _normalize_required_string,
    _normalize_string_mapping,
    _normalize_timestamp_field,
)


RECORD_TYPES = ("event", "metric", "span", "degraded")
COMPLETENESS_MARKERS = ("complete", "partial", "sampled", "absent", "unknown")
DEGRADATION_MARKERS = ("none", "partial_failure", "capture_gap", "import_loss", "compatibility_upgrade")
ORIGIN_MARKERS = ("explicit_capture", "assisted_capture", "wrapped_capture", "imported", "inferred", "replayed")
EVENT_LEVELS = ("debug", "info", "warning", "error", "critical")
METRIC_AGGREGATION_SCOPES = ("run", "stage", "operation", "step", "slice")
TRACE_SPAN_STATUSES = ("ok", "error", "cancelled", "timeout")
TRACE_SPAN_KINDS = ("operation", "internal", "io", "network", "process")
DEGRADED_CATEGORIES = ("capture", "store", "import", "compatibility", "verification", "recovery")
DEGRADED_SEVERITIES = ("warning", "error")

PRODUCER_REF_PATTERN = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)*$")
DOT_TOKEN_PATTERN = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)*$")
LOWER_SNAKE_TOKEN_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
LOWER_DOT_OR_SNAKE_TOKEN_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")


def _raise_record_error(
    message: str,
    *,
    code: str,
    details: Mapping[str, Any] | None = None,
) -> None:
    raise ValidationError(message, code=code, details=details)


def _normalize_marker(field_name: str, value: str, allowed: Sequence[str]) -> str:
    text = _normalize_required_string(field_name, value)
    if text not in allowed:
        _raise_record_error(
            f"{field_name} must be one of the canonical values.",
            code="record_invalid_marker",
            details={"field_name": field_name, "value": text, "allowed": tuple(allowed)},
        )
    return text


def _normalize_optional_nonblank_string(field_name: str, value: str | None) -> str | None:
    if value is None:
        return None
    return _normalize_required_string(field_name, value)


def _normalize_token(field_name: str, value: str, *, pattern: re.Pattern[str], code: str) -> str:
    text = _normalize_required_string(field_name, value)
    if not pattern.fullmatch(text):
        _raise_record_error(
            f"Invalid {field_name}.",
            code=code,
            details={"field_name": field_name, "value": text},
        )
    return text


def _normalize_ref_text(field_name: str, value: StableRef | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, StableRef):
        ref = value
    elif isinstance(value, str):
        ref = StableRef.parse(value)
    else:
        _raise_record_error(
            f"{field_name} must be a StableRef, string, or None.",
            code="record_invalid_ref",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    if ref.kind in CORE_STABLE_REF_KINDS:
        validate_core_stable_ref(ref)
    return str(ref)


def _normalize_ref_tuple(field_name: str, values: Sequence[StableRef | str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    normalized: list[str] = []
    for index, value in enumerate(values):
        ref_text = _normalize_ref_text(f"{field_name}[{index}]", value)
        assert ref_text is not None
        normalized.append(ref_text)
    return tuple(normalized)


def _normalize_json_mapping(field_name: str, value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        _raise_record_error(
            f"{field_name} must be a mapping.",
            code="record_invalid_mapping",
            details={"field_name": field_name, "type": type(value).__name__},
        )

    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            _raise_record_error(
                f"{field_name} contains an invalid key.",
                code="record_invalid_mapping",
                details={"field_name": field_name, "key": key},
            )
        normalized[key.strip()] = _freeze_json_value(item, path=f"{field_name}.{key.strip()}")
    return MappingProxyType({key: normalized[key] for key in sorted(normalized)})


def _serialize_json_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _thaw_json_value(value) for key, value in mapping.items()}


@dataclass(frozen=True, slots=True)
class CorrelationRefs:
    """Correlation identifiers shared by record families."""

    trace_id: str | None = None
    session_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _normalize_optional_nonblank_string("trace_id", self.trace_id))
        object.__setattr__(self, "session_id", _normalize_optional_nonblank_string("session_id", self.session_id))

    def to_dict(self) -> dict[str, str | None]:
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
        }


@dataclass(frozen=True, slots=True)
class RecordEnvelope:
    """Common envelope shared by all record families."""

    record_ref: StableRef | str
    record_type: str
    recorded_at: str
    observed_at: str
    producer_ref: str
    run_ref: StableRef | str
    deployment_execution_ref: StableRef | str | None = None
    stage_execution_ref: StableRef | str | None = None
    batch_execution_ref: StableRef | str | None = None
    sample_observation_ref: StableRef | str | None = None
    operation_context_ref: StableRef | str | None = None
    correlation_refs: CorrelationRefs = CorrelationRefs()
    completeness_marker: str = "complete"
    degradation_marker: str = "none"
    schema_version: str = DEFAULT_CONTRACT_SCHEMA_VERSION
    extensions: tuple[ExtensionFieldSet, ...] = ()

    def __post_init__(self) -> None:
        record_ref = _coerce_ref("record_ref", self.record_ref)
        validate_core_stable_ref(record_ref)
        validate_stable_ref_kind(record_ref, "record", field_name="record_ref")

        run_ref = _coerce_ref("run_ref", self.run_ref)
        validate_core_stable_ref(run_ref)
        validate_stable_ref_kind(run_ref, "run", field_name="run_ref")

        deployment_execution_ref = None if self.deployment_execution_ref is None else _coerce_ref(
            "deployment_execution_ref",
            self.deployment_execution_ref,
        )
        if deployment_execution_ref is not None:
            validate_core_stable_ref(deployment_execution_ref)
            validate_stable_ref_kind(
                deployment_execution_ref,
                "deployment",
                field_name="deployment_execution_ref",
            )

        stage_execution_ref = None if self.stage_execution_ref is None else _coerce_ref(
            "stage_execution_ref",
            self.stage_execution_ref,
        )
        if stage_execution_ref is not None:
            validate_core_stable_ref(stage_execution_ref)
            validate_stable_ref_kind(stage_execution_ref, "stage", field_name="stage_execution_ref")

        batch_execution_ref = None if self.batch_execution_ref is None else _coerce_ref(
            "batch_execution_ref",
            self.batch_execution_ref,
        )
        if batch_execution_ref is not None:
            validate_core_stable_ref(batch_execution_ref)
            validate_stable_ref_kind(batch_execution_ref, "batch", field_name="batch_execution_ref")

        sample_observation_ref = None if self.sample_observation_ref is None else _coerce_ref(
            "sample_observation_ref",
            self.sample_observation_ref,
        )
        if sample_observation_ref is not None:
            validate_core_stable_ref(sample_observation_ref)
            validate_stable_ref_kind(sample_observation_ref, "sample", field_name="sample_observation_ref")

        operation_context_ref = None if self.operation_context_ref is None else _coerce_ref(
            "operation_context_ref",
            self.operation_context_ref,
        )
        if operation_context_ref is not None:
            validate_core_stable_ref(operation_context_ref)
            validate_stable_ref_kind(operation_context_ref, "op", field_name="operation_context_ref")

        record_type = _normalize_marker("record_type", self.record_type, RECORD_TYPES)
        recorded_at = _normalize_timestamp_field("recorded_at", self.recorded_at)
        observed_at = _normalize_timestamp_field("observed_at", self.observed_at)
        producer_ref = _normalize_token(
            "producer_ref",
            self.producer_ref,
            pattern=PRODUCER_REF_PATTERN,
            code="record_invalid_producer_ref",
        )
        completeness_marker = _normalize_marker(
            "completeness_marker",
            self.completeness_marker,
            COMPLETENESS_MARKERS,
        )
        degradation_marker = _normalize_marker(
            "degradation_marker",
            self.degradation_marker,
            DEGRADATION_MARKERS,
        )
        schema_version = _normalize_required_string("schema_version", self.schema_version)

        if record_ref.components[0:2] != run_ref.components:
            _raise_record_error(
                "record_ref must share the same run prefix as run_ref.",
                code="record_ref_prefix_mismatch",
                details={"record_ref": str(record_ref), "run_ref": str(run_ref)},
            )
        if recorded_at < observed_at:
            _raise_record_error(
                "recorded_at must be greater than or equal to observed_at.",
                code="record_invalid_time_order",
                details={"recorded_at": recorded_at, "observed_at": observed_at},
            )
        if stage_execution_ref is not None and stage_execution_ref.components[0:2] != run_ref.components:
            _raise_record_error(
                "stage_execution_ref must share the same run prefix as run_ref.",
                code="record_ref_prefix_mismatch",
                details={"stage_execution_ref": str(stage_execution_ref), "run_ref": str(run_ref)},
            )
        if batch_execution_ref is not None and stage_execution_ref is None:
            _raise_record_error(
                "batch_execution_ref requires stage_execution_ref.",
                code="record_missing_stage_context",
            )
        if batch_execution_ref is not None and stage_execution_ref is not None:
            if batch_execution_ref.components[0:3] != stage_execution_ref.components:
                _raise_record_error(
                    "batch_execution_ref must share the same stage prefix as stage_execution_ref.",
                    code="record_ref_prefix_mismatch",
                    details={
                        "batch_execution_ref": str(batch_execution_ref),
                        "stage_execution_ref": str(stage_execution_ref),
                    },
                )
        if sample_observation_ref is not None and stage_execution_ref is None:
            _raise_record_error(
                "sample_observation_ref requires stage_execution_ref.",
                code="record_missing_stage_context",
            )
        if sample_observation_ref is not None and stage_execution_ref is not None:
            expected_prefix = batch_execution_ref.components if batch_execution_ref is not None else stage_execution_ref.components
            if sample_observation_ref.components[: len(expected_prefix)] != expected_prefix:
                _raise_record_error(
                    "sample_observation_ref must share the same owning prefix as stage/batch context.",
                    code="record_ref_prefix_mismatch",
                    details={
                        "sample_observation_ref": str(sample_observation_ref),
                        "owner_ref": str(batch_execution_ref or stage_execution_ref),
                    },
                )
        if operation_context_ref is not None and stage_execution_ref is None:
            _raise_record_error(
                "operation_context_ref requires stage_execution_ref.",
                code="record_missing_stage_context",
            )
        if operation_context_ref is not None and stage_execution_ref is not None:
            expected_prefix = batch_execution_ref.components if batch_execution_ref is not None else stage_execution_ref.components
            if operation_context_ref.components[: len(expected_prefix)] != expected_prefix:
                _raise_record_error(
                    "operation_context_ref must share the same owning prefix as stage/batch context.",
                    code="record_ref_prefix_mismatch",
                    details={
                        "operation_context_ref": str(operation_context_ref),
                        "owner_ref": str(batch_execution_ref or stage_execution_ref),
                    },
                )

        correlation_refs = self.correlation_refs
        if not isinstance(correlation_refs, CorrelationRefs):
            _raise_record_error(
                "correlation_refs must be CorrelationRefs.",
                code="record_invalid_correlation_refs",
                details={"type": type(correlation_refs).__name__},
            )

        object.__setattr__(self, "record_ref", record_ref)
        object.__setattr__(self, "record_type", record_type)
        object.__setattr__(self, "recorded_at", recorded_at)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "producer_ref", producer_ref)
        object.__setattr__(self, "run_ref", run_ref)
        object.__setattr__(self, "deployment_execution_ref", deployment_execution_ref)
        object.__setattr__(self, "stage_execution_ref", stage_execution_ref)
        object.__setattr__(self, "batch_execution_ref", batch_execution_ref)
        object.__setattr__(self, "sample_observation_ref", sample_observation_ref)
        object.__setattr__(self, "operation_context_ref", operation_context_ref)
        object.__setattr__(self, "completeness_marker", completeness_marker)
        object.__setattr__(self, "degradation_marker", degradation_marker)
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "extensions", _normalize_extensions(self.extensions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_ref": str(self.record_ref),
            "record_type": self.record_type,
            "recorded_at": self.recorded_at,
            "observed_at": self.observed_at,
            "producer_ref": self.producer_ref,
            "run_ref": str(self.run_ref),
            "deployment_execution_ref": None
            if self.deployment_execution_ref is None
            else str(self.deployment_execution_ref),
            "stage_execution_ref": None if self.stage_execution_ref is None else str(self.stage_execution_ref),
            "batch_execution_ref": None if self.batch_execution_ref is None else str(self.batch_execution_ref),
            "sample_observation_ref": None
            if self.sample_observation_ref is None
            else str(self.sample_observation_ref),
            "operation_context_ref": None if self.operation_context_ref is None else str(self.operation_context_ref),
            "correlation_refs": self.correlation_refs.to_dict(),
            "completeness_marker": self.completeness_marker,
            "degradation_marker": self.degradation_marker,
            "schema_version": self.schema_version,
            "extensions": [extension.to_dict() for extension in self.extensions],
        }


@dataclass(frozen=True, slots=True)
class StructuredEventPayload:
    """Structured event payload."""

    event_key: str
    level: str
    message: str
    subject_ref: StableRef | str | None = None
    attributes: Mapping[str, Any] | None = None
    origin_marker: str = "explicit_capture"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "event_key",
            _normalize_token("event_key", self.event_key, pattern=DOT_TOKEN_PATTERN, code="record_invalid_event_key"),
        )
        object.__setattr__(self, "level", _normalize_marker("level", self.level, EVENT_LEVELS))
        object.__setattr__(self, "message", _normalize_required_string("message", self.message))
        object.__setattr__(self, "subject_ref", _normalize_ref_text("subject_ref", self.subject_ref))
        object.__setattr__(self, "attributes", _normalize_json_mapping("attributes", self.attributes))
        object.__setattr__(self, "origin_marker", _normalize_marker("origin_marker", self.origin_marker, ORIGIN_MARKERS))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_key": self.event_key,
            "level": self.level,
            "message": self.message,
            "subject_ref": self.subject_ref,
            "attributes": _serialize_json_mapping(self.attributes),
            "origin_marker": self.origin_marker,
        }


@dataclass(frozen=True, slots=True)
class MetricPayload:
    """Metric payload."""

    metric_key: str
    value: int | float
    value_type: str
    unit: str | None = None
    aggregation_scope: str = "step"
    subject_ref: StableRef | str | None = None
    slice_ref: str | None = None
    tags: Mapping[str, str] | None = None
    summary_basis: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "metric_key",
            _normalize_token("metric_key", self.metric_key, pattern=DOT_TOKEN_PATTERN, code="record_invalid_metric_key"),
        )
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool) or not math.isfinite(self.value):
            _raise_record_error(
                "Metric value must be a finite numeric value.",
                code="record_invalid_metric_value",
                details={"value": self.value},
            )
        object.__setattr__(self, "value_type", _normalize_token("value_type", self.value_type, pattern=LOWER_SNAKE_TOKEN_PATTERN, code="record_invalid_value_type"))
        object.__setattr__(self, "unit", _normalize_optional_nonblank_string("unit", self.unit))
        object.__setattr__(self, "aggregation_scope", _normalize_marker("aggregation_scope", self.aggregation_scope, METRIC_AGGREGATION_SCOPES))
        object.__setattr__(self, "subject_ref", _normalize_ref_text("subject_ref", self.subject_ref))
        if self.slice_ref is None:
            object.__setattr__(self, "slice_ref", None)
        else:
            object.__setattr__(
                self,
                "slice_ref",
                _normalize_token(
                    "slice_ref",
                    self.slice_ref,
                    pattern=LOWER_DOT_OR_SNAKE_TOKEN_PATTERN,
                    code="record_invalid_slice_ref",
                ),
            )
        object.__setattr__(self, "tags", _normalize_string_mapping("tags", self.tags))
        if self.summary_basis is None:
            object.__setattr__(self, "summary_basis", None)
        else:
            object.__setattr__(
                self,
                "summary_basis",
                _normalize_token(
                    "summary_basis",
                    self.summary_basis,
                    pattern=LOWER_SNAKE_TOKEN_PATTERN,
                    code="record_invalid_summary_basis",
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_key": self.metric_key,
            "value": self.value,
            "value_type": self.value_type,
            "unit": self.unit,
            "aggregation_scope": self.aggregation_scope,
            "subject_ref": self.subject_ref,
            "slice_ref": self.slice_ref,
            "tags": dict(self.tags),
            "summary_basis": self.summary_basis,
        }


@dataclass(frozen=True, slots=True)
class TraceSpanPayload:
    """Trace/span payload."""

    span_id: str
    trace_id: str
    parent_span_id: str | None
    span_name: str
    started_at: str
    ended_at: str
    status: str
    span_kind: str
    attributes: Mapping[str, Any] | None = None
    linked_refs: tuple[StableRef | str, ...] = ()

    def __post_init__(self) -> None:
        started_at = _normalize_timestamp_field("started_at", self.started_at)
        ended_at = _normalize_timestamp_field("ended_at", self.ended_at)
        if ended_at < started_at:
            _raise_record_error(
                "TraceSpanPayload.ended_at must be greater than or equal to started_at.",
                code="record_invalid_time_order",
                details={"started_at": started_at, "ended_at": ended_at},
            )

        object.__setattr__(self, "span_id", _normalize_required_string("span_id", self.span_id))
        object.__setattr__(self, "trace_id", _normalize_required_string("trace_id", self.trace_id))
        object.__setattr__(self, "parent_span_id", _normalize_optional_nonblank_string("parent_span_id", self.parent_span_id))
        object.__setattr__(self, "span_name", _normalize_required_string("span_name", self.span_name))
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "ended_at", ended_at)
        object.__setattr__(self, "status", _normalize_marker("status", self.status, TRACE_SPAN_STATUSES))
        object.__setattr__(self, "span_kind", _normalize_marker("span_kind", self.span_kind, TRACE_SPAN_KINDS))
        object.__setattr__(self, "attributes", _normalize_json_mapping("attributes", self.attributes))
        object.__setattr__(self, "linked_refs", _normalize_ref_tuple("linked_refs", self.linked_refs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "span_name": self.span_name,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status,
            "span_kind": self.span_kind,
            "attributes": _serialize_json_mapping(self.attributes),
            "linked_refs": list(self.linked_refs),
        }


@dataclass(frozen=True, slots=True)
class DegradedPayload:
    """Payload used to describe known gaps or degraded capture conditions."""

    issue_key: str
    category: str
    severity: str
    summary: str
    subject_ref: StableRef | str | None = None
    origin_marker: str = "explicit_capture"
    attributes: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "issue_key",
            _normalize_token("issue_key", self.issue_key, pattern=LOWER_DOT_OR_SNAKE_TOKEN_PATTERN, code="record_invalid_issue_key"),
        )
        object.__setattr__(self, "category", _normalize_marker("category", self.category, DEGRADED_CATEGORIES))
        object.__setattr__(self, "severity", _normalize_marker("severity", self.severity, DEGRADED_SEVERITIES))
        object.__setattr__(self, "summary", _normalize_required_string("summary", self.summary))
        object.__setattr__(self, "subject_ref", _normalize_ref_text("subject_ref", self.subject_ref))
        object.__setattr__(self, "origin_marker", _normalize_marker("origin_marker", self.origin_marker, ORIGIN_MARKERS))
        object.__setattr__(self, "attributes", _normalize_json_mapping("attributes", self.attributes))

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_key": self.issue_key,
            "category": self.category,
            "severity": self.severity,
            "summary": self.summary,
            "subject_ref": self.subject_ref,
            "origin_marker": self.origin_marker,
            "attributes": _serialize_json_mapping(self.attributes),
        }


def _validate_record_wrapper(
    *,
    envelope: RecordEnvelope,
    expected_type: str,
) -> None:
    if not isinstance(envelope, RecordEnvelope):
        _raise_record_error(
            "record envelope must be RecordEnvelope.",
            code="record_invalid_envelope",
            details={"type": type(envelope).__name__},
        )
    if envelope.record_type != expected_type:
        _raise_record_error(
            "Record envelope type does not match payload family.",
            code="record_type_mismatch",
            details={"expected": expected_type, "actual": envelope.record_type},
        )
    if expected_type in {"event", "metric", "span"} and envelope.completeness_marker == "absent":
        _raise_record_error(
            "event/metric/span records cannot use completeness_marker='absent'.",
            code="record_absent_not_allowed",
            details={"record_type": expected_type},
        )
    if expected_type == "degraded" and envelope.degradation_marker == "none":
        _raise_record_error(
            "degraded records must carry a non-'none' degradation marker.",
            code="record_degraded_requires_gap",
        )


@dataclass(frozen=True, slots=True)
class StructuredEventRecord:
    """Envelope + structured event payload."""

    envelope: RecordEnvelope
    payload: StructuredEventPayload

    def __post_init__(self) -> None:
        _validate_record_wrapper(envelope=self.envelope, expected_type="event")
        if not isinstance(self.payload, StructuredEventPayload):
            _raise_record_error("payload must be StructuredEventPayload.", code="record_invalid_payload")

    def to_dict(self) -> dict[str, Any]:
        return {"envelope": self.envelope.to_dict(), "payload": self.payload.to_dict()}


@dataclass(frozen=True, slots=True)
class MetricRecord:
    """Envelope + metric payload."""

    envelope: RecordEnvelope
    payload: MetricPayload

    def __post_init__(self) -> None:
        _validate_record_wrapper(envelope=self.envelope, expected_type="metric")
        if not isinstance(self.payload, MetricPayload):
            _raise_record_error("payload must be MetricPayload.", code="record_invalid_payload")

    def to_dict(self) -> dict[str, Any]:
        return {"envelope": self.envelope.to_dict(), "payload": self.payload.to_dict()}


@dataclass(frozen=True, slots=True)
class TraceSpanRecord:
    """Envelope + trace span payload."""

    envelope: RecordEnvelope
    payload: TraceSpanPayload

    def __post_init__(self) -> None:
        _validate_record_wrapper(envelope=self.envelope, expected_type="span")
        if not isinstance(self.payload, TraceSpanPayload):
            _raise_record_error("payload must be TraceSpanPayload.", code="record_invalid_payload")

    def to_dict(self) -> dict[str, Any]:
        return {"envelope": self.envelope.to_dict(), "payload": self.payload.to_dict()}


@dataclass(frozen=True, slots=True)
class DegradedRecord:
    """Envelope + degraded payload."""

    envelope: RecordEnvelope
    payload: DegradedPayload

    def __post_init__(self) -> None:
        _validate_record_wrapper(envelope=self.envelope, expected_type="degraded")
        if not isinstance(self.payload, DegradedPayload):
            _raise_record_error("payload must be DegradedPayload.", code="record_invalid_payload")

    def to_dict(self) -> dict[str, Any]:
        return {"envelope": self.envelope.to_dict(), "payload": self.payload.to_dict()}


__all__ = [
    "COMPLETENESS_MARKERS",
    "CorrelationRefs",
    "DEGRADATION_MARKERS",
    "DEGRADED_CATEGORIES",
    "DEGRADED_SEVERITIES",
    "EVENT_LEVELS",
    "DegradedPayload",
    "DegradedRecord",
    "METRIC_AGGREGATION_SCOPES",
    "MetricPayload",
    "MetricRecord",
    "ORIGIN_MARKERS",
    "PRODUCER_REF_PATTERN",
    "RECORD_TYPES",
    "RecordEnvelope",
    "StructuredEventPayload",
    "StructuredEventRecord",
    "TRACE_SPAN_KINDS",
    "TRACE_SPAN_STATUSES",
    "TraceSpanPayload",
    "TraceSpanRecord",
]
