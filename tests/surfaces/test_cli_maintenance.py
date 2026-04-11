"""TST-022: CLI maintenance command tests (report, export, artifact, backup, restore, replay)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from contexta.surfaces.cli.main import run_cli


def _cli(mock_repo, tmp_path, args):
    """Run CLI with mock repo injected."""
    from tests.conftest import make_ctx_with_repo
    ctx = make_ctx_with_repo(mock_repo, tmp_path)
    with patch("contexta.surfaces.cli.main._resolve_context", return_value=ctx):
        return run_cli(args)


# ---------------------------------------------------------------------------
# report snapshot
# ---------------------------------------------------------------------------

class TestCliReportSnapshot:
    def test_report_snapshot_exits_zero(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["report", "snapshot", "my-proj.run-01"])
        assert rc == 0

    def test_report_snapshot_markdown(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["report", "snapshot", "my-proj.run-01", "--render", "markdown"])
        assert rc == 0
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_report_snapshot_json(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["report", "snapshot", "my-proj.run-01", "--render", "json"])
        assert rc == 0

    def test_report_snapshot_html(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["report", "snapshot", "my-proj.run-01", "--render", "html"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "<" in out  # HTML content

    def test_report_snapshot_to_file(self, mock_repo, tmp_path, capsys):
        output_path = tmp_path / "report.md"
        rc = _cli(mock_repo, tmp_path, ["report", "snapshot", "my-proj.run-01", "--output", str(output_path)])
        assert rc == 0
        assert output_path.exists()


# ---------------------------------------------------------------------------
# report compare
# ---------------------------------------------------------------------------

class TestCliReportCompare:
    def test_report_compare_exits_zero(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["report", "compare", "my-proj.run-01", "my-proj.run-02"])
        assert rc == 0

    def test_report_compare_json(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["report", "compare", "my-proj.run-01", "my-proj.run-02", "--render", "json"])
        assert rc == 0


# ---------------------------------------------------------------------------
# export html
# ---------------------------------------------------------------------------

class TestCliExportHtml:
    def test_export_html_with_run(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["export", "html", "--run", "my-proj.run-01"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "<" in out

    def test_export_html_with_compare(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["export", "html", "--left", "my-proj.run-01", "--right", "my-proj.run-02"])
        assert rc == 0

    def test_export_html_to_file(self, mock_repo, tmp_path, capsys):
        output_path = tmp_path / "report.html"
        rc = _cli(mock_repo, tmp_path, ["export", "html", "--run", "my-proj.run-01", "--output", str(output_path)])
        assert rc == 0
        assert output_path.exists()


# ---------------------------------------------------------------------------
# export csv
# ---------------------------------------------------------------------------

class TestCliExportCsv:
    def test_export_csv_runs(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["export", "csv", "runs"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "run_id" in out

    def test_export_csv_runs_with_project(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["export", "csv", "runs", "--project", "my-proj"])
        assert rc == 0

    def test_export_csv_runs_to_file(self, mock_repo, tmp_path, capsys):
        output_path = tmp_path / "runs.csv"
        rc = _cli(mock_repo, tmp_path, ["export", "csv", "runs", "--output", str(output_path)])
        assert rc == 0
        assert output_path.exists()

    def test_export_csv_compare(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["export", "csv", "compare", "my-proj.run-01", "my-proj.run-02"])
        assert rc == 0

    def test_export_csv_trend(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["export", "csv", "trend", "loss"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "metric_key" in out or "run_id" in out

    def test_export_csv_anomaly(self, mock_repo, tmp_path, capsys):
        rc = _cli(mock_repo, tmp_path, ["export", "csv", "anomaly", "my-proj.run-01"])
        assert rc == 0


# ---------------------------------------------------------------------------
# backup create
# ---------------------------------------------------------------------------

def _make_ctx_with_backup_root(mock_repo, tmp_path):
    """Create Contexta with a proper RecoveryConfig.backup_root."""
    from contexta.api.client import Contexta
    from contexta.config.models import UnifiedConfig, WorkspaceConfig, RecoveryConfig
    from contexta.interpretation.query.service import QueryService

    backup_root = tmp_path / "backups"
    backup_root.mkdir(exist_ok=True)
    workspace = tmp_path / ".contexta"
    workspace.mkdir(exist_ok=True)
    (workspace / "dummy.txt").write_text("data")

    config = UnifiedConfig(
        project_name="my-proj",
        workspace=WorkspaceConfig(root_path=workspace),
        recovery=RecoveryConfig(backup_root=backup_root),
    )
    ctx = Contexta(config=config)
    ctx._repository = mock_repo
    ctx._query_service = QueryService(mock_repo)
    return ctx


class TestCliBackupCreate:
    def test_backup_create_exits_zero(self, mock_repo, tmp_path, capsys):
        ctx = _make_ctx_with_backup_root(mock_repo, tmp_path)
        with patch("contexta.surfaces.cli.main._resolve_context", return_value=ctx):
            rc = run_cli(["backup", "create", "--label", "test"])
        assert rc == 0

    def test_backup_creates_zip(self, mock_repo, tmp_path, capsys):
        ctx = _make_ctx_with_backup_root(mock_repo, tmp_path)
        output_path = tmp_path / "my-backup"
        with patch("contexta.surfaces.cli.main._resolve_context", return_value=ctx):
            rc = run_cli(["backup", "create", "--output", str(output_path)])
        zip_path = Path(str(output_path) + ".zip")
        assert rc == 0
        assert zip_path.exists()


# ---------------------------------------------------------------------------
# restore apply (verify-only mode - no actual restore needed)
# ---------------------------------------------------------------------------

class TestCliRestoreApply:
    def test_restore_verify_only(self, tmp_path, capsys):
        # Create a dummy zip to "verify"
        zip_path = tmp_path / "backup.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(".contexta/dummy.txt", "data")

        rc = run_cli(["restore", "apply", str(zip_path), "--verify-only"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Verified" in out or "backup" in out.lower()

    def test_restore_missing_backup_returns_nonzero(self, tmp_path, capsys):
        rc = run_cli(["restore", "apply", str(tmp_path / "nonexistent.zip")])
        assert rc != 0


# ---------------------------------------------------------------------------
# recover replay
# ---------------------------------------------------------------------------

class TestCliRecoverReplay:
    def test_recover_replay_exits_zero(self, mock_repo, tmp_path, capsys):
        from tests.conftest import make_ctx_with_repo
        ctx = make_ctx_with_repo(mock_repo, tmp_path)
        # record_store.replay needs an actual RecordStore; patch it
        from unittest.mock import MagicMock
        from contexta.store.records.models import ReplayResult, ReplayMode, IntegrityState
        mock_result = ReplayResult(
            mode=ReplayMode.TOLERANT,
            record_count=0,
            warnings=(),
            known_gaps=(),
            integrity_state=IntegrityState.HEALTHY,
        )
        from unittest.mock import MagicMock
        mock_store = MagicMock()
        mock_store.replay.return_value = mock_result
        ctx._record_store = mock_store
        with patch("contexta.surfaces.cli.main._resolve_context", return_value=ctx):
            rc = run_cli(["recover", "replay"])
        assert rc == 0
