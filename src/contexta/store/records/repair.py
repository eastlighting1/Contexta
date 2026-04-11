"""Repair helpers for the record truth plane."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...common.io import atomic_write_json, ensure_directory
from ...common.time import iso_utc_now
from .integrity import check_integrity
from .models import IntegrityState


@dataclass(frozen=True, slots=True)
class RepairReport:
    success: bool
    repaired_segments: tuple[int, ...] = ()
    quarantined_paths: tuple[str, ...] = ()
    rebuilt_indexes: bool = False
    integrity_state: IntegrityState = IntegrityState.DEGRADED
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def rebuild_indexes(store: Any) -> RepairReport:
    """Rebuild derived indexes from current readable segment truth."""

    indexes_root = store._indexes_dir()
    temp_root = store.root_path / ".tmp-indexes"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    ensure_directory(temp_root)

    warnings: list[str] = []
    try:
        for family in ("run_ref", "stage_execution_ref", "record_type"):
            ensure_directory(temp_root / family)
        for segment_path in sorted(store._segments_dir().glob("segment-*.jsonl")):
            segment_id = int(segment_path.stem.removeprefix("segment-"))
            raw_lines = segment_path.read_bytes().splitlines(keepends=True)
            for line_number, raw_line in enumerate(raw_lines, start=1):
                try:
                    text = raw_line.decode("utf-8")
                    payload = json.loads(text)
                    record = payload["record"]
                    envelope = record["envelope"]
                except Exception:
                    warnings.append(f"skipped unreadable line at segment {segment_id} line {line_number}")
                    continue
                pointer = json.dumps(
                    {"sequence": int(payload["sequence"]), "segment_id": segment_id, "offset": line_number},
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ) + "\n"
                _append_pointer(temp_root / "run_ref", str(envelope["run_ref"]), pointer)
                _append_pointer(temp_root / "record_type", str(envelope["record_type"]), pointer)
                stage_ref = envelope.get("stage_execution_ref")
                if stage_ref:
                    _append_pointer(temp_root / "stage_execution_ref", str(stage_ref), pointer)
        if indexes_root.exists():
            shutil.rmtree(indexes_root)
        temp_root.replace(indexes_root)
    finally:
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)

    report = check_integrity(store)
    return RepairReport(
        success=not any("unreadable" in warning for warning in warnings),
        repaired_segments=(),
        quarantined_paths=(),
        rebuilt_indexes=True,
        integrity_state=report.state,
        notes=("rebuild_indexes_completed",),
        warnings=tuple(warnings),
    )


def repair_truncated_tails(store: Any) -> RepairReport:
    """Repair only trailing truncated tail lines and rebuild indexes afterwards."""

    repaired_segments: list[int] = []
    quarantined_paths: list[str] = []
    warnings: list[str] = []

    for segment_path in sorted(store._segments_dir().glob("segment-*.jsonl")):
        segment_id = int(segment_path.stem.removeprefix("segment-"))
        raw = segment_path.read_bytes()
        if not raw:
            continue
        lines = raw.splitlines(keepends=True)
        if not lines:
            continue
        last_line = lines[-1]
        has_newline = last_line.endswith(b"\n") or last_line.endswith(b"\r")
        if has_newline:
            continue
        try:
            json.loads(last_line.decode("utf-8"))
            continue
        except Exception:
            pass

        bad_middle = False
        last_good_sequence = 0
        last_good_count = 0
        kept_lines: list[bytes] = []
        for raw_line in lines[:-1]:
            try:
                payload = json.loads(raw_line.decode("utf-8"))
                last_good_sequence = int(payload["sequence"])
                kept_lines.append(raw_line)
                last_good_count += 1
            except Exception:
                bad_middle = True
                break
        if bad_middle:
            warnings.append(f"segment {segment_id} has unreadable middle corruption; tail repair skipped")
            continue

        quarantine = store._quarantine_dir() / f"segment-{segment_id:06d}.before-tail-repair-{_safe_timestamp()}.jsonl"
        ensure_directory(quarantine.parent)
        shutil.copy2(segment_path, quarantine)
        quarantined_paths.append(str(quarantine))
        segment_path.write_bytes(b"".join(kept_lines))
        repaired_segments.append(segment_id)

        manifest = store._load_manifest()
        if manifest.current_segment_id == segment_id:
            updated = manifest.__class__(
                layout_mode=manifest.layout_mode,
                layout_version=manifest.layout_version,
                current_segment_id=manifest.current_segment_id,
                next_sequence=last_good_sequence + 1,
                last_committed_sequence=last_good_sequence,
                current_segment_record_count=last_good_count,
            )
            atomic_write_json(store._manifest_path(), updated.to_dict(), indent=2, sort_keys=True)

    rebuilt = rebuild_indexes(store)
    report = check_integrity(store)
    return RepairReport(
        success=bool(repaired_segments) and report.state is not IntegrityState.CORRUPTED,
        repaired_segments=tuple(repaired_segments),
        quarantined_paths=tuple(quarantined_paths),
        rebuilt_indexes=True,
        integrity_state=report.state,
        notes=("repair_truncated_tails_completed",) if repaired_segments else (),
        warnings=tuple(warnings) + rebuilt.warnings,
    )


def _append_pointer(root: Path, key: str, pointer: str) -> None:
    safe_key = key.replace(":", "__")
    for bad in ('\\', '/', '*', '?', '"', '<', '>', '|', ' '):
        safe_key = safe_key.replace(bad, "_")
    target = root / f"{safe_key}.jsonl"
    ensure_directory(target.parent)
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(pointer)


def _safe_timestamp() -> str:
    return iso_utc_now().replace(":", "").replace("-", "")


__all__ = ["RepairReport", "rebuild_indexes", "repair_truncated_tails"]
