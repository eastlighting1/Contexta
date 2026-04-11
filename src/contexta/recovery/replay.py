"""Outbox replay helpers for recovery orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from ..capture.sinks.local import LocalJsonlSink
from ..capture.sinks.protocol import Sink
from ..common.errors import RecoveryError
from ..common.io import ensure_directory
from ..common.time import iso_utc_now
from ..config import UnifiedConfig
from .models import ReplayBatchResult, ReplayEntryResult


class ReplayError(RecoveryError):
    """Raised when recovery replay orchestration fails."""


def replay_outbox(
    config: UnifiedConfig,
    *,
    target: str | None = None,
    limit: int | None = None,
    acknowledge_successes: bool = True,
    dead_letter_after_failures: int | None = None,
    sinks: Sequence[Sink] | None = None,
) -> ReplayBatchResult:
    outbox_root = config.recovery.outbox_root
    if outbox_root is None:
        raise ReplayError("Recovery outbox_root is not configured.", code="recovery_outbox_root_missing")
    failed_deliveries_path = Path(outbox_root) / "failed_deliveries.jsonl"
    if not failed_deliveries_path.exists():
        return ReplayBatchResult(
            status="SUCCESS",
            entries=(),
            acknowledged_count=0,
            pending_count=0,
            dead_lettered_count=0,
            notes=("outbox_empty",),
        )

    entries = _load_entries(failed_deliveries_path)
    active_entries = entries[: limit if limit is not None else len(entries)]
    remaining_entries = entries[len(active_entries) :]
    sink = _resolve_target_sink(config=config, target=target, sinks=sinks)

    results: list[ReplayEntryResult] = []
    pending: list[dict[str, Any]] = list(remaining_entries)
    dead_letters: list[dict[str, Any]] = []
    acknowledged_count = 0

    for entry in active_entries:
        if target is not None and entry.get("sink_name") != target and target != sink.name:
            results.append(
                ReplayEntryResult(
                    replay_ref=str(entry.get("replay_ref", "")),
                    family=str(entry.get("family", "")),
                    target=target,
                    status="SKIPPED",
                    detail="entry target does not match selected target",
                    attempts=int(entry.get("attempts", 0)),
                )
            )
            pending.append(entry)
            continue

        try:
            receipt = sink.capture(family=str(entry["family"]).upper(), payload=entry["payload"])
        except Exception as exc:  # noqa: BLE001
            attempts = int(entry.get("attempts", 0)) + 1
            updated = dict(entry)
            updated["attempts"] = attempts
            updated["last_replayed_at"] = iso_utc_now()
            updated["last_error"] = str(exc)
            status = "FAILURE"
            if dead_letter_after_failures is not None and attempts >= dead_letter_after_failures:
                dead_letters.append(updated)
            else:
                pending.append(updated)
            results.append(
                ReplayEntryResult(
                    replay_ref=str(entry.get("replay_ref", "")),
                    family=str(entry.get("family", "")),
                    target=sink.name,
                    status=status,
                    detail=str(exc),
                    attempts=attempts,
                )
            )
            continue

        results.append(
            ReplayEntryResult(
                replay_ref=str(entry.get("replay_ref", "")),
                family=str(entry.get("family", "")),
                target=sink.name,
                status=receipt.status.value,
                detail=receipt.detail,
                attempts=int(entry.get("attempts", 0)),
            )
        )
        if acknowledge_successes:
            acknowledged_count += 1
        else:
            pending.append(entry)

    _write_entries(failed_deliveries_path, pending)
    if dead_letters:
        _append_dead_letters(Path(outbox_root) / "dead_letter.jsonl", dead_letters)

    failure_count = sum(1 for item in results if item.status == "FAILURE")
    degraded = any(item.status in {"FAILURE", "SKIPPED"} for item in results)
    status = "DEGRADED" if degraded else "SUCCESS"
    if failure_count == len(results) and results:
        status = "FAILURE"
    notes = ()
    if dead_letters:
        notes = (f"dead_lettered:{len(dead_letters)}",)
    return ReplayBatchResult(
        status=status,
        entries=tuple(results),
        acknowledged_count=acknowledged_count,
        pending_count=len(pending),
        dead_lettered_count=len(dead_letters),
        notes=notes,
    )


def _resolve_target_sink(
    *,
    config: UnifiedConfig,
    target: str | None,
    sinks: Sequence[Sink] | None,
) -> Sink:
    if sinks:
        if target is None:
            return sinks[0]
        for sink in sinks:
            if sink.name == target:
                return sink
        raise ReplayError(
            "Requested replay target sink was not provided.",
            code="recovery_replay_target_missing",
            details={"target": target},
        )
    replay_root = ensure_directory(config.workspace.exports_path / "replayed")
    return LocalJsonlSink(replay_root, name=target or "local-jsonl-replay")


def _load_entries(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise ReplayError("Outbox entry must be a JSON object.", code="recovery_invalid_outbox_entry")
            entries.append(payload)
    return entries


def _write_entries(path: Path, entries: Sequence[dict[str, Any]]) -> None:
    if not entries:
        path.write_text("", encoding="utf-8", newline="\n")
        return
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str))
            handle.write("\n")


def _append_dead_letters(path: Path, entries: Sequence[dict[str, Any]]) -> None:
    ensure_directory(path.parent)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str))
            handle.write("\n")


__all__ = ["ReplayError", "replay_outbox"]
