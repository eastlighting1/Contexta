"""Runtime capture preview example for Contexta."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig


PROJECT_NAME = "capture-proj"
RUN_NAME = "demo-run"


def _resolve_workspace(workspace: Path | str | None) -> Path:
    if workspace is None:
        root = Path(tempfile.mkdtemp(prefix="contexta-capture-preview-"))
        return root / ".contexta"
    return Path(workspace)


def run_example(workspace: Path | str | None = None) -> dict[str, Any]:
    """Exercise the runtime scope API and record local capture output."""

    workspace_path = _resolve_workspace(workspace)
    ctx = Contexta(
        config=UnifiedConfig(
            project_name=PROJECT_NAME,
            workspace=WorkspaceConfig(root_path=workspace_path),
        )
    )

    with ctx.run(RUN_NAME) as run:
        run.event("dataset.loaded", message="dataset prepared")
        with run.stage("train") as stage:
            stage.metric("accuracy", 0.93, unit="ratio")
            stage.metric("loss", 0.12)

    record_capture_path = ctx.config.workspace.cache_path / "capture" / "record.jsonl"
    captured_record_count = 0
    if record_capture_path.exists():
        captured_record_count = sum(1 for line in record_capture_path.read_text(encoding="utf-8").splitlines() if line)

    return {
        "workspace": str(workspace_path),
        "run_ref": run.ref,
        "record_capture_path": str(record_capture_path),
        "record_capture_exists": record_capture_path.exists(),
        "captured_record_count": captured_record_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Contexta runtime capture preview.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Optional workspace root. Defaults to a temporary .contexta workspace.",
    )
    args = parser.parse_args()

    result = run_example(args.workspace)
    print(f"Workspace: {result['workspace']}")
    print(f"Run ref: {result['run_ref']}")
    print(f"Capture file: {result['record_capture_path']}")
    print(f"Capture file exists: {result['record_capture_exists']}")
    print(f"Captured records: {result['captured_record_count']}")


if __name__ == "__main__":
    main()
