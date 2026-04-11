"""Batch input models for Contexta capture helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping

from ..common.errors import ValidationError
from ..common.time import normalize_timestamp
from ..contract import StableRef
from ..contract.models.records import (
    DOT_TOKEN_PATTERN,
    EVENT_LEVELS,
    LOWER_SNAKE_TOKEN_PATTERN,
    METRIC_AGGREGATION_SCOPES,
    TRACE_SPAN_KINDS,
    TRACE_SPAN_STATUSES,
)


def _raise_capture_model_error(
    message: str,
    *,
    code: str,
    details: Mapping[str, Any] | None = None,
) -> None:
    raise ValidationError(message, code=code, details=details)


def _normalize_required_string(field_name: str, value: str) -> str:
    if not isinstance(value, str):
        _raise_capture_model_error(
            f"{field_name} must be a string.",
            code="capture_model_invalid_string",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    text = value.strip()
    if not text:
        _raise_capture_model_error(
            f"{field_name} must not be blank.",
            code="capture_model_invalid_string",
            details={"field_name": field_name},
        )
    return text


def _normalize_optional_string(field_name: str, value: str | None) -> str | None:
    if value is None:
        return None
    return _normalize_required_string(field_name, value)


def _normalize_marker(field_name: str, value: str, allowed: tuple[str, ...]) -> str:
    text = _normalize_required_string(field_name, value)
    if text not in allowed:
        _raise_capture_model_error(
            f"{field_name} must be one of the canonical values.",
            code="capture_model_invalid_marker",
            details={"field_name": field_name, "value": text, "allowed": allowed},
        )
    return text


def _normalize_token(field_name: str, value: str, pattern: Any, *, code: str) -> str:
    text = _normalize_required_string(field_name, value)
    if not pattern.fullmatch(text):
        _raise_capture_model_error(
            f"Invalid {field_name}.",
            code=code,
            details={"field_name": field_name, "value": text},
        )
    return text


def _freeze_json_value(value: Any, *, path: str) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and not math.isfinite(value):
            _raise_capture_model_error(
                f"{path} must be JSON-safe.",
                code="capture_model_invalid_json_value",
                details={"path": path, "value": value},
            )
        return value

    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                _raise_capture_model_error(
                    f"{path} contains an invalid key.",
                    code="capture_model_invalid_mapping",
                    details={"path": path, "key": key},
                )
            key_text = key.strip()
            normalized[key_text] = _freeze_json_value(item, path=f"{path}.{key_text}")
        return MappingProxyType({key: normalized[key] for key in sorted(normalized)})

    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_value(item, path=f"{path}[{index}]") for index, item in enumerate(value))

    _raise_capture_model_error(
        f"{path} must be JSON-safe.",
        code="capture_model_invalid_json_value",
        details={"path": path, "type": type(value).__name__},
    )


def _thaw_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json_value(item) for item in value]
    return value


def _normalize_json_mapping(field_name: str, mapping: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if mapping is None:
        return MappingProxyType({})
    if not isinstance(mapping, Mapping):
        _raise_capture_model_error(
            f"{field_name} must be a mapping.",
            code="capture_model_invalid_mapping",
            details={"field_name": field_name, "type": type(mapping).__name__},
        )

    normalized: dict[str, Any] = {}
    for key, value in mapping.items():
        if not isinstance(key, str) or not key.strip():
            _raise_capture_model_error(
                f"{field_name} contains an invalid key.",
                code="capture_model_invalid_mapping",
                details={"field_name": field_name, "key": key},
            )
        key_text = key.strip()
        normalized[key_text] = _freeze_json_value(value, path=f"{field_name}.{key_text}")
    return MappingProxyType({key: normalized[key] for key in sorted(normalized)})


def _normalize_string_mapping(field_name: str, mapping: Mapping[str, str] | None) -> Mapping[str, str]:
    if mapping is None:
        return MappingProxyType({})
    if not isinstance(mapping, Mapping):
        _raise_capture_model_error(
            f"{field_name} must be a mapping.",
            code="capture_model_invalid_mapping",
            details={"field_name": field_name, "type": type(mapping).__name__},
        )

    normalized: dict[str, str] = {}
    for key, value in mapping.items():
        if not isinstance(key, str) or not key.strip():
            _raise_capture_model_error(
                f"{field_name} contains an invalid key.",
                code="capture_model_invalid_mapping",
                details={"field_name": field_name, "key": key},
            )
        key_text = key.strip()
        normalized[key_text] = _normalize_required_string(f"{field_name}.{key_text}", value)
    return MappingProxyType({key: normalized[key] for key in sorted(normalized)})


@dataclass(frozen=True, slots=True)
class EventEmission:
    """Batch input model for event capture."""

    key: str
    message: str
    level: str = "info"
    attributes: Mapping[str, Any] | None = None
    tags: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "key",
            _normalize_token("key", self.key, DOT_TOKEN_PATTERN, code="capture_model_invalid_event_key"),
        )
        object.__setattr__(self, "message", _normalize_required_string("message", self.message))
        object.__setattr__(self, "level", _normalize_marker("level", self.level, EVENT_LEVELS))
        object.__setattr__(self, "attributes", _normalize_json_mapping("attributes", self.attributes))
        object.__setattr__(self, "tags", _normalize_string_mapping("tags", self.tags))

    def to_dict(self) -> dict[str, Any]:
        """Return a stable transport-friendly payload."""

        return {
            "key": self.key,
            "message": self.message,
            "level": self.level,
            "attributes": _thaw_json_value(self.attributes),
            "tags": dict(self.tags),
        }


@dataclass(frozen=True, slots=True)
class MetricEmission:
    """Batch input model for metric capture."""

    key: str
    value: int | float
    unit: str | None = None
    aggregation_scope: str = "step"
    tags: Mapping[str, str] | None = None
    summary_basis: str = "raw_observation"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "key",
            _normalize_token("key", self.key, DOT_TOKEN_PATTERN, code="capture_model_invalid_metric_key"),
        )
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool) or not math.isfinite(self.value):
            _raise_capture_model_error(
                "value must be a finite numeric value.",
                code="capture_model_invalid_metric_value",
                details={"value": self.value},
            )
        object.__setattr__(self, "unit", _normalize_optional_string("unit", self.unit))
        object.__setattr__(
            self,
            "aggregation_scope",
            _normalize_marker("aggregation_scope", self.aggregation_scope, METRIC_AGGREGATION_SCOPES),
        )
        object.__setattr__(self, "tags", _normalize_string_mapping("tags", self.tags))
        object.__setattr__(
            self,
            "summary_basis",
            _normalize_token(
                "summary_basis",
                self.summary_basis,
                LOWER_SNAKE_TOKEN_PATTERN,
                code="capture_model_invalid_summary_basis",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a stable transport-friendly payload."""

        return {
            "key": self.key,
            "value": self.value,
            "unit": self.unit,
            "aggregation_scope": self.aggregation_scope,
            "tags": dict(self.tags),
            "summary_basis": self.summary_basis,
        }


def _normalize_timestamp(field_name: str, value: str | None) -> str | None:
    if value is None:
        return None
    return normalize_timestamp(_normalize_required_string(field_name, value))


def _normalize_linked_refs(values: tuple[StableRef | str, ...] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    normalized: list[str] = []
    for index, item in enumerate(values):
        if isinstance(item, StableRef):
            normalized.append(str(item))
            continue
        if isinstance(item, str):
            normalized.append(str(StableRef.parse(item)))
            continue
        _raise_capture_model_error(
            "linked_refs must contain StableRef or str values.",
            code="capture_model_invalid_linked_ref",
            details={"index": index, "type": type(item).__name__},
        )
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class SpanEmission:
    """Batch input model for span capture."""

    name: str
    started_at: str | None = None
    ended_at: str | None = None
    status: str = "ok"
    span_kind: str = "operation"
    attributes: Mapping[str, Any] | None = None
    linked_refs: tuple[StableRef | str, ...] | None = None
    parent_span_id: str | None = None

    def __post_init__(self) -> None:
        started_at = _normalize_timestamp("started_at", self.started_at)
        ended_at = _normalize_timestamp("ended_at", self.ended_at)
        if started_at is not None and ended_at is not None and ended_at < started_at:
            _raise_capture_model_error(
                "ended_at must be greater than or equal to started_at.",
                code="capture_model_invalid_time_order",
                details={"started_at": started_at, "ended_at": ended_at},
            )
        object.__setattr__(self, "name", _normalize_required_string("name", self.name))
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "ended_at", ended_at)
        object.__setattr__(self, "status", _normalize_marker("status", self.status, TRACE_SPAN_STATUSES))
        object.__setattr__(self, "span_kind", _normalize_marker("span_kind", self.span_kind, TRACE_SPAN_KINDS))
        object.__setattr__(self, "attributes", _normalize_json_mapping("attributes", self.attributes))
        object.__setattr__(self, "linked_refs", _normalize_linked_refs(self.linked_refs))
        object.__setattr__(self, "parent_span_id", _normalize_optional_string("parent_span_id", self.parent_span_id))

    def to_dict(self) -> dict[str, Any]:
        """Return a stable transport-friendly payload."""

        return {
            "name": self.name,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status,
            "span_kind": self.span_kind,
            "attributes": _thaw_json_value(self.attributes),
            "linked_refs": list(self.linked_refs),
            "parent_span_id": self.parent_span_id,
        }


@dataclass(frozen=True, slots=True)
class ArtifactRegistrationEmission:
    """Batch input model for artifact registration."""

    artifact_kind: str
    path: str
    artifact_ref: StableRef | str | None = None
    attributes: Mapping[str, Any] | None = None
    compute_hash: bool = True
    allow_missing: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "artifact_kind",
            _normalize_token(
                "artifact_kind",
                self.artifact_kind,
                LOWER_SNAKE_TOKEN_PATTERN,
                code="capture_model_invalid_artifact_kind",
            ),
        )
        object.__setattr__(self, "path", _normalize_required_string("path", self.path))
        if self.artifact_ref is None:
            object.__setattr__(self, "artifact_ref", None)
        elif isinstance(self.artifact_ref, StableRef):
            object.__setattr__(self, "artifact_ref", self.artifact_ref)
        elif isinstance(self.artifact_ref, str):
            object.__setattr__(self, "artifact_ref", StableRef.parse(self.artifact_ref))
        else:
            _raise_capture_model_error(
                "artifact_ref must be StableRef, str, or None.",
                code="capture_model_invalid_artifact_ref",
                details={"type": type(self.artifact_ref).__name__},
            )
        if not isinstance(self.compute_hash, bool):
            _raise_capture_model_error(
                "compute_hash must be a bool.",
                code="capture_model_invalid_bool",
                details={"field_name": "compute_hash", "type": type(self.compute_hash).__name__},
            )
        if not isinstance(self.allow_missing, bool):
            _raise_capture_model_error(
                "allow_missing must be a bool.",
                code="capture_model_invalid_bool",
                details={"field_name": "allow_missing", "type": type(self.allow_missing).__name__},
            )
        object.__setattr__(self, "attributes", _normalize_json_mapping("attributes", self.attributes))

    def to_dict(self) -> dict[str, Any]:
        """Return a stable transport-friendly payload."""

        return {
            "artifact_kind": self.artifact_kind,
            "path": self.path,
            "artifact_ref": None if self.artifact_ref is None else str(self.artifact_ref),
            "attributes": _thaw_json_value(self.attributes),
            "compute_hash": self.compute_hash,
            "allow_missing": self.allow_missing,
        }


__all__ = [
    "ArtifactRegistrationEmission",
    "EventEmission",
    "MetricEmission",
    "SpanEmission",
]
