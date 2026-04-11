"""Replay-based JSONL export for the record truth plane."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...common.io import ensure_directory
from ...contract import to_json
from .models import ReplayMode, ReplayResult, ScanFilter
from .replay import replay_records


def export_jsonl(
    store: Any,
    destination: str | Path,
    scan_filter: ScanFilter | None = None,
    *,
    mode: ReplayMode = ReplayMode.STRICT,
) -> ReplayResult:
    """Export replayable canonical records as JSONL."""

    result = replay_records(store, scan_filter, mode=mode)
    target = Path(destination)
    ensure_directory(target.parent)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for stored in result.records:
            handle.write(to_json(stored.record))
            handle.write("\n")
    return result


__all__ = ["export_jsonl"]
