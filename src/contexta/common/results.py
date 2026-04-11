"""Shared result primitives for Contexta orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Generic, Mapping, Sequence, TypeVar

from .errors import ContextaError


T = TypeVar("T")


def _freeze_mapping(values: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Return a stable read-only mapping."""
    if not values:
        return MappingProxyType({})
    return MappingProxyType({key: values[key] for key in sorted(values)})


class ResultStatus(str, Enum):
    """Global operation outcome triad."""

    SUCCESS = "SUCCESS"
    DEGRADED = "DEGRADED"
    FAILURE = "FAILURE"


class MessageLevel(str, Enum):
    """Stable message level vocabulary."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class ResultMessage:
    """General informational or warning message."""

    level: MessageLevel
    code: str
    message: str
    details: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("ResultMessage.code must not be empty.")
        object.__setattr__(self, "details", _freeze_mapping(self.details))


@dataclass(frozen=True, slots=True)
class DegradationNote:
    """Machine-readable explanation for degraded success."""

    code: str
    message: str
    fidelity_loss: bool = True
    recoverable: bool = True
    affected_planes: tuple[str, ...] = ()
    details: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("DegradationNote.code must not be empty.")
        object.__setattr__(self, "affected_planes", tuple(self.affected_planes))
        object.__setattr__(self, "details", _freeze_mapping(self.details))


@dataclass(frozen=True, slots=True)
class FailureInfo:
    """Summary of a failure that did not raise immediately."""

    code: str
    message: str
    retryable: bool = False
    error_type: str | None = None
    details: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("FailureInfo.code must not be empty.")
        object.__setattr__(self, "details", _freeze_mapping(self.details))

    @classmethod
    def from_exception(cls, error: BaseException) -> "FailureInfo":
        """Build a failure summary from an exception."""
        if isinstance(error, ContextaError):
            return cls(
                code=error.code,
                message=error.message,
                retryable=error.retryable,
                error_type=type(error).__name__,
                details=error.details,
            )
        return cls(
            code="unexpected_error",
            message=str(error) or type(error).__name__,
            retryable=False,
            error_type=type(error).__name__,
        )


@dataclass(frozen=True, slots=True)
class OperationResult(Generic[T]):
    """Shared operation outcome container."""

    status: ResultStatus
    value: T | None = None
    messages: tuple[ResultMessage, ...] = ()
    degradation_notes: tuple[DegradationNote, ...] = ()
    failure: FailureInfo | None = None
    applied: bool = True
    planned_only: bool = False
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "messages", tuple(self.messages))
        object.__setattr__(self, "degradation_notes", tuple(self.degradation_notes))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

        if self.status is ResultStatus.SUCCESS and self.failure is not None:
            raise ValueError("SUCCESS result cannot contain failure info.")
        if self.status is ResultStatus.DEGRADED and not self.degradation_notes:
            raise ValueError("DEGRADED result must include degradation notes.")
        if self.status is ResultStatus.FAILURE and self.failure is None:
            raise ValueError("FAILURE result must include failure info.")
        if self.planned_only and self.applied:
            raise ValueError("planned_only=True requires applied=False.")

    @property
    def succeeded(self) -> bool:
        """Return whether the operation succeeded without fidelity loss."""
        return self.status is ResultStatus.SUCCESS

    @property
    def degraded(self) -> bool:
        """Return whether the operation succeeded with degradation."""
        return self.status is ResultStatus.DEGRADED

    @property
    def failed(self) -> bool:
        """Return whether the operation failed."""
        return self.status is ResultStatus.FAILURE

    @classmethod
    def success(
        cls,
        value: T | None = None,
        *,
        messages: Sequence[ResultMessage] = (),
        metadata: Mapping[str, Any] | None = None,
        applied: bool = True,
    ) -> "OperationResult[T]":
        """Create a success result."""
        return cls(
            status=ResultStatus.SUCCESS,
            value=value,
            messages=tuple(messages),
            applied=applied,
            planned_only=False,
            metadata=metadata,
        )

    @classmethod
    def with_degradation(
        cls,
        value: T | None = None,
        *,
        degradation_notes: Sequence[DegradationNote],
        messages: Sequence[ResultMessage] = (),
        metadata: Mapping[str, Any] | None = None,
        applied: bool = True,
        planned_only: bool = False,
    ) -> "OperationResult[T]":
        """Create a degraded result."""
        return cls(
            status=ResultStatus.DEGRADED,
            value=value,
            messages=tuple(messages),
            degradation_notes=tuple(degradation_notes),
            applied=applied,
            planned_only=planned_only,
            metadata=metadata,
        )

    @classmethod
    def failure_result(
        cls,
        failure: FailureInfo | BaseException,
        *,
        messages: Sequence[ResultMessage] = (),
        metadata: Mapping[str, Any] | None = None,
        applied: bool = False,
        planned_only: bool = False,
    ) -> "OperationResult[T]":
        """Create a failure result."""
        failure_info = (
            failure
            if isinstance(failure, FailureInfo)
            else FailureInfo.from_exception(failure)
        )
        return cls(
            status=ResultStatus.FAILURE,
            messages=tuple(messages),
            failure=failure_info,
            applied=applied,
            planned_only=planned_only,
            metadata=metadata,
        )


@dataclass(frozen=True, slots=True)
class BatchResult(OperationResult[T], Generic[T]):
    """Shared batch outcome container."""

    items: tuple[OperationResult[T], ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "items", tuple(self.items))

    @property
    def total_count(self) -> int:
        """Return the total number of items in the batch."""
        return len(self.items)

    @property
    def success_count(self) -> int:
        """Return the number of successful items."""
        return sum(item.succeeded for item in self.items)

    @property
    def degraded_count(self) -> int:
        """Return the number of degraded items."""
        return sum(item.degraded for item in self.items)

    @property
    def failure_count(self) -> int:
        """Return the number of failed items."""
        return sum(item.failed for item in self.items)

    @classmethod
    def aggregate(
        cls,
        items: Sequence[OperationResult[T]],
        *,
        value: T | None = None,
        messages: Sequence[ResultMessage] = (),
        metadata: Mapping[str, Any] | None = None,
        applied: bool | None = None,
        planned_only: bool | None = None,
    ) -> "BatchResult[T]":
        """Aggregate item results into a batch summary."""
        frozen_items = tuple(items)
        if any(item.failed for item in frozen_items):
            status = ResultStatus.FAILURE
        elif any(item.degraded for item in frozen_items):
            status = ResultStatus.DEGRADED
        else:
            status = ResultStatus.SUCCESS

        degradation_notes = tuple(
            note for item in frozen_items for note in item.degradation_notes
        )
        failure = next((item.failure for item in frozen_items if item.failure is not None), None)

        if applied is None:
            applied = any(item.applied for item in frozen_items) if frozen_items else True
        if planned_only is None:
            planned_only = bool(frozen_items) and all(item.planned_only for item in frozen_items)

        return cls(
            status=status,
            value=value,
            items=frozen_items,
            messages=tuple(messages),
            degradation_notes=degradation_notes,
            failure=failure if status is ResultStatus.FAILURE else None,
            applied=applied,
            planned_only=planned_only,
            metadata=metadata,
        )


__all__ = [
    "BatchResult",
    "DegradationNote",
    "FailureInfo",
    "MessageLevel",
    "OperationResult",
    "ResultMessage",
    "ResultStatus",
]
