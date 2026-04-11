"""Regression coverage for public quickstart examples."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT = ROOT / "examples" / "quickstart"


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verified_quickstart_reaches_query_and_report(tmp_path):
    module = _load_module(
        "contexta_example_verified_quickstart",
        EXAMPLES_ROOT / "verified_quickstart.py",
    )

    result = module.run_example(tmp_path / ".contexta")

    assert result["run_ref"] == "run:quickstart-proj.demo-run"
    assert result["runs_visible"] == 1
    assert result["snapshot_stage_count"] == 1
    assert "demo-run" in result["report_title"]
    assert Path(result["report_path"]).exists()


def test_runtime_capture_preview_writes_record_payloads(tmp_path):
    module = _load_module(
        "contexta_example_runtime_capture_preview",
        EXAMPLES_ROOT / "runtime_capture_preview.py",
    )

    result = module.run_example(tmp_path / ".contexta")

    assert result["run_ref"] == "run:capture-proj.demo-run"
    assert result["record_capture_exists"] is True
    assert result["captured_record_count"] >= 3
    assert Path(result["record_capture_path"]).exists()
