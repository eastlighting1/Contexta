"""Capture-specific result wrappers built on top of common result primitives."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from ..common.results import (
    BatchResult,
    DegradationNote,
    FailureInfo,
    MessageLevel,
    OperationResult,
    ResultMessage,
    ResultStatus,
)


def _freeze_mapping(values: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not values:
        return MappingProxyType({})
    return MappingProxyType({key: values[key] for key in sorted(values)})


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _serialize_value(value.to_dict())
    if isinstance(value, Mapping):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _normalize_nonblank_string(field_name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be blank.")
    return text


def _normalize_optional_string(field_name: str, value: str | None) -> str | None:
    if value is None:
        return None
    return _normalize_nonblank_string(field_name, value)


def _normalize_string_tuple(field_name: str, values: Sequence[str]) -> tuple[str, ...]:
    return tuple(_normalize_nonblank_string(f"{field_name}[{index}]", value) for index, value in enumerate(values))


class PayloadFamily(str, Enum):
    """Capture payload family routing."""

    CONTEXT = "CONTEXT"
    RECORD = "RECORD"
    ARTIFACT = "ARTIFACT"
    DEGRADATION = "DEGRADATION"


class DeliveryStatus(str, Enum):
    """Per-sink delivery status vocabulary."""

    SUCCESS = "SUCCESS"
    DEGRADED = "DEGRADED"
    FAILURE = "FAILURE"
    SKIPPED = "SKIPPED"


def _normalize_payload_family(value: PayloadFamily | str) -> PayloadFamily:
    if isinstance(value, PayloadFamily):
        return value
    return PayloadFamily(_normalize_nonblank_string("family", value).upper())


def _normalize_delivery_status(value: DeliveryStatus | str) -> DeliveryStatus:
    if isinstance(value, DeliveryStatus):
        return value
    return DeliveryStatus(_normalize_nonblank_string("status", value).upper())


def _normalize_result_status(value: ResultStatus | str) -> ResultStatus:
    if isinstance(value, ResultStatus):
        return value
    return ResultStatus(_normalize_nonblank_string("status", value).upper())


def _notes_from_reasons(reasons: Sequence[str]) -> tuple[DegradationNote, ...]:
    return tuple(
        DegradationNote(
            code=f"capture_degradation_{index + 1}",
            message=reason,
            affected_planes=("capture",),
        )
        for index, reason in enumerate(reasons)
    )


def _warning_messages(warnings: Sequence[str]) -> tuple[ResultMessage, ...]:
    return tuple(
        ResultMessage(
            level=MessageLevel.WARNING,
            code=f"capture_warning_{index + 1}",
            message=warning,
        )
        for index, warning in enumerate(warnings)
    )


@dataclass(frozen=True, slots=True)
class Delivery:
    """Per-sink delivery detail for one capture attempt."""

    sink_name: str
    family: PayloadFamily | str
    status: DeliveryStatus | str
    detail: str = ""
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "sink_name", _normalize_nonblank_string("sink_name", self.sink_name))
        object.__setattr__(self, "family", _normalize_payload_family(self.family))
        object.__setattr__(self, "status", _normalize_delivery_status(self.status))
        detail = self.detail.strip() if isinstance(self.detail, str) else self.detail
        if not isinstance(detail, str):
            raise ValueError("detail must be a string.")
        object.__setattr__(self, "detail", detail)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return a transport-friendly shape."""

        return {
            "sink_name": self.sink_name,
            "family": self.family.value,
            "status": self.status.value,
            "detail": self.detail,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CaptureResult(OperationResult[Any]):
    """Capture-oriented result built on top of the common operation result."""

    family: PayloadFamily | str = PayloadFamily.RECORD
    deliveries: tuple[Delivery, ...] = ()
    warnings: tuple[str, ...] = ()
    degradation_reasons: tuple[str, ...] = ()
    payload: Any | None = None
    degradation_emitted: bool = False
    degradation_payload: Any | None = None
    recovered_to_outbox: bool = False
    replay_refs: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _normalize_result_status(self.status))
        object.__setattr__(self, "family", _normalize_payload_family(self.family))
        object.__setattr__(
            self,
            "deliveries",
            tuple(item if isinstance(item, Delivery) else Delivery(**item) for item in self.deliveries),
        )
        warnings = _normalize_string_tuple("warnings", self.warnings)
        reasons = _normalize_string_tuple("degradation_reasons", self.degradation_reasons)
        replay_refs = _normalize_string_tuple("replay_refs", self.replay_refs)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "degradation_reasons", reasons)
        object.__setattr__(self, "replay_refs", replay_refs)
        object.__setattr__(self, "error_code", _normalize_optional_string("error_code", self.error_code))
        object.__setattr__(self, "error_message", _normalize_optional_string("error_message", self.error_message))

        if self.payload is None and self.value is not None:
            object.__setattr__(self, "payload", self.value)
        elif self.payload is not None and self.value is None:
            object.__setattr__(self, "value", self.payload)
        elif self.payload is not None and self.value is not None and self.payload != self.value:
            raise ValueError("payload and value must match when both are provided.")

        messages = tuple(self.messages) + _warning_messages(warnings)
        object.__setattr__(self, "messages", messages)

        if self.status is ResultStatus.DEGRADED and not self.degradation_notes:
            notes = _notes_from_reasons(reasons) or (
                DegradationNote(
                    code="capture_degraded",
                    message="Capture completed with degradation.",
                    affected_planes=("capture",),
                ),
            )
            object.__setattr__(self, "degradation_notes", notes)

        if self.status is ResultStatus.FAILURE and self.failure is None:
            object.__setattr__(
                self,
                "failure",
                FailureInfo(
                    code=self.error_code or "capture_failed",
                    message=self.error_message or "Capture failed.",
                ),
            )

        if self.failure is not None:
            if self.error_code is None:
                object.__setattr__(self, "error_code", self.failure.code)
            if self.error_message is None:
                object.__setattr__(self, "error_message", self.failure.message)

        if self.degradation_payload is not None and not self.degradation_emitted:
            raise ValueError("degradation_payload requires degradation_emitted=True.")

        super().__post_init__()

    @classmethod
    def success(
        cls,
        family: PayloadFamily | str,
        *,
        payload: Any | None = None,
        deliveries: Sequence[Delivery] = (),
        warnings: Sequence[str] = (),
        messages: Sequence[ResultMessage] = (),
        metadata: Mapping[str, Any] | None = None,
        applied: bool = True,
    ) -> "CaptureResult":
        """Create a successful capture result."""

        return cls(
            family=family,
            status=ResultStatus.SUCCESS,
            payload=payload,
            deliveries=tuple(deliveries),
            warnings=tuple(warnings),
            messages=tuple(messages),
            metadata=metadata,
            applied=applied,
        )

    @classmethod
    def with_degradation(
        cls,
        family: PayloadFamily | str,
        *,
        payload: Any | None = None,
        deliveries: Sequence[Delivery] = (),
        warnings: Sequence[str] = (),
        degradation_reasons: Sequence[str] = (),
        degradation_notes: Sequence[DegradationNote] = (),
        degradation_emitted: bool = False,
        degradation_payload: Any | None = None,
        recovered_to_outbox: bool = False,
        replay_refs: Sequence[str] = (),
        messages: Sequence[ResultMessage] = (),
        metadata: Mapping[str, Any] | None = None,
        applied: bool = True,
        planned_only: bool = False,
    ) -> "CaptureResult":
        """Create a degraded capture result."""

        return cls(
            family=family,
            status=ResultStatus.DEGRADED,
            payload=payload,
            deliveries=tuple(deliveries),
            warnings=tuple(warnings),
            degradation_reasons=tuple(degradation_reasons),
            degradation_notes=tuple(degradation_notes),
            degradation_emitted=degradation_emitted,
            degradation_payload=degradation_payload,
            recovered_to_outbox=recovered_to_outbox,
            replay_refs=tuple(replay_refs),
            messages=tuple(messages),
            metadata=metadata,
            applied=applied,
            planned_only=planned_only,
        )

    @classmethod
    def failure_result(
        cls,
        family: PayloadFamily | str,
        failure: FailureInfo | BaseException,
        *,
        deliveries: Sequence[Delivery] = (),
        warnings: Sequence[str] = (),
        replay_refs: Sequence[str] = (),
        messages: Sequence[ResultMessage] = (),
        metadata: Mapping[str, Any] | None = None,
        applied: bool = False,
        planned_only: bool = False,
    ) -> "CaptureResult":
        """Create a failed capture result."""

        failure_info = failure if isinstance(failure, FailureInfo) else FailureInfo.from_exception(failure)
        return cls(
            family=family,
            status=ResultStatus.FAILURE,
            deliveries=tuple(deliveries),
            warnings=tuple(warnings),
            replay_refs=tuple(replay_refs),
            messages=tuple(messages),
            failure=failure_info,
            error_code=failure_info.code,
            error_message=failure_info.message,
            metadata=metadata,
            applied=applied,
            planned_only=planned_only,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a transport-friendly shape."""

        return {
            "family": self.family.value,
            "status": self.status.value,
            "deliveries": [delivery.to_dict() for delivery in self.deliveries],
            "warnings": list(self.warnings),
            "degradation_reasons": list(self.degradation_reasons),
            "payload": _serialize_value(self.payload),
            "degradation_emitted": self.degradation_emitted,
            "degradation_payload": _serialize_value(self.degradation_payload),
            "recovered_to_outbox": self.recovered_to_outbox,
            "replay_refs": list(self.replay_refs),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "messages": [
                {
                    "level": message.level.value,
                    "code": message.code,
                    "message": message.message,
                    "details": dict(message.details) if message.details is not None else None,
                }
                for message in self.messages
            ],
            "degradation_notes": [
                {
                    "code": note.code,
                    "message": note.message,
                    "fidelity_loss": note.fidelity_loss,
                    "recoverable": note.recoverable,
                    "affected_planes": list(note.affected_planes),
                    "details": dict(note.details) if note.details is not None else None,
                }
                for note in self.degradation_notes
            ],
            "failure": None
            if self.failure is None
            else {
                "code": self.failure.code,
                "message": self.failure.message,
                "retryable": self.failure.retryable,
                "error_type": self.failure.error_type,
                "details": dict(self.failure.details) if self.failure.details is not None else None,
            },
            "applied": self.applied,
            "planned_only": self.planned_only,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class BatchCaptureResult(BatchResult[CaptureResult]):
    """Capture-specific batch result with canonical batch-status semantics."""

    family: PayloadFamily | str = PayloadFamily.RECORD

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _normalize_result_status(self.status))
        object.__setattr__(self, "family", _normalize_payload_family(self.family))
        object.__setattr__(self, "items", tuple(self.items))
        for index, item in enumerate(self.items):
            if not isinstance(item, CaptureResult):
                raise ValueError(f"items[{index}] must be CaptureResult.")
        super().__post_init__()

    @property
    def results(self) -> tuple[CaptureResult, ...]:
        """Return batch items using the capture-specific name."""

        return self.items

    @classmethod
    def from_results(
        cls,
        family: PayloadFamily | str,
        results: Sequence[CaptureResult],
        *,
        messages: Sequence[ResultMessage] = (),
        metadata: Mapping[str, Any] | None = None,
        applied: bool | None = None,
        planned_only: bool | None = None,
    ) -> "BatchCaptureResult":
        """Aggregate capture results using the canonical batch-status rules."""

        frozen_results = tuple(results)
        normalized_family = _normalize_payload_family(family)

        if frozen_results and any(result.family is not normalized_family for result in frozen_results):
            raise ValueError("All capture results in one batch must share the same family.")

        if not frozen_results or all(result.succeeded for result in frozen_results):
            status = ResultStatus.SUCCESS
        elif all(result.failed for result in frozen_results):
            status = ResultStatus.FAILURE
        else:
            status = ResultStatus.DEGRADED

        degradation_notes = tuple(note for result in frozen_results for note in result.degradation_notes)
        if status is ResultStatus.DEGRADED and not degradation_notes:
            degradation_notes = (
                DegradationNote(
                    code="capture_batch_partial_failure",
                    message="Batch capture completed with mixed item outcomes.",
                    affected_planes=("capture",),
                ),
            )

        failure = next((result.failure for result in frozen_results if result.failure is not None), None)

        if applied is None:
            applied = any(result.applied for result in frozen_results) if frozen_results else True
        if planned_only is None:
            planned_only = bool(frozen_results) and all(result.planned_only for result in frozen_results)

        return cls(
            family=normalized_family,
            status=status,
            items=frozen_results,
            messages=tuple(messages),
            degradation_notes=degradation_notes,
            failure=failure if status is ResultStatus.FAILURE else None,
            applied=applied,
            planned_only=planned_only,
            metadata=metadata,
        )

    @classmethod
    def aggregate(
        cls,
        family: PayloadFamily | str,
        results: Sequence[CaptureResult],
        *,
        messages: Sequence[ResultMessage] = (),
        metadata: Mapping[str, Any] | None = None,
        applied: bool | None = None,
        planned_only: bool | None = None,
    ) -> "BatchCaptureResult":
        """Alias for `from_results` using the capture-specific semantics."""

        return cls.from_results(
            family,
            results,
            messages=messages,
            metadata=metadata,
            applied=applied,
            planned_only=planned_only,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a transport-friendly shape."""

        return {
            "family": self.family.value,
            "status": self.status.value,
            "results": [result.to_dict() for result in self.results],
            "messages": [
                {
                    "level": message.level.value,
                    "code": message.code,
                    "message": message.message,
                    "details": dict(message.details) if message.details is not None else None,
                }
                for message in self.messages
            ],
            "degradation_notes": [
                {
                    "code": note.code,
                    "message": note.message,
                    "fidelity_loss": note.fidelity_loss,
                    "recoverable": note.recoverable,
                    "affected_planes": list(note.affected_planes),
                    "details": dict(note.details) if note.details is not None else None,
                }
                for note in self.degradation_notes
            ],
            "failure": None
            if self.failure is None
            else {
                "code": self.failure.code,
                "message": self.failure.message,
                "retryable": self.failure.retryable,
                "error_type": self.failure.error_type,
                "details": dict(self.failure.details) if self.failure.details is not None else None,
            },
            "applied": self.applied,
            "planned_only": self.planned_only,
            "metadata": dict(self.metadata),
        }


__all__ = [
    "BatchCaptureResult",
    "CaptureResult",
    "Delivery",
    "DeliveryStatus",
    "PayloadFamily",
    "ResultStatus",
]
