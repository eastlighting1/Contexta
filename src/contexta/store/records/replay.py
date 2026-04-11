"""Replay helpers for the record truth plane."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from ...common.errors import RecordError
from .models import IntegrityState, KnownGap, ReplayMode, ReplayResult, ScanFilter, StoredRecord
from .read import _deserialize_record_payload, _matches_filter, _segment_id_from_path


class ReplayError(RecordError):
    """Raised when replay cannot provide a coherent result in the chosen mode."""


@dataclass(frozen=True, slots=True)
class _ReplayCollection:
    records: tuple[StoredRecord, ...]
    warnings: tuple[str, ...]
    known_gaps: tuple[KnownGap, ...]
    integrity_state: IntegrityState


def replay_records(
    store: Any,
    scan_filter: ScanFilter | None = None,
    *,
    mode: ReplayMode = ReplayMode.STRICT,
) -> ReplayResult:
    active_filter = scan_filter or ScanFilter()
    collection = _collect_replay(store, active_filter)
    if mode is ReplayMode.STRICT and (collection.warnings or collection.known_gaps):
        raise ReplayError(
            "Strict replay failed because the record store is not healthy.",
            code="record_replay_unhealthy_store",
            details={
                "warnings": list(collection.warnings),
                "known_gaps": [gap.code for gap in collection.known_gaps],
                "integrity_state": collection.integrity_state.value,
            },
        )
    if mode is ReplayMode.STRICT:
        return ReplayResult(
            records=collection.records,
            record_count=len(collection.records),
            mode=mode,
            warnings=(),
            known_gaps=(),
            integrity_state=IntegrityState.HEALTHY,
        )
    return ReplayResult(
        records=collection.records,
        record_count=len(collection.records),
        mode=mode,
        warnings=collection.warnings,
        known_gaps=collection.known_gaps,
        integrity_state=collection.integrity_state,
    )


def iter_replay_records(
    store: Any,
    scan_filter: ScanFilter | None = None,
    *,
    mode: ReplayMode = ReplayMode.STRICT,
) -> Iterator[StoredRecord]:
    result = replay_records(store, scan_filter, mode=mode)
    yield from result.records


def _collect_replay(store: Any, scan_filter: ScanFilter) -> _ReplayCollection:
    manifest = store._load_manifest()
    records: list[StoredRecord] = []
    warnings: list[str] = []
    known_gaps: list[KnownGap] = []
    expected_sequence: int | None = None
    highest_sequence = 0

    segment_paths = sorted(store._segments_dir().glob("segment-*.jsonl"))
    for segment_path in segment_paths:
        segment_id = _segment_id_from_path(segment_path)
        raw_lines = segment_path.read_bytes().splitlines(keepends=True)
        for line_number, raw_line in enumerate(raw_lines, start=1):
            has_newline = raw_line.endswith(b"\n") or raw_line.endswith(b"\r")
            try:
                text = raw_line.decode("utf-8")
            except UnicodeDecodeError:
                known_gaps.append(
                    KnownGap(
                        code="invalid_json_line",
                        message="Segment line is not valid UTF-8.",
                        segment_id=segment_id,
                        line_number=line_number,
                    )
                )
                warnings.append(f"segment {segment_id} line {line_number} is not valid UTF-8")
                continue
            if not text.strip():
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                code = "truncated_line" if line_number == len(raw_lines) and not has_newline else "invalid_json_line"
                known_gaps.append(
                    KnownGap(
                        code=code,
                        message="Segment line could not be decoded as JSON.",
                        segment_id=segment_id,
                        line_number=line_number,
                    )
                )
                warnings.append(f"{code} at segment {segment_id} line {line_number}")
                continue
            try:
                stored = StoredRecord(
                    sequence=int(payload["sequence"]),
                    segment_id=segment_id,
                    offset=line_number,
                    appended_at=payload["appended_at"],
                    record=_deserialize_record_payload(payload["record"]),
                )
            except Exception:
                known_gaps.append(
                    KnownGap(
                        code="invalid_json_line",
                        message="Stored line could not be materialized into a canonical record.",
                        segment_id=segment_id,
                        line_number=line_number,
                    )
                )
                warnings.append(f"materialization failed at segment {segment_id} line {line_number}")
                continue

            if expected_sequence is not None and stored.sequence != expected_sequence:
                known_gaps.append(
                    KnownGap(
                        code="sequence_gap",
                        message="Replay detected a non-contiguous sequence.",
                        segment_id=segment_id,
                        line_number=line_number,
                        start_sequence=expected_sequence,
                        end_sequence=stored.sequence - 1,
                    )
                )
                warnings.append(
                    f"sequence gap before segment {segment_id} line {line_number}: expected {expected_sequence}, got {stored.sequence}"
                )
            expected_sequence = stored.sequence + 1
            highest_sequence = max(highest_sequence, stored.sequence)
            if _matches_filter(stored, scan_filter=scan_filter):
                records.append(stored)

    if manifest.last_committed_sequence != highest_sequence:
        warnings.append(
            f"manifest sequence mismatch: committed={manifest.last_committed_sequence}, observed={highest_sequence}"
        )

    integrity_state = _derive_integrity_state(warnings=tuple(warnings), known_gaps=tuple(known_gaps))
    return _ReplayCollection(
        records=tuple(records),
        warnings=tuple(warnings),
        known_gaps=tuple(known_gaps),
        integrity_state=integrity_state,
    )


def _derive_integrity_state(
    *,
    warnings: tuple[str, ...],
    known_gaps: tuple[KnownGap, ...],
) -> IntegrityState:
    if not warnings and not known_gaps:
        return IntegrityState.HEALTHY
    if any(gap.code in {"invalid_json_line", "truncated_line"} for gap in known_gaps):
        return IntegrityState.CORRUPTED
    return IntegrityState.DEGRADED


__all__ = ["ReplayError", "iter_replay_records", "replay_records"]
