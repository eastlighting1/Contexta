"""Sequential scan helpers for the record truth plane."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from ...common.errors import RecordError, SerializationError
from ...contract import (
    deserialize_degraded_record,
    deserialize_metric_record,
    deserialize_structured_event_record,
    deserialize_trace_span_record,
)
from .models import CanonicalRecord, ScanFilter, StoredRecord


def scan_records(store: Any, scan_filter: ScanFilter | None = None) -> Iterator[StoredRecord]:
    """Yield stored records directly from segment truth."""

    active_filter = scan_filter or ScanFilter()
    _ = store._load_manifest()
    segment_paths = sorted(store._segments_dir().glob("segment-*.jsonl"))
    for segment_path in segment_paths:
        segment_id = _segment_id_from_path(segment_path)
        yield from _scan_segment(segment_path, segment_id=segment_id, scan_filter=active_filter)


def _scan_segment(segment_path: Path, *, segment_id: int, scan_filter: ScanFilter) -> Iterator[StoredRecord]:
    raw_lines = segment_path.read_bytes().splitlines(keepends=True)
    for line_number, raw_line in enumerate(raw_lines, start=1):
        try:
            line = raw_line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SerializationError(
                "Segment line is not valid UTF-8.",
                code="record_scan_invalid_encoding",
                details={"segment_id": segment_id, "line_number": line_number},
                cause=exc,
            ) from exc
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SerializationError(
                "Segment line is not valid JSON.",
                code="record_scan_invalid_json",
                details={"segment_id": segment_id, "line_number": line_number},
                cause=exc,
            ) from exc
        try:
            stored = StoredRecord(
                sequence=int(payload["sequence"]),
                segment_id=segment_id,
                offset=line_number,
                appended_at=payload["appended_at"],
                record=_deserialize_record_payload(payload["record"]),
            )
        except Exception as exc:
            raise RecordError(
                "Stored record line could not be materialized.",
                code="record_scan_materialization_failed",
                details={"segment_id": segment_id, "line_number": line_number},
                cause=exc,
            ) from exc
        if _matches_filter(stored, scan_filter=scan_filter):
            yield stored


def _deserialize_record_payload(payload: Any) -> CanonicalRecord:
    if not isinstance(payload, dict):
        raise SerializationError(
            "Stored record payload must be a mapping.",
            code="record_scan_invalid_record_payload",
        )
    envelope = payload.get("envelope")
    if not isinstance(envelope, dict):
        raise SerializationError(
            "Stored record envelope must be a mapping.",
            code="record_scan_invalid_record_envelope",
        )
    record_type = envelope.get("record_type")
    if record_type == "event":
        return deserialize_structured_event_record(payload)
    if record_type == "metric":
        return deserialize_metric_record(payload)
    if record_type == "span":
        return deserialize_trace_span_record(payload)
    if record_type == "degraded":
        return deserialize_degraded_record(payload)
    raise SerializationError(
        "Stored record type is not supported.",
        code="record_scan_invalid_record_type",
        details={"record_type": record_type},
    )


def _matches_filter(stored: StoredRecord, *, scan_filter: ScanFilter) -> bool:
    if scan_filter.run_ref is not None and stored.run_ref != scan_filter.run_ref:
        return False
    if scan_filter.stage_execution_ref is not None and stored.stage_execution_ref != scan_filter.stage_execution_ref:
        return False
    if scan_filter.batch_execution_ref is not None and stored.batch_execution_ref != scan_filter.batch_execution_ref:
        return False
    if scan_filter.sample_observation_ref is not None and stored.sample_observation_ref != scan_filter.sample_observation_ref:
        return False
    if scan_filter.record_type is not None and stored.record_type != scan_filter.record_type:
        return False
    recorded_at = stored.record.envelope.recorded_at
    if scan_filter.start_time is not None and recorded_at < scan_filter.start_time:
        return False
    if scan_filter.end_time is not None and recorded_at > scan_filter.end_time:
        return False
    return True


def _segment_id_from_path(segment_path: Path) -> int:
    stem = segment_path.stem
    prefix = "segment-"
    if not stem.startswith(prefix):
        raise RecordError(
            "Segment file name does not match the canonical layout.",
            code="record_scan_invalid_segment_name",
            details={"segment_path": str(segment_path)},
        )
    return int(stem[len(prefix) :])


__all__ = ["scan_records"]
