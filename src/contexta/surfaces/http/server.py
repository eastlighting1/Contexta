"""Embedded local-only HTTP server for Contexta JSON and UI surfaces."""

from __future__ import annotations

from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import parse_qs, unquote, urlparse

from ...api import Contexta
from ...common.errors import ContextaError
from ...interpretation import (
    AggregationService,
    AlertRule,
    AnomalyService,
    RunListQuery,
    TimeRange,
)
from ..html import (
    DashboardConfig,
    render_html_comparison,
    render_html_dashboard,
    render_html_run_detail,
    render_html_run_list,
    render_html_trend,
)
from ..html.templates import note_block, page_header, page_shell, raw_section, stat_grid, table_card
from .serializers import (
    environment_diff_payload,
    error_envelope,
    reproducibility_payload,
    run_summary_payload,
    to_jsonable,
)


def make_server(contexta: Contexta, host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
    handler = partial(ContextaRequestHandler, contexta=contexta)
    return ThreadingHTTPServer((host, port), handler)


def serve(contexta: Contexta, host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
    server = make_server(contexta, host=host, port=port)
    server.serve_forever()
    return server


class ContextaRequestHandler(BaseHTTPRequestHandler):
    server_version = "ContextaHTTP/0.1"

    def __init__(self, *args, contexta: Contexta, **kwargs) -> None:
        self.contexta = contexta
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query, keep_blank_values=False)
        try:
            if path == "/projects":
                return self._write_json(200, {"projects": list(self.contexta.list_projects())})
            if path == "/runs":
                return self._handle_runs(query)
            if path.startswith("/runs/"):
                return self._handle_run_routes(path, query)
            if path == "/compare":
                return self._handle_compare(query)
            if path == "/compare/multi":
                return self._handle_compare_multi(query)
            if path == "/metrics/trend":
                return self._handle_metric_trend(query)
            if path == "/metrics/aggregate":
                return self._handle_metric_aggregate(query)
            if path.startswith("/alerts/evaluate/"):
                return self._handle_alerts(path, query)
            if path == "/search/runs":
                return self._handle_search_runs(query)
            if path == "/search/artifacts":
                return self._handle_search_artifacts(query)
            if path in {"/ui", "/ui/"} or path == "/ui":
                return self._write_html(200, render_html_run_list(self.contexta))
            if path.startswith("/ui/"):
                return self._handle_ui_routes(path, query)
            return self._write_json(404, error_envelope("http_not_found", f"Unknown endpoint: {path}"))
        except ValueError as exc:
            return self._write_json(400, error_envelope("http_bad_request", str(exc)))
        except ContextaError as exc:
            return self._write_json(500, error_envelope(getattr(exc, "code", "contexta_error"), str(exc), getattr(exc, "details", None)))
        except Exception as exc:  # noqa: BLE001
            return self._write_json(500, error_envelope("http_internal_error", "Unexpected internal error.", {"type": type(exc).__name__, "message": str(exc)}))

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return None

    def _handle_runs(self, query: dict[str, list[str]]) -> None:
        run_query = _build_run_list_query(query)
        runs = self.contexta.list_runs(_query_value(query, "project"), query=run_query)
        self._write_json(200, {"runs": to_jsonable(runs)})

    def _handle_run_routes(self, path: str, query: dict[str, list[str]]) -> None:
        parts = [part for part in path.split("/") if part]
        if len(parts) < 2:
            raise ValueError("run_id is required.")
        run_id = unquote(parts[1])
        if len(parts) == 2:
            snapshot = self.contexta.get_run_snapshot(run_id)
            return self._write_json(200, run_summary_payload(snapshot))
        suffix = parts[2]
        if suffix == "diagnostics":
            return self._write_json(200, to_jsonable(self.contexta.diagnose_run(run_id)))
        if suffix == "lineage":
            direction = _query_value(query, "direction")
            mapped_direction = None
            if direction == "upstream":
                mapped_direction = "inbound"
            elif direction == "downstream":
                mapped_direction = "outbound"
            elif direction in {None, "both", "inbound", "outbound"}:
                mapped_direction = direction
            else:
                raise ValueError("direction must be upstream, downstream, inbound, outbound, or both.")
            depth = _parse_int(query, "depth", default=3)
            snapshot = self.contexta.get_run_snapshot(run_id)
            subject_ref = snapshot.run.run_id
            return self._write_json(
                200,
                to_jsonable(self.contexta.traverse_lineage(subject_ref, direction=mapped_direction, max_depth=depth)),
            )
        if suffix == "report":
            return self._write_json(200, self.contexta.build_snapshot_report(run_id).to_json())
        if suffix == "anomalies":
            return self._handle_run_anomalies(run_id, query)
        if suffix == "reproducibility":
            return self._write_json(200, reproducibility_payload(self.contexta.audit_reproducibility(run_id)))
        if suffix == "environment-diff" and len(parts) >= 4:
            return self._write_json(
                200,
                environment_diff_payload(self.contexta.compare_environments(run_id, parts[3])),
            )
        raise ValueError(f"Unsupported run route suffix: {suffix}")

    def _handle_compare(self, query: dict[str, list[str]]) -> None:
        left = _required_query(query, "left")
        right = _required_query(query, "right")
        self._write_json(200, to_jsonable(self.contexta.compare_runs(left, right)))

    def _handle_compare_multi(self, query: dict[str, list[str]]) -> None:
        run_ids = [item for item in _required_query(query, "run_ids").split(",") if item]
        if len(run_ids) < 2:
            raise ValueError("run_ids must contain at least two ids.")
        self._write_json(200, to_jsonable(self.contexta.compare_multiple_runs(run_ids)))

    def _handle_metric_trend(self, query: dict[str, list[str]]) -> None:
        metric = _required_query(query, "metric")
        run_query = _build_run_list_query(query)
        payload = self.contexta.get_metric_trend(
            metric,
            project_name=_query_value(query, "project"),
            stage_name=_query_value(query, "stage"),
            query=run_query,
        )
        self._write_json(200, to_jsonable(payload))

    def _handle_metric_aggregate(self, query: dict[str, list[str]]) -> None:
        metric = _required_query(query, "metric")
        service = _aggregation_service(self.contexta)
        payload = service.aggregate_metric(
            metric,
            query=_build_run_list_query(query),
            project_name=_query_value(query, "project"),
            stage_name=_query_value(query, "stage"),
        )
        self._write_json(200, to_jsonable(payload))

    def _handle_run_anomalies(self, run_id: str, query: dict[str, list[str]]) -> None:
        service = _anomaly_service(self.contexta)
        metric = _query_value(query, "metric")
        metric_keys = None if metric is None else (metric,)
        baseline_query = None
        project = _query_value(query, "project")
        if project is not None:
            baseline_query = RunListQuery(project_name=project)
        payload = service.detect_anomalies_in_run(
            run_id,
            baseline_query=baseline_query,
            metric_keys=metric_keys,
            stage_name=_query_value(query, "stage"),
        )
        self._write_json(200, {"anomalies": to_jsonable(payload)})

    def _handle_alerts(self, path: str, query: dict[str, list[str]]) -> None:
        run_id = unquote(path.split("/")[-1])
        rule = AlertRule(
            metric_key=_required_query(query, "metric"),
            operator=_required_query(query, "operator"),
            threshold=float(_required_query(query, "threshold")),
            stage_name=_query_value(query, "stage"),
            severity=_query_value(query, "severity") or self.contexta.config.interpretation.alert.default_severity,
        )
        payload = self.contexta.evaluate_alerts(run_id, [rule])
        self._write_json(200, {"results": to_jsonable(payload)})

    def _handle_search_runs(self, query: dict[str, list[str]]) -> None:
        term = _required_query(query, "q").lower()
        limit = _parse_int(query, "limit", default=20)
        runs = self.contexta.list_runs(
            _query_value(query, "project"),
            status=_query_value(query, "status"),
            limit=limit,
        )
        payload = [
            run for run in runs
            if term in run.run_id.lower() or term in run.name.lower() or term in run.project_name.lower()
        ]
        self._write_json(200, {"runs": to_jsonable(tuple(payload[:limit]))})

    def _handle_search_artifacts(self, query: dict[str, list[str]]) -> None:
        term = _required_query(query, "q").lower()
        kind = _query_value(query, "kind")
        artifacts = self.contexta.repository.list_artifacts()
        payload = [
            artifact
            for artifact in artifacts
            if term in artifact.artifact_ref.lower()
            or term in artifact.kind.lower()
            or term in (artifact.location or "").lower()
        ]
        if kind is not None:
            payload = [artifact for artifact in payload if artifact.kind == kind]
        self._write_json(200, {"artifacts": to_jsonable(tuple(payload))})

    def _handle_ui_routes(self, path: str, query: dict[str, list[str]]) -> None:
        parts = [part for part in path.split("/") if part]
        if parts == ["ui", "runs"]:
            return self._write_html(
                200,
                render_html_run_list(
                    self.contexta,
                    project_name=_query_value(query, "project"),
                    query=_build_run_list_query(query),
                ),
            )
        if len(parts) >= 3 and parts[1] == "runs" and len(parts) == 3:
            return self._write_html(200, render_html_run_detail(self.contexta, parts[2]))
        if len(parts) >= 4 and parts[1] == "runs" and parts[3] == "diagnostics":
            return self._write_html(200, _render_diagnostics_page(self.contexta, parts[2]))
        if len(parts) >= 4 and parts[1] == "runs" and parts[3] == "anomalies":
            return self._write_html(200, _render_anomalies_page(self.contexta, parts[2], query))
        if parts == ["ui", "compare"]:
            return self._write_html(200, render_html_comparison(self.contexta, _required_query(query, "left"), _required_query(query, "right")))
        if parts == ["ui", "compare", "multi"]:
            return self._write_html(200, _render_compare_multi_page(self.contexta, query))
        if parts == ["ui", "metrics", "trend"]:
            return self._write_html(
                200,
                render_html_trend(
                    self.contexta,
                    _required_query(query, "metric"),
                    project_name=_query_value(query, "project"),
                    stage_name=_query_value(query, "stage"),
                    query=_build_run_list_query(query),
                ),
            )
        if parts == ["ui", "metrics", "aggregate"]:
            return self._write_html(200, _render_aggregate_page(self.contexta, query))
        raise ValueError(f"Unsupported UI route: {'/'.join(parts)}")

    def _write_json(self, status: int, payload: dict[str, object] | list[object]) -> None:
        body = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_html(self, status: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _build_run_list_query(query: dict[str, list[str]]) -> RunListQuery | None:
    after = _query_value(query, "after")
    before = _query_value(query, "before")
    time_range = None
    if after is not None or before is not None:
        time_range = TimeRange(started_after=after, started_before=before)
    limit = _parse_int(query, "limit", default=None)
    offset = _parse_int(query, "offset", default=0)
    sort_by = _query_value(query, "sort") or "started_at"
    desc_text = _query_value(query, "desc")
    sort_desc = True if desc_text is None else desc_text.lower() in {"1", "true", "yes"}
    if all(
        value is None
        for value in (
            _query_value(query, "status"),
            after,
            before,
            limit,
        )
    ) and offset == 0 and sort_by == "started_at" and sort_desc is True:
        return None
    return RunListQuery(
        status=_query_value(query, "status"),
        time_range=time_range,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )


def _required_query(query: dict[str, list[str]], key: str) -> str:
    value = _query_value(query, key)
    if value is None:
        raise ValueError(f"Missing required query parameter: {key}")
    return value


def _query_value(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    return values[0]


def _parse_int(query: dict[str, list[str]], key: str, default: int | None) -> int | None:
    value = _query_value(query, key)
    if value is None:
        return default
    return int(value)


def _aggregation_service(ctx: Contexta) -> AggregationService:
    return AggregationService(ctx.query_service, metric_aggregation=ctx.config.interpretation.trend.metric_aggregation)


def _anomaly_service(ctx: Contexta) -> AnomalyService:
    return AnomalyService(
        ctx.query_service,
        z_score_threshold=ctx.config.interpretation.anomaly.z_score_threshold,
        min_baseline_runs=ctx.config.interpretation.anomaly.min_baseline_runs,
        monitored_metrics=ctx.config.interpretation.anomaly.monitored_metrics,
        metric_aggregation=ctx.config.interpretation.trend.metric_aggregation,
    )


def _render_diagnostics_page(ctx: Contexta, run_id: str) -> str:
    diagnostics = ctx.diagnose_run(run_id)
    body = (
        page_header(f"Diagnostics: {run_id}")
        + raw_section(
            section_id="diagnostics-summary",
            title="Summary",
            body=f"<p>{len(diagnostics.issues)} issue(s) found.</p>",
        )
        + table_card(
            section_id="diagnostics-issues",
            title="Issues",
            headers=("Severity", "Code", "Summary", "Subject"),
            rows=tuple(
                (
                    issue.severity,
                    issue.code,
                    issue.summary,
                    issue.subject_ref,
                )
                for issue in diagnostics.issues
            ),
            empty_text="No diagnostic issues.",
        )
        + note_block(
            section_id="diagnostics-notes",
            title="Completeness Notes",
            notes=tuple(note.summary for note in diagnostics.completeness_notes),
        )
    )
    return page_shell(title=f"Diagnostics: {run_id}", body=body)


def _render_anomalies_page(ctx: Contexta, run_id: str, query: dict[str, list[str]]) -> str:
    metric = _query_value(query, "metric")
    metric_keys = None if metric is None else (metric,)
    project = _query_value(query, "project")
    baseline_query = None if project is None else RunListQuery(project_name=project)
    anomalies = _anomaly_service(ctx).detect_anomalies_in_run(
        run_id,
        baseline_query=baseline_query,
        metric_keys=metric_keys,
        stage_name=_query_value(query, "stage"),
    )
    body = (
        page_header(f"Anomalies: {run_id}")
        + table_card(
            section_id="anomalies-table",
            title="Anomalies",
            headers=("Metric", "Actual", "Expected Range", "Z Score", "Severity"),
            rows=tuple(
                (
                    item.metric_key,
                    str(item.actual_value),
                    f"{item.expected_range[0]}..{item.expected_range[1]}",
                    str(item.z_score),
                    item.severity,
                )
                for item in anomalies
            ),
            empty_text="No anomalies detected.",
        )
    )
    return page_shell(title=f"Anomalies: {run_id}", body=body)


def _render_compare_multi_page(ctx: Contexta, query: dict[str, list[str]]) -> str:
    run_ids = [item for item in _required_query(query, "run_ids").split(",") if item]
    comparison = ctx.compare_multiple_runs(run_ids)
    body = (
        page_header("Compare Multi")
        + raw_section(
            section_id="comparison-summary",
            title="Summary",
            body=f"<p>{comparison.summary}</p>",
        )
        + table_card(
            section_id="comparison-stage-table",
            title="Metric Table",
            headers=("Stage", "Metric", "Values", "Best Run"),
            rows=tuple(
                (
                    row.stage_name or "run",
                    row.metric_key,
                    ", ".join("" if value is None else str(value) for value in row.values),
                    row.best_run_id or "",
                )
                for row in comparison.metric_table
            ),
            empty_text="No multi-run metric rows.",
        )
    )
    return page_shell(title="Compare Multi", body=body)


def _render_aggregate_page(ctx: Contexta, query: dict[str, list[str]]) -> str:
    metric = _required_query(query, "metric")
    aggregate = _aggregation_service(ctx).aggregate_metric(
        metric,
        query=_build_run_list_query(query),
        project_name=_query_value(query, "project"),
        stage_name=_query_value(query, "stage"),
    )
    body = (
        page_header(f"Aggregate: {metric}")
        + stat_grid(
            (
                ("Count", str(aggregate.count)),
                ("Mean", str(aggregate.mean)),
                ("Std", str(aggregate.std)),
                ("Min", str(aggregate.min)),
                ("Max", str(aggregate.max)),
            ),
            section_id="trend-summary",
            title="Aggregate Summary",
        )
        + note_block(
            section_id="trend-notes",
            title="Completeness Notes",
            notes=tuple(note.summary for note in aggregate.completeness_notes),
        )
    )
    return page_shell(title=f"Aggregate: {metric}", body=body)


__all__ = ["ContextaRequestHandler", "make_server", "serve"]
