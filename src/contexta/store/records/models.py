"""Canonical models for record append, scan, and replay workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from ...common.errors import ValidationError
from ...common.time import normalize_timestamp
from ...contract import DegradedRecord, MetricRecord, StructuredEventRecord, TraceSpanRecord


CanonicalRecord = StructuredEventRecord | MetricRecord | TraceSpanRecord | DegradedRecord
RECORD_MODEL_TYPES = (
    StructuredEventRecord,
    MetricRecord,
    TraceSpanRecord,
    DegradedRecord,
)


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not value:
        return MappingProxyType({})
    return MappingProxyType({key: value[key] for key in sorted(value)})


def _normalize_timestamp(value: str | datetime, *, field_name: str) -> str:
    if isinstance(value, datetime):
        return normalize_timestamp(value)
    if not isinstance(value, str):
        raise ValidationError(
            f"{field_name} must be a UTC timestamp string.",
            code="record_store_invalid_timestamp",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    text = value.strip()
    if not text:
        raise ValidationError(
            f"{field_name} must not be blank.",
            code="record_store_invalid_timestamp",
            details={"field_name": field_name},
        )
    return normalize_timestamp(text)


def _normalize_positive_int(value: int, *, field_name: str, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(
            f"{field_name} must be an integer.",
            code="record_store_invalid_number",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    if value < minimum:
        raise ValidationError(
            f"{field_name} must be greater than or equal to {minimum}.",
            code="record_store_invalid_number",
            details={"field_name": field_name, "value": value, "minimum": minimum},
        )
    return value


def _normalize_optional_positive_int(value: int | None, *, field_name: str) -> int | None:
    if value is None:
        return None
    return _normalize_positive_int(value, field_name=field_name)


def _normalize_optional_timestamp(value: str | datetime | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _normalize_timestamp(value, field_name=field_name)


def _normalize_optional_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(
            f"{field_name} must be a string.",
            code="record_store_invalid_text",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    text = value.strip()
    return text or None


def _normalize_record_type(value: str | None, *, field_name: str = "record_type") -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(
            f"{field_name} must be a string.",
            code="record_store_invalid_record_type",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    text = value.strip().lower()
    if text not in {"event", "metric", "span", "degraded"}:
        raise ValidationError(
            f"Unsupported {field_name}.",
            code="record_store_invalid_record_type",
            details={"field_name": field_name, "value": value},
        )
    return text


def _normalize_record(value: CanonicalRecord) -> CanonicalRecord:
    if not isinstance(value, RECORD_MODEL_TYPES):
        raise ValidationError(
            "Stored record must use a canonical record model.",
            code="record_store_invalid_record",
            details={"type": type(value).__name__},
        )
    return value


class ReplayMode(str, Enum):
    STRICT = "strict"
    TOLERANT = "tolerant"


class DurabilityStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    FLUSHED = "FLUSHED"
    FSYNCED = "FSYNCED"


class IntegrityState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CORRUPTED = "CORRUPTED"


@dataclass(frozen=True, slots=True)
class AppendReceipt:
    sequence: int
    segment_id: int
    offset: int
    record_ref: str
    record_type: str
    run_ref: str
    durability_status: DurabilityStatus = DurabilityStatus.ACCEPTED

    def __post_init__(self) -> None:
        object.__setattr__(self, "sequence", _normalize_positive_int(self.sequence, field_name="sequence"))
        object.__setattr__(self, "segment_id", _normalize_positive_int(self.segment_id, field_name="segment_id"))
        object.__setattr__(self, "offset", _normalize_positive_int(self.offset, field_name="offset"))
        object.__setattr__(self, "record_type", _normalize_record_type(self.record_type) or "event")
        if not isinstance(self.record_ref, str) or not self.record_ref.strip():
            raise ValidationError("record_ref must not be blank.", code="record_store_invalid_record_ref")
        if not isinstance(self.run_ref, str) or not self.run_ref.strip():
            raise ValidationError("run_ref must not be blank.", code="record_store_invalid_run_ref")


@dataclass(frozen=True, slots=True)
class AppendRejection:
    index: int
    code: str
    message: str
    record_ref: str | None = None
    record_type: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "index", _normalize_positive_int(self.index, field_name="index", minimum=0))
        if not self.code or not self.message:
            raise ValidationError(
                "AppendRejection requires non-empty code and message.",
                code="record_store_invalid_rejection",
            )
        object.__setattr__(self, "record_ref", _normalize_optional_text(self.record_ref, field_name="record_ref"))
        object.__setattr__(self, "record_type", _normalize_record_type(self.record_type))


@dataclass(frozen=True, slots=True)
class AppendResult:
    accepted: tuple[AppendReceipt, ...] = ()
    rejected: tuple[AppendRejection, ...] = ()
    durability_status: DurabilityStatus = DurabilityStatus.ACCEPTED
    durable_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "accepted", tuple(self.accepted))
        object.__setattr__(self, "rejected", tuple(self.rejected))
        object.__setattr__(self, "durable_count", _normalize_positive_int(self.durable_count, field_name="durable_count", minimum=0))
        if self.accepted:
            if self.durable_count > len(self.accepted):
                raise ValidationError(
                    "durable_count cannot exceed accepted_count.",
                    code="record_store_invalid_append_result",
                    details={"durable_count": self.durable_count, "accepted_count": len(self.accepted)},
                )
        elif self.durable_count != 0:
            raise ValidationError(
                "durable_count must be zero when nothing was accepted.",
                code="record_store_invalid_append_result",
            )

    @property
    def accepted_count(self) -> int:
        return len(self.accepted)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)

    @property
    def success(self) -> bool:
        return self.rejected_count == 0


@dataclass(frozen=True, slots=True)
class ScanFilter:
    run_ref: str | None = None
    stage_execution_ref: str | None = None
    batch_execution_ref: str | None = None
    sample_observation_ref: str | None = None
    record_type: str | None = None
    start_time: str | datetime | None = None
    end_time: str | datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_ref", _normalize_optional_text(self.run_ref, field_name="run_ref"))
        object.__setattr__(
            self,
            "stage_execution_ref",
            _normalize_optional_text(self.stage_execution_ref, field_name="stage_execution_ref"),
        )
        object.__setattr__(
            self,
            "batch_execution_ref",
            _normalize_optional_text(self.batch_execution_ref, field_name="batch_execution_ref"),
        )
        object.__setattr__(
            self,
            "sample_observation_ref",
            _normalize_optional_text(self.sample_observation_ref, field_name="sample_observation_ref"),
        )
        object.__setattr__(self, "record_type", _normalize_record_type(self.record_type))
        start_time = _normalize_optional_timestamp(self.start_time, field_name="start_time")
        end_time = _normalize_optional_timestamp(self.end_time, field_name="end_time")
        if start_time is not None and end_time is not None and start_time > end_time:
            raise ValidationError(
                "start_time must be less than or equal to end_time.",
                code="record_store_invalid_time_range",
                details={"start_time": start_time, "end_time": end_time},
            )
        object.__setattr__(self, "start_time", start_time)
        object.__setattr__(self, "end_time", end_time)


@dataclass(frozen=True, slots=True)
class StoredRecord:
    sequence: int
    segment_id: int
    offset: int
    appended_at: str | datetime
    record: CanonicalRecord

    def __post_init__(self) -> None:
        object.__setattr__(self, "sequence", _normalize_positive_int(self.sequence, field_name="sequence"))
        object.__setattr__(self, "segment_id", _normalize_positive_int(self.segment_id, field_name="segment_id"))
        object.__setattr__(self, "offset", _normalize_positive_int(self.offset, field_name="offset"))
        object.__setattr__(self, "appended_at", _normalize_timestamp(self.appended_at, field_name="appended_at"))
        object.__setattr__(self, "record", _normalize_record(self.record))

    @property
    def record_ref(self) -> str:
        return str(self.record.envelope.record_ref)

    @property
    def record_type(self) -> str:
        return self.record.envelope.record_type

    @property
    def run_ref(self) -> str:
        return str(self.record.envelope.run_ref)

    @property
    def stage_execution_ref(self) -> str | None:
        ref = self.record.envelope.stage_execution_ref
        return None if ref is None else str(ref)

    @property
    def batch_execution_ref(self) -> str | None:
        ref = self.record.envelope.batch_execution_ref
        return None if ref is None else str(ref)

    @property
    def sample_observation_ref(self) -> str | None:
        ref = self.record.envelope.sample_observation_ref
        return None if ref is None else str(ref)


@dataclass(frozen=True, slots=True)
class KnownGap:
    code: str
    message: str
    segment_id: int
    line_number: int | None = None
    start_sequence: int | None = None
    end_sequence: int | None = None
    details: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.code or not self.message:
            raise ValidationError("KnownGap requires non-empty code and message.", code="record_store_invalid_gap")
        object.__setattr__(self, "segment_id", _normalize_positive_int(self.segment_id, field_name="segment_id"))
        object.__setattr__(self, "line_number", _normalize_optional_positive_int(self.line_number, field_name="line_number"))
        object.__setattr__(
            self,
            "start_sequence",
            _normalize_optional_positive_int(self.start_sequence, field_name="start_sequence"),
        )
        object.__setattr__(
            self,
            "end_sequence",
            _normalize_optional_positive_int(self.end_sequence, field_name="end_sequence"),
        )
        if (
            self.start_sequence is not None
            and self.end_sequence is not None
            and self.start_sequence > self.end_sequence
        ):
            raise ValidationError(
                "start_sequence must be less than or equal to end_sequence.",
                code="record_store_invalid_gap",
            )
        object.__setattr__(self, "details", _freeze_mapping(self.details))


@dataclass(frozen=True, slots=True)
class ReplayResult:
    records: tuple[StoredRecord, ...] = ()
    record_count: int = 0
    mode: ReplayMode = ReplayMode.STRICT
    warnings: tuple[str, ...] = ()
    known_gaps: tuple[KnownGap, ...] = ()
    integrity_state: IntegrityState = IntegrityState.HEALTHY

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(self.records))
        object.__setattr__(self, "warnings", tuple(str(item) for item in self.warnings))
        object.__setattr__(self, "known_gaps", tuple(self.known_gaps))
        if self.record_count != len(self.records):
            raise ValidationError(
                "record_count must equal len(records).",
                code="record_store_invalid_replay_result",
                details={"record_count": self.record_count, "actual_count": len(self.records)},
            )
        if self.mode is ReplayMode.STRICT and (self.warnings or self.known_gaps):
            raise ValidationError(
                "STRICT replay result cannot carry warnings or known gaps.",
                code="record_store_invalid_replay_result",
            )


__all__ = [
    "AppendReceipt",
    "AppendRejection",
    "AppendResult",
    "CanonicalRecord",
    "DurabilityStatus",
    "IntegrityState",
    "KnownGap",
    "ReplayMode",
    "ReplayResult",
    "ScanFilter",
    "StoredRecord",
]
