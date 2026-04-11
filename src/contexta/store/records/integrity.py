"""Integrity scan for the record truth plane."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import IntegrityState, KnownGap


@dataclass(frozen=True, slots=True)
class IntegrityIssue:
    severity: str
    code: str
    message: str
    segment_id: int | None = None
    line_number: int | None = None


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    healthy: bool
    issues: tuple[IntegrityIssue, ...] = ()
    segment_count: int = 0
    record_count: int = 0
    state: IntegrityState = IntegrityState.HEALTHY
    recommendations: tuple[str, ...] = ()


def check_integrity(store: Any) -> IntegrityReport:
    """Scan record segments and manifest for integrity issues."""

    manifest = store._load_manifest()
    segment_paths = sorted(store._segments_dir().glob("segment-*.jsonl"))
    issues: list[IntegrityIssue] = []
    recommendations: list[str] = []
    record_count = 0
    expected_sequence: int | None = None
    highest_sequence = 0

    for segment_path in segment_paths:
        segment_id = _segment_id_from_path(segment_path)
        raw_lines = segment_path.read_bytes().splitlines(keepends=True)
        last_line_number = len(raw_lines)
        for line_number, raw_line in enumerate(raw_lines, start=1):
            has_newline = raw_line.endswith(b"\n") or raw_line.endswith(b"\r")
            try:
                text = raw_line.decode("utf-8")
            except UnicodeDecodeError:
                issues.append(
                    IntegrityIssue(
                        severity="error",
                        code="invalid_json_line",
                        message="Segment line is not valid UTF-8.",
                        segment_id=segment_id,
                        line_number=line_number,
                    )
                )
                continue
            if not text.strip():
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                issues.append(
                    IntegrityIssue(
                        severity="error",
                        code="truncated_line" if line_number == last_line_number and not has_newline else "invalid_json_line",
                        message="Segment line could not be decoded as JSON.",
                        segment_id=segment_id,
                        line_number=line_number,
                    )
                )
                continue
            try:
                sequence = int(payload["sequence"])
            except Exception:
                issues.append(
                    IntegrityIssue(
                        severity="error",
                        code="invalid_json_line",
                        message="Segment line is missing a valid sequence.",
                        segment_id=segment_id,
                        line_number=line_number,
                    )
                )
                continue
            if expected_sequence is not None and sequence != expected_sequence:
                issues.append(
                    IntegrityIssue(
                        severity="warning",
                        code="sequence_gap",
                        message="Record sequence is not contiguous.",
                        segment_id=segment_id,
                        line_number=line_number,
                    )
                )
            expected_sequence = sequence + 1
            highest_sequence = max(highest_sequence, sequence)
            record_count += 1

    if manifest.last_committed_sequence != highest_sequence:
        issues.append(
            IntegrityIssue(
                severity="warning",
                code="manifest_sequence_mismatch",
                message="Manifest committed sequence does not match observed segment truth.",
            )
        )

    codes = {issue.code for issue in issues}
    if "truncated_line" in codes:
        recommendations.append("repair_truncated_tails")
    if codes & {"invalid_json_line", "sequence_gap", "manifest_sequence_mismatch"}:
        recommendations.append("rebuild_indexes")

    state = _derive_state(tuple(issues))
    return IntegrityReport(
        healthy=state is IntegrityState.HEALTHY,
        issues=tuple(issues),
        segment_count=len(segment_paths),
        record_count=record_count,
        state=state,
        recommendations=tuple(dict.fromkeys(recommendations)),
    )


def _derive_state(issues: tuple[IntegrityIssue, ...]) -> IntegrityState:
    if not issues:
        return IntegrityState.HEALTHY
    if any(issue.code in {"invalid_json_line", "truncated_line"} and issue.severity == "error" for issue in issues):
        return IntegrityState.CORRUPTED
    return IntegrityState.DEGRADED


def _segment_id_from_path(segment_path: Path) -> int:
    return int(segment_path.stem.removeprefix("segment-"))


__all__ = ["IntegrityIssue", "IntegrityReport", "check_integrity"]
