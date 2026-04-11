"""TST-021: CLI query command tests (runs, compare, diagnostics, lineage, trend)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from contexta.surfaces.cli.main import run_cli


def _cli(mock_repo, tmp_path, args):
    """Run CLI with mock repo injected via patched _resolve_context."""
    from tests.conftest import make_ctx_with_repo
    ctx = make_ctx_with_repo(mock_repo, tmp_path)
    with patch("contexta.surfaces.cli.main._resolve_context", return_value=ctx):
        return run_cli(args)


# ---------------------------------------------------------------------------
# runs / run list
# ---------------------------------------------------------------------------

class TestCliRuns:
    def test_runs_exits_zero(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["runs"])
        assert rc == 0

    def test_runs_output_contains_run_id(self, mock_repo, tmp_path, capsys):
        _cli(mock_repo, tmp_path, ["runs"])
        out = capsys.readouterr().out
        assert "my-proj.run-01" in out

    def test_runs_json_format(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["--format", "json", "runs"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "runs" in data

    def test_run_list_alias(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["run", "list"])
        assert rc == 0

    def test_runs_with_project_filter(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["runs", "--project", "my-proj"])
        assert rc == 0

    def test_runs_with_limit(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["runs", "--limit", "1"])
        assert rc == 0
        out = capsys.readouterr().out
        # At most 1 run listed
        assert out.count("my-proj.run-0") <= 2  # header + 1 run line


# ---------------------------------------------------------------------------
# run show
# ---------------------------------------------------------------------------

class TestCliRunShow:
    def test_run_show_exits_zero(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["run", "show", "my-proj.run-01"])
        assert rc == 0

    def test_run_show_contains_run_id(self, mock_repo, tmp_path, capsys):
        _cli(mock_repo, tmp_path, ["run", "show", "my-proj.run-01"])
        out = capsys.readouterr().out
        assert "my-proj.run-01" in out

    def test_run_show_json_format(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["--format", "json", "run", "show", "my-proj.run-01"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "run_id" in data or "run" in data


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------

class TestCliCompare:
    def test_compare_exits_zero(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["compare", "my-proj.run-01", "my-proj.run-02"])
        assert rc == 0

    def test_compare_json_format(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["--format", "json", "compare", "my-proj.run-01", "my-proj.run-02"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "left_run_id" in data or "left" in str(data)

    def test_compare_run_alias(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["run", "compare", "my-proj.run-01", "my-proj.run-02"])
        assert rc == 0

    def test_compare_multi(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["compare-multi", "my-proj.run-01", "my-proj.run-02"])
        assert rc == 0


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------

class TestCliDiagnostics:
    def test_diagnostics_exits_zero(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["diagnostics", "my-proj.run-01"])
        assert rc == 0

    def test_diagnostics_json_format(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["--format", "json", "diagnostics", "my-proj.run-01"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, dict)

    def test_diagnostics_run_alias(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["run", "diagnose", "my-proj.run-01"])
        assert rc == 0

    def test_diagnostics_fail_on_no_issues(self, mock_repo, tmp_path, capsys):
        # Should still exit 0 when no issues match fail-on threshold
        rc = _cli(mock_repo, tmp_path, ["diagnostics", "my-proj.run-01", "--fail-on", "error"])
        assert rc == 0


# ---------------------------------------------------------------------------
# lineage
# ---------------------------------------------------------------------------

class TestCliLineage:
    def test_lineage_exits_zero(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["lineage", "my-proj.run-01"])
        assert rc == 0

    def test_lineage_with_direction(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["lineage", "my-proj.run-01", "--direction", "both"])
        assert rc == 0

    def test_lineage_with_depth(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["lineage", "my-proj.run-01", "--depth", "2"])
        assert rc == 0

    def test_lineage_json_format(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["--format", "json", "lineage", "my-proj.run-01"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# trend
# ---------------------------------------------------------------------------

class TestCliTrend:
    def test_trend_exits_zero(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["trend", "loss"])
        assert rc == 0

    def test_trend_with_project(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["trend", "loss", "--project", "my-proj"])
        assert rc == 0

    def test_trend_json_format(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["--format", "json", "trend", "loss"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "metric_key" in data or "points" in str(data)

    def test_aggregate_exits_zero(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["aggregate", "loss"])
        assert rc == 0

    def test_aggregate_json_format(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["--format", "json", "aggregate", "loss"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

class TestCliSearch:
    def test_search_runs_exits_zero(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["search", "runs", "run"])
        assert rc == 0

    def test_search_artifacts_exits_zero(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["search", "artifacts", "model"])
        assert rc == 0
