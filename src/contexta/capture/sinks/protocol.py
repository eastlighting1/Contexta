"""Sink protocol and dispatch-facing helpers for capture fan-out."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

from ...common.errors import DispatchError
from ...contract import StableRef
from ..results import DeliveryStatus, PayloadFamily


def _freeze_mapping(values: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not values:
        return MappingProxyType({})
    return MappingProxyType({key: values[key] for key in sorted(values)})


def _normalize_nonblank_string(field_name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be blank.")
    return text


def _normalize_payload_family(value: PayloadFamily | str) -> PayloadFamily:
    if isinstance(value, PayloadFamily):
        return value
    return PayloadFamily(_normalize_nonblank_string("family", value).upper())


def _serialize_payload(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _serialize_payload(value.to_dict())
    if isinstance(value, Mapping):
        return {key: _serialize_payload(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_serialize_payload(item) for item in value]
    if isinstance(value, list):
        return [_serialize_payload(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, StableRef):
        return str(value)
    return value


def extract_payload_ref(payload: object) -> str | None:
    """Best-effort extraction of the canonical identity carried by a payload."""

    if hasattr(payload, "artifact_ref"):
        artifact_ref = getattr(payload, "artifact_ref")
        if artifact_ref is not None:
            return str(artifact_ref)

    envelope = getattr(payload, "envelope", None)
    if envelope is not None and hasattr(envelope, "record_ref"):
        record_ref = getattr(envelope, "record_ref")
        if record_ref is not None:
            return str(record_ref)

    for attribute in (
        "operation_context_ref",
        "stage_execution_ref",
        "run_ref",
        "project_ref",
        "ref",
    ):
        if hasattr(payload, attribute):
            ref = getattr(payload, attribute)
            if ref is not None:
                return str(ref)
    return None


@dataclass(frozen=True, slots=True)
class SinkCaptureRequest:
    """Dispatch-ready view of one canonical payload handoff."""

    family: PayloadFamily | str
    payload: object
    payload_type: str | None = None
    payload_ref: str | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "family", _normalize_payload_family(self.family))
        payload_type = self.payload_type or type(self.payload).__name__
        object.__setattr__(self, "payload_type", _normalize_nonblank_string("payload_type", payload_type))
        payload_ref = self.payload_ref
        if payload_ref is None:
            payload_ref = extract_payload_ref(self.payload)
        elif not isinstance(payload_ref, str):
            raise ValueError("payload_ref must be a string when provided.")
        elif not payload_ref.strip():
            raise ValueError("payload_ref must not be blank when provided.")
        object.__setattr__(self, "payload_ref", payload_ref)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @property
    def serialized_payload(self) -> Any:
        """Return a JSON-ready payload snapshot."""

        return _serialize_payload(self.payload)

    def to_dict(self) -> dict[str, Any]:
        """Return a transport-friendly representation."""

        return {
            "family": self.family.value,
            "payload_type": self.payload_type,
            "payload_ref": self.payload_ref,
            "metadata": dict(self.metadata),
            "payload": self.serialized_payload,
        }


@dataclass(frozen=True, slots=True)
class SinkCaptureReceipt:
    """One sink's result for a dispatched payload."""

    status: DeliveryStatus | str = DeliveryStatus.SUCCESS
    detail: str = ""
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        status = self.status if isinstance(self.status, DeliveryStatus) else DeliveryStatus(_normalize_nonblank_string("status", self.status).upper())
        if status is DeliveryStatus.SKIPPED:
            raise ValueError("SinkCaptureReceipt does not allow SKIPPED status.")
        object.__setattr__(self, "status", status)
        detail = self.detail.strip() if isinstance(self.detail, str) else self.detail
        if not isinstance(detail, str):
            raise ValueError("detail must be a string.")
        object.__setattr__(self, "detail", detail)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @classmethod
    def success(cls, *, detail: str = "", metadata: Mapping[str, Any] | None = None) -> "SinkCaptureReceipt":
        return cls(status=DeliveryStatus.SUCCESS, detail=detail, metadata=metadata)

    @classmethod
    def degraded(cls, *, detail: str, metadata: Mapping[str, Any] | None = None) -> "SinkCaptureReceipt":
        return cls(status=DeliveryStatus.DEGRADED, detail=detail, metadata=metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "detail": self.detail,
            "metadata": dict(self.metadata),
        }


@runtime_checkable
class Sink(Protocol):
    """Capture sink protocol used by the dispatch engine."""

    name: str
    supported_families: tuple[PayloadFamily, ...]

    def supports(self, family: PayloadFamily | str) -> bool: ...

    def capture(self, *, family: PayloadFamily | str, payload: object) -> SinkCaptureReceipt: ...


class BaseSink:
    """Common support helpers for built-in sink implementations."""

    name: str
    supported_families: tuple[PayloadFamily, ...]

    def __init__(
        self,
        *,
        name: str,
        supported_families: tuple[PayloadFamily | str, ...] | None = None,
    ) -> None:
        self.name = _normalize_nonblank_string("name", name)
        normalized = supported_families or tuple(PayloadFamily)
        self.supported_families = tuple(_normalize_payload_family(item) for item in normalized)

    def supports(self, family: PayloadFamily | str) -> bool:
        normalized = _normalize_payload_family(family)
        return normalized in self.supported_families

    def make_request(
        self,
        *,
        family: PayloadFamily | str,
        payload: object,
        metadata: Mapping[str, Any] | None = None,
    ) -> SinkCaptureRequest:
        normalized = _normalize_payload_family(family)
        if not self.supports(normalized):
            raise DispatchError(
                f"Sink '{self.name}' does not support family '{normalized.value}'.",
                code="sink_family_not_supported",
                details={"sink_name": self.name, "family": normalized.value},
            )
        return SinkCaptureRequest(family=normalized, payload=payload, metadata=metadata)


__all__ = [
    "BaseSink",
    "Sink",
    "SinkCaptureReceipt",
    "SinkCaptureRequest",
    "extract_payload_ref",
]
