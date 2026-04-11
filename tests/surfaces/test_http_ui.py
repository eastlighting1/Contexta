"""TST-024: HTTP UI route and HTML error block tests."""

from __future__ import annotations

import threading
import urllib.request
import urllib.error

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


def _get_html(base_url: str, path: str) -> tuple[int, str]:
    """Make a GET request and return (status_code, html_body)."""
    url = base_url + path
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


# ---------------------------------------------------------------------------
# /ui root redirects to run list
# ---------------------------------------------------------------------------

class TestUiRoot:
    def test_ui_root_returns_200(self, http_server):
        status, html = _get_html(http_server, "/ui")
        assert status == 200

    def test_ui_root_is_html(self, http_server):
        _, html = _get_html(http_server, "/ui")
        assert "<html" in html.lower() or "<!doctype" in html.lower()

    def test_ui_root_contains_runs_table(self, http_server):
        _, html = _get_html(http_server, "/ui")
        assert "runs-table" in html


# ---------------------------------------------------------------------------
# /ui/runs
# ---------------------------------------------------------------------------

class TestUiRuns:
    def test_ui_runs_returns_200(self, http_server):
        status, html = _get_html(http_server, "/ui/runs")
        assert status == 200

    def test_ui_runs_contains_run_id(self, http_server):
        _, html = _get_html(http_server, "/ui/runs")
        assert "my-proj.run-01" in html

    def test_ui_runs_contains_summary_section(self, http_server):
        _, html = _get_html(http_server, "/ui/runs")
        assert "run-list-summary" in html

    def test_ui_runs_with_project_filter(self, http_server):
        status, html = _get_html(http_server, "/ui/runs?project=my-proj")
        assert status == 200

    def test_ui_runs_xss_escaped(self, http_server):
        # project name with XSS payload should be escaped in output
        status, html = _get_html(http_server, "/ui/runs?project=%3Cscript%3Ealert(1)%3C%2Fscript%3E")
        assert status == 200
        assert "<script>alert(1)</script>" not in html


# ---------------------------------------------------------------------------
# /ui/runs/{run_id}
# ---------------------------------------------------------------------------

class TestUiRunDetail:
    def test_ui_run_detail_returns_200(self, http_server):
        status, html = _get_html(http_server, "/ui/runs/my-proj.run-01")
        assert status == 200

    def test_ui_run_detail_contains_run_id(self, http_server):
        _, html = _get_html(http_server, "/ui/runs/my-proj.run-01")
        assert "my-proj.run-01" in html

    def test_ui_run_detail_has_stage_section(self, http_server):
        _, html = _get_html(http_server, "/ui/runs/my-proj.run-01")
        assert "stage" in html.lower()


# ---------------------------------------------------------------------------
# /ui/runs/{run_id}/diagnostics
# ---------------------------------------------------------------------------

class TestUiRunDiagnostics:
    def test_ui_diagnostics_returns_200(self, http_server):
        status, html = _get_html(http_server, "/ui/runs/my-proj.run-01/diagnostics")
        assert status == 200

    def test_ui_diagnostics_is_html(self, http_server):
        _, html = _get_html(http_server, "/ui/runs/my-proj.run-01/diagnostics")
        assert "<" in html


# ---------------------------------------------------------------------------
# /ui/compare
# ---------------------------------------------------------------------------

class TestUiCompare:
    def test_ui_compare_returns_200(self, http_server):
        status, html = _get_html(http_server, "/ui/compare?left=my-proj.run-01&right=my-proj.run-02")
        assert status == 200

    def test_ui_compare_contains_run_ids(self, http_server):
        _, html = _get_html(http_server, "/ui/compare?left=my-proj.run-01&right=my-proj.run-02")
        assert "my-proj.run-01" in html
        assert "my-proj.run-02" in html

    def test_ui_compare_missing_left_returns_400(self, http_server):
        status, html = _get_html(http_server, "/ui/compare?right=my-proj.run-02")
        assert status == 400

    def test_ui_compare_unknown_run_returns_error(self, http_server):
        # Unknown run IDs should return an error response
        status, body = _get_html(http_server, "/ui/compare?left=nonexistent.run-01&right=my-proj.run-02")
        assert status in (400, 404, 500)


# ---------------------------------------------------------------------------
# /ui/metrics/trend
# ---------------------------------------------------------------------------

class TestUiMetricTrend:
    def test_ui_trend_returns_200(self, http_server):
        status, html = _get_html(http_server, "/ui/metrics/trend?metric=loss")
        assert status == 200

    def test_ui_trend_contains_metric_key(self, http_server):
        _, html = _get_html(http_server, "/ui/metrics/trend?metric=loss")
        assert "loss" in html

    def test_ui_trend_missing_metric_returns_400(self, http_server):
        status, html = _get_html(http_server, "/ui/metrics/trend")
        assert status == 400

    def test_ui_trend_has_trend_summary(self, http_server):
        _, html = _get_html(http_server, "/ui/metrics/trend?metric=loss")
        assert "trend-summary" in html


# ---------------------------------------------------------------------------
# HTML error blocks
# ---------------------------------------------------------------------------

class TestHtmlErrorBlocks:
    def test_unknown_ui_route_returns_400(self, http_server):
        status, html = _get_html(http_server, "/ui/nonexistent/route")
        assert status == 400

    def test_unknown_api_path_returns_404_json(self, http_server):
        import json, urllib.error
        url = http_server + "/unknown/api"
        try:
            with urllib.request.urlopen(url) as resp:
                status = resp.status
                body = resp.read().decode()
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read().decode()
        assert status == 404
        data = json.loads(body)
        assert "error" in data
        assert data["error"]["code"] == "http_not_found"

    def test_error_envelope_structure(self, http_server):
        import json, urllib.error
        url = http_server + "/does/not/exist"
        try:
            with urllib.request.urlopen(url) as resp:
                body = resp.read().decode()
                status = resp.status
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read().decode()
        data = json.loads(body)
        err = data.get("error", {})
        assert "code" in err
        assert "message" in err
