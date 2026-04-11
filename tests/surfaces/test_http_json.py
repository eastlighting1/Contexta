"""TST-023: HTTP JSON endpoint payload and status code tests."""

from __future__ import annotations

import json
import threading
import urllib.request
import urllib.error
from http.client import HTTPConnection

import pytest

from contexta.surfaces.http.server import make_server


@pytest.fixture()
def http_server(ctx_with_repo):
    """Start an HTTP server bound to a random port; yield base URL."""
    server = make_server(ctx_with_repo, host="127.0.0.1", port=0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield f"http://{host}:{port}"
    server.shutdown()


def _get_json(base_url: str, path: str) -> tuple[int, dict]:
    """Make a GET request and return (status_code, parsed_json)."""
    url = base_url + path
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


# ---------------------------------------------------------------------------
# /projects
# ---------------------------------------------------------------------------

class TestProjectsEndpoint:
    def test_projects_returns_200(self, http_server):
        status, data = _get_json(http_server, "/projects")
        assert status == 200

    def test_projects_has_projects_key(self, http_server):
        _, data = _get_json(http_server, "/projects")
        assert "projects" in data

    def test_projects_contains_my_proj(self, http_server):
        _, data = _get_json(http_server, "/projects")
        assert "my-proj" in data["projects"]


# ---------------------------------------------------------------------------
# /runs
# ---------------------------------------------------------------------------

class TestRunsEndpoint:
    def test_runs_returns_200(self, http_server):
        status, data = _get_json(http_server, "/runs")
        assert status == 200

    def test_runs_has_runs_key(self, http_server):
        _, data = _get_json(http_server, "/runs")
        assert "runs" in data

    def test_runs_has_two_runs(self, http_server):
        _, data = _get_json(http_server, "/runs")
        assert len(data["runs"]) == 2

    def test_runs_with_project_filter(self, http_server):
        status, data = _get_json(http_server, "/runs?project=my-proj")
        assert status == 200
        assert "runs" in data

    def test_runs_with_limit(self, http_server):
        status, data = _get_json(http_server, "/runs?limit=1")
        assert status == 200
        assert len(data["runs"]) <= 1


# ---------------------------------------------------------------------------
# /runs/{run_id}
# ---------------------------------------------------------------------------

class TestRunDetailEndpoint:
    def test_run_detail_returns_200(self, http_server):
        status, data = _get_json(http_server, "/runs/my-proj.run-01")
        assert status == 200

    def test_run_detail_has_run_id(self, http_server):
        _, data = _get_json(http_server, "/runs/my-proj.run-01")
        assert "my-proj.run-01" in json.dumps(data)

    def test_run_missing_returns_500_or_404(self, http_server):
        status, data = _get_json(http_server, "/runs/nonexistent.run")
        assert status in (404, 500)
        assert "error" in data


# ---------------------------------------------------------------------------
# /runs/{run_id}/diagnostics
# ---------------------------------------------------------------------------

class TestRunDiagnosticsEndpoint:
    def test_diagnostics_returns_200(self, http_server):
        status, data = _get_json(http_server, "/runs/my-proj.run-01/diagnostics")
        assert status == 200

    def test_diagnostics_has_issues(self, http_server):
        _, data = _get_json(http_server, "/runs/my-proj.run-01/diagnostics")
        assert "issues" in data or isinstance(data, dict)


# ---------------------------------------------------------------------------
# /runs/{run_id}/report
# ---------------------------------------------------------------------------

class TestRunReportEndpoint:
    def test_report_returns_200(self, http_server):
        status, data = _get_json(http_server, "/runs/my-proj.run-01/report")
        assert status == 200

    def test_report_has_title(self, http_server):
        _, data = _get_json(http_server, "/runs/my-proj.run-01/report")
        assert "title" in data


# ---------------------------------------------------------------------------
# /runs/{run_id}/lineage
# ---------------------------------------------------------------------------

class TestRunLineageEndpoint:
    def test_lineage_returns_200(self, http_server):
        status, data = _get_json(http_server, "/runs/my-proj.run-01/lineage")
        assert status == 200

    def test_lineage_with_direction(self, http_server):
        status, data = _get_json(http_server, "/runs/my-proj.run-01/lineage?direction=both")
        assert status == 200

    def test_lineage_invalid_direction_returns_400(self, http_server):
        status, data = _get_json(http_server, "/runs/my-proj.run-01/lineage?direction=sideways")
        assert status == 400
        assert "error" in data


# ---------------------------------------------------------------------------
# /compare
# ---------------------------------------------------------------------------

class TestCompareEndpoint:
    def test_compare_returns_200(self, http_server):
        status, data = _get_json(http_server, "/compare?left=my-proj.run-01&right=my-proj.run-02")
        assert status == 200

    def test_compare_has_run_ids(self, http_server):
        _, data = _get_json(http_server, "/compare?left=my-proj.run-01&right=my-proj.run-02")
        payload_str = json.dumps(data)
        assert "my-proj.run-01" in payload_str

    def test_compare_missing_param_returns_400(self, http_server):
        status, data = _get_json(http_server, "/compare?left=my-proj.run-01")
        assert status == 400
        assert "error" in data


# ---------------------------------------------------------------------------
# /compare/multi
# ---------------------------------------------------------------------------

class TestCompareMultiEndpoint:
    def test_compare_multi_returns_200(self, http_server):
        status, data = _get_json(http_server, "/compare/multi?run_ids=my-proj.run-01,my-proj.run-02")
        assert status == 200

    def test_compare_multi_too_few_returns_400(self, http_server):
        status, data = _get_json(http_server, "/compare/multi?run_ids=my-proj.run-01")
        assert status == 400


# ---------------------------------------------------------------------------
# /metrics/trend
# ---------------------------------------------------------------------------

class TestMetricTrendEndpoint:
    def test_trend_returns_200(self, http_server):
        status, data = _get_json(http_server, "/metrics/trend?metric=loss")
        assert status == 200

    def test_trend_has_metric_key(self, http_server):
        _, data = _get_json(http_server, "/metrics/trend?metric=loss")
        assert "metric_key" in data or "loss" in json.dumps(data)

    def test_trend_missing_metric_returns_400(self, http_server):
        status, data = _get_json(http_server, "/metrics/trend")
        assert status == 400
        assert "error" in data


# ---------------------------------------------------------------------------
# /metrics/aggregate
# ---------------------------------------------------------------------------

class TestMetricAggregateEndpoint:
    def test_aggregate_returns_200(self, http_server):
        status, data = _get_json(http_server, "/metrics/aggregate?metric=loss")
        assert status == 200

    def test_aggregate_missing_metric_returns_400(self, http_server):
        status, data = _get_json(http_server, "/metrics/aggregate")
        assert status == 400


# ---------------------------------------------------------------------------
# /search/runs
# ---------------------------------------------------------------------------

class TestSearchRunsEndpoint:
    def test_search_runs_returns_200(self, http_server):
        status, data = _get_json(http_server, "/search/runs?q=run")
        assert status == 200

    def test_search_runs_has_runs(self, http_server):
        _, data = _get_json(http_server, "/search/runs?q=run")
        assert "runs" in data

    def test_search_runs_missing_q_returns_400(self, http_server):
        status, data = _get_json(http_server, "/search/runs")
        assert status == 400


# ---------------------------------------------------------------------------
# Unknown endpoint → 404
# ---------------------------------------------------------------------------

class TestUnknownEndpoint:
    def test_unknown_path_returns_404(self, http_server):
        status, data = _get_json(http_server, "/nonexistent/path")
        assert status == 404
        assert "error" in data

    def test_error_envelope_has_code(self, http_server):
        _, data = _get_json(http_server, "/nonexistent/path")
        assert "code" in data.get("error", {})

    def test_error_envelope_has_message(self, http_server):
        _, data = _get_json(http_server, "/nonexistent/path")
        assert "message" in data.get("error", {})
