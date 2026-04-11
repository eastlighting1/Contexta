"""Regression coverage for public recovery examples."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT = ROOT / "examples" / "recovery"


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backup_restore_verify_example(tmp_path):
    module = _load_module("contexta_example_backup_restore_verify", EXAMPLES_ROOT / "backup_restore_verify.py")
    result = module.run_example(tmp_path / "backup-demo")
    assert result["backup_ref"]
    assert Path(result["backup_location"]).exists()
    assert result["restore_status"] == "SUCCESS"
    assert result["restore_applied"] is False


def test_replay_outbox_example(tmp_path):
    module = _load_module("contexta_example_replay_outbox", EXAMPLES_ROOT / "replay_outbox_demo.py")
    result = module.run_example(tmp_path / "replay-demo")
    assert result["status"] == "SUCCESS"
    assert result["acknowledged_count"] == 1
    assert result["pending_count"] == 0
    assert result["replayed_exists"] is True
    assert Path(result["replayed_path"]).exists()


def test_artifact_transfer_example(tmp_path):
    module = _load_module("contexta_example_artifact_transfer", EXAMPLES_ROOT / "artifact_transfer_demo.py")
    result = module.run_example(tmp_path / "artifact-demo")
    assert result["source_binding"] == "artifact:my-proj.run-01.model"
    assert Path(result["export_directory"]).exists()
    assert result["target_artifact_count"] == 1
