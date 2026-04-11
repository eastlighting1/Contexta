"""Canonical payload and JSON serialization helpers for Contexta contract."""

from __future__ import annotations

from dataclasses import fields
import json
import math
from typing import Any, Callable, Mapping, Sequence

from ...common.errors import SerializationError, ValidationError
from ..extensions import ExtensionFieldSet
from ..models import (
    ArtifactManifest,
    BatchExecution,
    CorrelationRefs,
    DegradedPayload,
    DegradedRecord,
    DeploymentExecution,
    EnvironmentSnapshot,
    MetricPayload,
    MetricRecord,
    OperationContext,
    Project,
    ProvenanceRecord,
    RecordEnvelope,
    Run,
    SampleObservation,
    StageExecution,
    StructuredEventPayload,
    StructuredEventRecord,
    TraceSpanPayload,
    TraceSpanRecord,
    LineageEdge,
)
from ..refs import StableRef
from ..registry import ExtensionRegistry
from ..validation import (
    validate_artifact_manifest,
    validate_batch_execution,
    validate_degraded_record,
    validate_deployment_execution,
    validate_environment_snapshot,
    validate_lineage_edge,
    validate_metric_record,
    validate_operation_context,
    validate_project,
    validate_provenance_record,
    validate_record_envelope,
    validate_run,
    validate_sample_observation,
    validate_stage_execution,
    validate_structured_event_record,
    validate_trace_span_record,
)


def _raise_serialization_error(
    message: str,
    *,
    code: str,
    details: Mapping[str, Any] | None = None,
    cause: BaseException | None = None,
) -> None:
    raise SerializationError(message, code=code, details=details, cause=cause)


def _jsonify(value: Any) -> Any:
    if isinstance(value, StableRef):
        return str(value)
    if isinstance(value, ExtensionFieldSet):
        return _jsonify(value.to_dict())
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _jsonify(value.to_dict())
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _raise_serialization_error(
                "Non-finite float values are not allowed in canonical payloads.",
                code="serialization_invalid_float",
                details={"value": value},
            )
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                _raise_serialization_error(
                    "Canonical payload mappings must use string keys.",
                    code="serialization_invalid_mapping_key",
                    details={"key": key},
                )
            item = _jsonify(value[key])
            if item is not None:
                normalized[key] = item
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_jsonify(item) for item in value]
    _raise_serialization_error(
        "Unsupported canonical serialization value.",
        code="serialization_unsupported_type",
        details={"type": type(value).__name__},
    )


def to_payload(obj: Any) -> Any:
    """Convert a canonical model into a JSON-safe payload."""

    return _jsonify(obj)


def to_json(obj: Any) -> str:
    """Convert a canonical model into deterministic canonical JSON."""

    return json.dumps(
        to_payload(obj),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _load_json_input(data: Any, *, name: str) -> Any:
    if isinstance(data, str):
        text = data.strip()
        if not text:
            _raise_serialization_error(
                f"{name} input must not be blank.",
                code="deserialize_blank_input",
                details={"name": name},
            )
        if text.startswith("{") or text.startswith("[") or text.startswith('"'):
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                _raise_serialization_error(
                    f"Invalid JSON for {name}.",
                    code="deserialize_invalid_json",
                    details={"name": name},
                    cause=exc,
                )
        return data
    return data


def _load_mapping(data: Any, *, name: str) -> dict[str, Any]:
    payload = _load_json_input(data, name=name)
    if not isinstance(payload, Mapping):
        _raise_serialization_error(
            f"{name} payload must be a mapping object.",
            code="deserialize_invalid_shape",
            details={"name": name, "type": type(payload).__name__},
        )
    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            _raise_serialization_error(
                f"{name} payload keys must be strings.",
                code="deserialize_invalid_shape",
                details={"name": name, "key": key},
            )
        normalized[key] = value
    return normalized


def _check_unknown_fields(payload: Mapping[str, Any], model_type: type[Any]) -> None:
    allowed = {field.name for field in fields(model_type)}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        _raise_serialization_error(
            f"Unknown fields for {model_type.__name__}.",
            code="deserialize_unknown_field",
            details={"model": model_type.__name__, "unknown_fields": unknown},
        )


def _construct_model(
    model_type: type[Any],
    payload: Mapping[str, Any],
    *,
    field_loaders: Mapping[str, Callable[[Any], Any]] | None = None,
) -> Any:
    _check_unknown_fields(payload, model_type)
    normalized = dict(payload)
    for field_name, loader in (field_loaders or {}).items():
        if field_name in normalized and normalized[field_name] is not None:
            normalized[field_name] = loader(normalized[field_name])
    try:
        return model_type(**normalized)
    except TypeError as exc:
        _raise_serialization_error(
            f"Invalid payload for {model_type.__name__}.",
            code="deserialize_invalid_payload",
            details={"model": model_type.__name__, "message": str(exc)},
            cause=exc,
        )
    except ValidationError:
        raise


def _run_validator(
    value: Any,
    validator: Callable[..., Any] | None,
    *,
    registry: ExtensionRegistry | None = None,
) -> None:
    if validator is None:
        return
    report = validator(value, registry=registry)
    report.raise_for_errors()


def deserialize_stable_ref(data: StableRef | str) -> StableRef:
    """Deserialize a canonical StableRef."""

    if isinstance(data, StableRef):
        return data
    raw = _load_json_input(data, name="StableRef")
    if not isinstance(raw, str):
        _raise_serialization_error(
            "StableRef input must be a canonical text string.",
            code="deserialize_invalid_shape",
            details={"name": "StableRef", "type": type(raw).__name__},
        )
    try:
        return StableRef.parse(raw)
    except ValidationError as exc:
        _raise_serialization_error(
            "Invalid StableRef text.",
            code="deserialize_invalid_ref",
            details={"value": raw},
            cause=exc,
        )


def deserialize_extension_field_set(data: Any) -> ExtensionFieldSet:
    """Deserialize an ExtensionFieldSet."""

    payload = _load_mapping(data, name="ExtensionFieldSet")
    return _construct_model(ExtensionFieldSet, payload)


def _deserialize_extensions(value: Any) -> tuple[ExtensionFieldSet, ...]:
    parsed = _load_json_input(value, name="extensions")
    if not isinstance(parsed, Sequence) or isinstance(parsed, (str, bytes, bytearray)):
        _raise_serialization_error(
            "extensions must be a sequence of extension payloads.",
            code="deserialize_invalid_shape",
            details={"name": "extensions", "type": type(parsed).__name__},
        )
    return tuple(deserialize_extension_field_set(item) for item in parsed)


def deserialize_correlation_refs(data: Any) -> CorrelationRefs:
    payload = _load_mapping(data, name="CorrelationRefs")
    return _construct_model(CorrelationRefs, payload)


def deserialize_project(data: Any, *, registry: ExtensionRegistry | None = None) -> Project:
    payload = _load_mapping(data, name="Project")
    value = _construct_model(Project, payload, field_loaders={"extensions": _deserialize_extensions})
    _run_validator(value, validate_project, registry=registry)
    return value


def deserialize_run(data: Any, *, registry: ExtensionRegistry | None = None) -> Run:
    payload = _load_mapping(data, name="Run")
    value = _construct_model(Run, payload, field_loaders={"extensions": _deserialize_extensions})
    _run_validator(value, validate_run, registry=registry)
    return value


def deserialize_deployment_execution(
    data: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> DeploymentExecution:
    payload = _load_mapping(data, name="DeploymentExecution")
    value = _construct_model(
        DeploymentExecution,
        payload,
        field_loaders={"extensions": _deserialize_extensions},
    )
    _run_validator(value, validate_deployment_execution, registry=registry)
    return value


def deserialize_stage_execution(data: Any, *, registry: ExtensionRegistry | None = None) -> StageExecution:
    payload = _load_mapping(data, name="StageExecution")
    value = _construct_model(StageExecution, payload, field_loaders={"extensions": _deserialize_extensions})
    _run_validator(value, validate_stage_execution, registry=registry)
    return value


def deserialize_batch_execution(data: Any, *, registry: ExtensionRegistry | None = None) -> BatchExecution:
    payload = _load_mapping(data, name="BatchExecution")
    value = _construct_model(BatchExecution, payload, field_loaders={"extensions": _deserialize_extensions})
    _run_validator(value, validate_batch_execution, registry=registry)
    return value


def deserialize_sample_observation(data: Any, *, registry: ExtensionRegistry | None = None) -> SampleObservation:
    payload = _load_mapping(data, name="SampleObservation")
    value = _construct_model(SampleObservation, payload, field_loaders={"extensions": _deserialize_extensions})
    _run_validator(value, validate_sample_observation, registry=registry)
    return value


def deserialize_operation_context(data: Any, *, registry: ExtensionRegistry | None = None) -> OperationContext:
    payload = _load_mapping(data, name="OperationContext")
    value = _construct_model(OperationContext, payload, field_loaders={"extensions": _deserialize_extensions})
    _run_validator(value, validate_operation_context, registry=registry)
    return value


def deserialize_environment_snapshot(
    data: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> EnvironmentSnapshot:
    payload = _load_mapping(data, name="EnvironmentSnapshot")
    value = _construct_model(
        EnvironmentSnapshot,
        payload,
        field_loaders={"extensions": _deserialize_extensions},
    )
    _run_validator(value, validate_environment_snapshot, registry=registry)
    return value


def deserialize_record_envelope(data: Any, *, registry: ExtensionRegistry | None = None) -> RecordEnvelope:
    payload = _load_mapping(data, name="RecordEnvelope")
    value = _construct_model(
        RecordEnvelope,
        payload,
        field_loaders={
            "correlation_refs": deserialize_correlation_refs,
            "extensions": _deserialize_extensions,
        },
    )
    _run_validator(value, validate_record_envelope, registry=registry)
    return value


def deserialize_structured_event_payload(data: Any) -> StructuredEventPayload:
    payload = _load_mapping(data, name="StructuredEventPayload")
    return _construct_model(StructuredEventPayload, payload)


def deserialize_metric_payload(data: Any) -> MetricPayload:
    payload = _load_mapping(data, name="MetricPayload")
    return _construct_model(MetricPayload, payload)


def deserialize_trace_span_payload(data: Any) -> TraceSpanPayload:
    payload = _load_mapping(data, name="TraceSpanPayload")
    return _construct_model(TraceSpanPayload, payload)


def deserialize_degraded_payload(data: Any) -> DegradedPayload:
    payload = _load_mapping(data, name="DegradedPayload")
    return _construct_model(DegradedPayload, payload)


def deserialize_structured_event_record(
    data: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> StructuredEventRecord:
    payload = _load_mapping(data, name="StructuredEventRecord")
    value = _construct_model(
        StructuredEventRecord,
        payload,
        field_loaders={
            "envelope": lambda item: deserialize_record_envelope(item, registry=registry),
            "payload": deserialize_structured_event_payload,
        },
    )
    _run_validator(value, validate_structured_event_record, registry=registry)
    return value


def deserialize_metric_record(
    data: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> MetricRecord:
    payload = _load_mapping(data, name="MetricRecord")
    value = _construct_model(
        MetricRecord,
        payload,
        field_loaders={
            "envelope": lambda item: deserialize_record_envelope(item, registry=registry),
            "payload": deserialize_metric_payload,
        },
    )
    _run_validator(value, validate_metric_record, registry=registry)
    return value


def deserialize_trace_span_record(
    data: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> TraceSpanRecord:
    payload = _load_mapping(data, name="TraceSpanRecord")
    value = _construct_model(
        TraceSpanRecord,
        payload,
        field_loaders={
            "envelope": lambda item: deserialize_record_envelope(item, registry=registry),
            "payload": deserialize_trace_span_payload,
        },
    )
    _run_validator(value, validate_trace_span_record, registry=registry)
    return value


def deserialize_degraded_record(
    data: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> DegradedRecord:
    payload = _load_mapping(data, name="DegradedRecord")
    value = _construct_model(
        DegradedRecord,
        payload,
        field_loaders={
            "envelope": lambda item: deserialize_record_envelope(item, registry=registry),
            "payload": deserialize_degraded_payload,
        },
    )
    _run_validator(value, validate_degraded_record, registry=registry)
    return value


def deserialize_artifact_manifest(
    data: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ArtifactManifest:
    payload = _load_mapping(data, name="ArtifactManifest")
    value = _construct_model(
        ArtifactManifest,
        payload,
        field_loaders={"extensions": _deserialize_extensions},
    )
    _run_validator(value, validate_artifact_manifest, registry=registry)
    return value


def deserialize_lineage_edge(
    data: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> LineageEdge:
    payload = _load_mapping(data, name="LineageEdge")
    value = _construct_model(
        LineageEdge,
        payload,
        field_loaders={"extensions": _deserialize_extensions},
    )
    _run_validator(value, validate_lineage_edge, registry=registry)
    return value


def deserialize_provenance_record(
    data: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ProvenanceRecord:
    payload = _load_mapping(data, name="ProvenanceRecord")
    value = _construct_model(
        ProvenanceRecord,
        payload,
        field_loaders={"extensions": _deserialize_extensions},
    )
    _run_validator(value, validate_provenance_record, registry=registry)
    return value


__all__ = [
    "deserialize_artifact_manifest",
    "deserialize_batch_execution",
    "deserialize_correlation_refs",
    "deserialize_degraded_payload",
    "deserialize_degraded_record",
    "deserialize_deployment_execution",
    "deserialize_environment_snapshot",
    "deserialize_extension_field_set",
    "deserialize_lineage_edge",
    "deserialize_metric_payload",
    "deserialize_metric_record",
    "deserialize_operation_context",
    "deserialize_project",
    "deserialize_provenance_record",
    "deserialize_record_envelope",
    "deserialize_run",
    "deserialize_sample_observation",
    "deserialize_stage_execution",
    "deserialize_stable_ref",
    "deserialize_structured_event_payload",
    "deserialize_structured_event_record",
    "deserialize_trace_span_payload",
    "deserialize_trace_span_record",
    "to_json",
    "to_payload",
]
