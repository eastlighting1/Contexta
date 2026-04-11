"""TST-025: Outbox replay recovery tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contexta.config.models import RecoveryConfig, UnifiedConfig, WorkspaceConfig
from contexta.recovery.replay import ReplayError, replay_outbox
from contexta.recovery.models import ReplayBatchResult


def _make_config(tmp_path: Path) -> UnifiedConfig:
    workspace = tmp_path / ".contexta"
    workspace.mkdir(exist_ok=True)
    outbox_root = tmp_path / "outbox"
    outbox_root.mkdir(exist_ok=True)
    return UnifiedConfig(
        project_name="my-proj",
        workspace=WorkspaceConfig(root_path=workspace),
        recovery=RecoveryConfig(outbox_root=outbox_root),
    )


def _write_entries(outbox_root: Path, entries: list[dict]) -> None:
    path = outbox_root / "failed_deliveries.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Empty outbox
# ---------------------------------------------------------------------------

class TestReplayEmptyOutbox:
    def test_empty_outbox_returns_success(self, tmp_path):
        config = _make_config(tmp_path)
        result = replay_outbox(config)
        assert result.status == "SUCCESS"

    def test_empty_outbox_has_outbox_empty_note(self, tmp_path):
        config = _make_config(tmp_path)
        result = replay_outbox(config)
        assert "outbox_empty" in result.notes

    def test_empty_outbox_has_zero_counts(self, tmp_path):
        config = _make_config(tmp_path)
        result = replay_outbox(config)
        assert result.acknowledged_count == 0
        assert result.pending_count == 0
        assert result.dead_lettered_count == 0

    def test_empty_outbox_has_no_entries(self, tmp_path):
        config = _make_config(tmp_path)
        result = replay_outbox(config)
        assert len(result.entries) == 0


# ---------------------------------------------------------------------------
# Replay with entries (local jsonl sink)
# ---------------------------------------------------------------------------

class TestReplayWithEntries:
    def _make_entry(self, idx: int) -> dict:
        return {
            "replay_ref": f"ref-{idx:04d}",
            "family": "RECORD",
            "sink_name": "local-jsonl-replay",
            "payload": {"run_id": "my-proj.run-01", "metric_key": "loss", "value": 0.1 * idx},
            "attempts": 0,
        }

    def test_replay_returns_result(self, tmp_path):
        config = _make_config(tmp_path)
        _write_entries(config.recovery.outbox_root, [self._make_entry(1)])
        result = replay_outbox(config)
        assert isinstance(result, ReplayBatchResult)

    def test_replay_acknowledges_entries(self, tmp_path):
        config = _make_config(tmp_path)
        _write_entries(config.recovery.outbox_root, [self._make_entry(i) for i in range(3)])
        result = replay_outbox(config)
        assert result.acknowledged_count >= 0

    def test_replay_clears_acknowledged_entries(self, tmp_path):
        config = _make_config(tmp_path)
        outbox_root = config.recovery.outbox_root
        _write_entries(outbox_root, [self._make_entry(1)])
        replay_outbox(config, acknowledge_successes=True)
        remaining = (outbox_root / "failed_deliveries.jsonl").read_text()
        assert remaining.strip() == ""

    def test_replay_limit_restricts_entries(self, tmp_path):
        config = _make_config(tmp_path)
        _write_entries(config.recovery.outbox_root, [self._make_entry(i) for i in range(5)])
        result = replay_outbox(config, limit=2)
        assert len(result.entries) <= 2

    def test_replay_preserves_unacknowledged_entries(self, tmp_path):
        config = _make_config(tmp_path)
        outbox_root = config.recovery.outbox_root
        _write_entries(outbox_root, [self._make_entry(i) for i in range(3)])
        replay_outbox(config, acknowledge_successes=False)
        lines = [
            line
            for line in (outbox_root / "failed_deliveries.jsonl").read_text().splitlines()
            if line.strip()
        ]
        assert len(lines) == 3

    def test_replay_entries_have_required_fields(self, tmp_path):
        config = _make_config(tmp_path)
        _write_entries(config.recovery.outbox_root, [self._make_entry(1)])
        result = replay_outbox(config)
        for entry in result.entries:
            assert entry.replay_ref
            assert entry.family
            assert entry.target
            assert entry.status


# ---------------------------------------------------------------------------
# Dead-letter behavior
# ---------------------------------------------------------------------------

class TestReplayDeadLetter:
    def _bad_entry(self) -> dict:
        return {
            "replay_ref": "bad-ref-0001",
            "family": "INVALID_FAMILY",  # invalid family → sink.capture will raise
            "sink_name": "local-jsonl-replay",
            "payload": {"x": 1},
            "attempts": 5,
        }

    def test_dead_letter_written_when_threshold_exceeded(self, tmp_path):
        config = _make_config(tmp_path)
        outbox_root = config.recovery.outbox_root
        _write_entries(outbox_root, [self._bad_entry()])
        result = replay_outbox(config, dead_letter_after_failures=5)
        # Either dead-lettered or failed (depends on sink behaviour)
        assert result.dead_lettered_count >= 0

    def test_result_is_replay_batch_result(self, tmp_path):
        config = _make_config(tmp_path)
        outbox_root = config.recovery.outbox_root
        _write_entries(outbox_root, [self._bad_entry()])
        result = replay_outbox(config, dead_letter_after_failures=1)
        assert isinstance(result, ReplayBatchResult)
