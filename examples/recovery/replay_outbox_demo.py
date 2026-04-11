"""Outbox replay example for Contexta."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from contexta.config import RecoveryConfig, UnifiedConfig, WorkspaceConfig
from contexta.recovery import replay_outbox


def _resolve_root(root: Path | str | None) -> Path:
    if root is None:
        return Path(tempfile.mkdtemp(prefix="contexta-replay-demo-"))
    return Path(root)


def _write_failed_delivery(outbox_root: Path) -> Path:
    outbox_root.mkdir(parents=True, exist_ok=True)
    path = outbox_root / "failed_deliveries.jsonl"
    entry = {
        "replay_ref": "replay:record.demo.0001",
        "family": "RECORD",
        "sink_name": "local-jsonl-replay",
        "payload": {"run_id": "recovery-proj.demo-run", "metric_key": "loss", "value": 0.12},
        "attempts": 0,
    }
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    return path


def run_example(root: Path | str | None = None) -> dict[str, Any]:
    base_root = _resolve_root(root)
    workspace = base_root / ".contexta"
    outbox_root = base_root / "outbox"

    config = UnifiedConfig(
        project_name="recovery-proj",
        workspace=WorkspaceConfig(root_path=workspace),
        recovery=RecoveryConfig(outbox_root=outbox_root),
    )

    failed_deliveries_path = _write_failed_delivery(outbox_root)
    result = replay_outbox(config)
    replayed_path = config.workspace.exports_path / "replayed" / "record.jsonl"

    return {
        "outbox_path": str(failed_deliveries_path),
        "status": result.status,
        "acknowledged_count": result.acknowledged_count,
        "pending_count": result.pending_count,
        "dead_lettered_count": result.dead_lettered_count,
        "replayed_path": str(replayed_path),
        "replayed_exists": replayed_path.exists(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Contexta outbox replay example.")
    parser.add_argument("--root", type=Path, default=None, help="Optional demo root directory.")
    args = parser.parse_args()

    result = run_example(args.root)
    print(f"Outbox path: {result['outbox_path']}")
    print(f"Replay status: {result['status']}")
    print(f"Acknowledged: {result['acknowledged_count']}")
    print(f"Pending: {result['pending_count']}")
    print(f"Dead-lettered: {result['dead_lettered_count']}")
    print(f"Replayed output: {result['replayed_path']}")


if __name__ == "__main__":
    main()
