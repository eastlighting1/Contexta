"""Embedded CLI surface for Contexta."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Sequence

from ... import Contexta, ContextaError
from ...common.io import ensure_directory, json_dumps, resolve_path, write_text
from ...config import UnifiedConfig, load_config
from ...contract import ArtifactManifest
from ...interpretation import AggregationService, AlertRule, AnomalyService, RunListQuery, TimeRange
from ...store.records import ReplayMode, ScanFilter
from ...surfaces.export import (
    export_anomaly_csv,
    export_comparison_csv,
    export_run_list_csv,
    export_trend_csv,
)
from ...surfaces.http import make_server
from ...surfaces.http.serializers import to_jsonable


def build_parser(*, prog: str = "contexta") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description="Contexta command surface")
    parser.add_argument("--workspace", default=".contexta", help='Workspace root. Default: ".contexta"')
    parser.add_argument("--profile", choices=("local", "test"), help="Config profile name.")
    parser.add_argument("--config", dest="config_file", help="External JSON/TOML config patch.")
    parser.add_argument("--set", dest="set_values", action="append", default=[], help="Direct config override in key=value form.")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Result output format.")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-result status lines.")

    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    runs = subparsers.add_parser("runs", help="List runs.")
    _add_run_list_options(runs)
    runs.set_defaults(handler=_cmd_run_list)

    run = subparsers.add_parser("run", help="Run-oriented commands.")
    run_subparsers = run.add_subparsers(dest="run_command")
    run_subparsers.required = True

    run_list = run_subparsers.add_parser("list", help="List runs.")
    _add_run_list_options(run_list)
    run_list.set_defaults(handler=_cmd_run_list)

    run_show = run_subparsers.add_parser("show", help="Show one run snapshot.")
    run_show.add_argument("run_id")
    run_show.set_defaults(handler=_cmd_run_show)

    run_compare = run_subparsers.add_parser("compare", help="Compare two runs.")
    run_compare.add_argument("left_run_id")
    run_compare.add_argument("right_run_id")
    run_compare.set_defaults(handler=_cmd_compare)

    run_compare_many = run_subparsers.add_parser("compare-many", help="Compare multiple runs.")
    run_compare_many.add_argument("run_ids", nargs="+")
    run_compare_many.set_defaults(handler=_cmd_compare_many)

    run_diagnose = run_subparsers.add_parser("diagnose", help="Diagnose one run.")
    run_diagnose.add_argument("run_id")
    run_diagnose.add_argument("--fail-on", choices=("info", "warning", "error"))
    run_diagnose.set_defaults(handler=_cmd_diagnostics)

    lineage = subparsers.add_parser("lineage", help="Trace lineage for a subject ref.")
    lineage.add_argument("subject_ref")
    lineage.add_argument("--direction", choices=("upstream", "downstream", "inbound", "outbound", "both"))
    lineage.add_argument("--depth", type=int, default=3)
    lineage.set_defaults(handler=_cmd_lineage)

    search = subparsers.add_parser("search", help="Search runs or artifacts.")
    search_subparsers = search.add_subparsers(dest="search_command")
    search_subparsers.required = True

    search_runs = search_subparsers.add_parser("runs", help="Search runs.")
    search_runs.add_argument("text")
    search_runs.add_argument("--project")
    search_runs.add_argument("--status")
    search_runs.add_argument("--limit", type=int, default=20)
    search_runs.set_defaults(handler=_cmd_search_runs)

    search_artifacts = search_subparsers.add_parser("artifacts", help="Search artifacts.")
    search_artifacts.add_argument("text")
    search_artifacts.add_argument("--kind")
    search_artifacts.add_argument("--limit", type=int, default=20)
    search_artifacts.set_defaults(handler=_cmd_search_artifacts)

    compare = subparsers.add_parser("compare", help="Compare two runs.")
    compare.add_argument("left_run_id")
    compare.add_argument("right_run_id")
    compare.set_defaults(handler=_cmd_compare)

    compare_multi = subparsers.add_parser("compare-multi", help="Compare multiple runs.")
    compare_multi.add_argument("run_ids", nargs="+")
    compare_multi.set_defaults(handler=_cmd_compare_many)

    diagnostics = subparsers.add_parser("diagnostics", help="Diagnose one run.")
    diagnostics.add_argument("run_id")
    diagnostics.add_argument("--fail-on", choices=("info", "warning", "error"))
    diagnostics.set_defaults(handler=_cmd_diagnostics)

    trend = subparsers.add_parser("trend", help="Show metric trend.")
    _add_metric_query_options(trend)
    trend.set_defaults(handler=_cmd_trend)

    aggregate = subparsers.add_parser("aggregate", help="Show metric aggregate.")
    _add_metric_query_options(aggregate)
    aggregate.set_defaults(handler=_cmd_aggregate)

    anomaly = subparsers.add_parser("anomaly", help="Detect run anomalies.")
    anomaly.add_argument("run_id")
    anomaly.add_argument("--metric", action="append", dest="metrics", default=[])
    anomaly.add_argument("--project")
    anomaly.add_argument("--stage")
    anomaly.set_defaults(handler=_cmd_anomaly)

    alert = subparsers.add_parser("alert", help="Evaluate a threshold alert.")
    alert.add_argument("run_id")
    alert.add_argument("--metric", required=True)
    alert.add_argument("--operator", required=True, choices=("gt", "lt", "gte", "lte", "eq", "ne"))
    alert.add_argument("--threshold", required=True, type=float)
    alert.add_argument("--stage")
    alert.add_argument("--severity", default="warning")
    alert.set_defaults(handler=_cmd_alert)

    report = subparsers.add_parser("report", help="Build report documents.")
    report_subparsers = report.add_subparsers(dest="report_command")
    report_subparsers.required = True

    report_snapshot = report_subparsers.add_parser("snapshot", help="Build a snapshot report.")
    report_snapshot.add_argument("run_id")
    report_snapshot.add_argument("--render", choices=("markdown", "json", "html", "csv"), default="markdown")
    report_snapshot.add_argument("--output")
    report_snapshot.set_defaults(handler=_cmd_report_snapshot)

    report_compare = report_subparsers.add_parser("compare", help="Build a comparison report.")
    report_compare.add_argument("left_run_id")
    report_compare.add_argument("right_run_id")
    report_compare.add_argument("--render", choices=("markdown", "json", "html", "csv"), default="markdown")
    report_compare.add_argument("--output")
    report_compare.set_defaults(handler=_cmd_report_compare)

    export = subparsers.add_parser("export", help="Export HTML or CSV materializations.")
    export_subparsers = export.add_subparsers(dest="export_command")
    export_subparsers.required = True

    export_html = export_subparsers.add_parser("html", help="Export report HTML.")
    export_html.add_argument("--run")
    export_html.add_argument("--left")
    export_html.add_argument("--right")
    export_html.add_argument("--output")
    export_html.set_defaults(handler=_cmd_export_html)

    export_csv = export_subparsers.add_parser("csv", help="Export CSV data.")
    export_csv_subparsers = export_csv.add_subparsers(dest="export_csv_command")
    export_csv_subparsers.required = True

    export_csv_runs = export_csv_subparsers.add_parser("runs", help="Export run list CSV.")
    export_csv_runs.add_argument("--project")
    export_csv_runs.add_argument("--status")
    export_csv_runs.add_argument("--after")
    export_csv_runs.add_argument("--before")
    export_csv_runs.add_argument("--sort", choices=("started_at", "ended_at", "name"), default="started_at")
    export_csv_runs.add_argument("--desc", action="store_true")
    export_csv_runs.add_argument("--limit", type=int)
    export_csv_runs.add_argument("--offset", type=int, default=0)
    export_csv_runs.add_argument("--output")
    export_csv_runs.set_defaults(handler=_cmd_export_csv_runs)

    export_csv_compare = export_csv_subparsers.add_parser("compare", help="Export comparison CSV.")
    export_csv_compare.add_argument("left_run_id")
    export_csv_compare.add_argument("right_run_id")
    export_csv_compare.add_argument("--output")
    export_csv_compare.set_defaults(handler=_cmd_export_csv_compare)

    export_csv_trend = export_csv_subparsers.add_parser("trend", help="Export trend CSV.")
    _add_metric_query_options(export_csv_trend, include_output=True)
    export_csv_trend.set_defaults(handler=_cmd_export_csv_trend)

    export_csv_anomaly = export_csv_subparsers.add_parser("anomaly", help="Export anomaly CSV.")
    export_csv_anomaly.add_argument("run_id")
    export_csv_anomaly.add_argument("--metric", action="append", dest="metrics", default=[])
    export_csv_anomaly.add_argument("--project")
    export_csv_anomaly.add_argument("--stage")
    export_csv_anomaly.add_argument("--output")
    export_csv_anomaly.set_defaults(handler=_cmd_export_csv_anomaly)

    serve = subparsers.add_parser("serve", help="Serve embedded adapters.")
    serve_subparsers = serve.add_subparsers(dest="serve_command")
    serve_subparsers.required = True

    serve_http = serve_subparsers.add_parser("http", help="Start embedded HTTP server.")
    serve_http.add_argument("--host", default="127.0.0.1")
    serve_http.add_argument("--port", type=int, default=8080)
    serve_http.set_defaults(handler=_cmd_serve_http)

    provenance = subparsers.add_parser("provenance", help="Run provenance checks.")
    provenance_subparsers = provenance.add_subparsers(dest="provenance_command")
    provenance_subparsers.required = True

    provenance_audit = provenance_subparsers.add_parser("audit", help="Audit run reproducibility.")
    provenance_audit.add_argument("run_id")
    provenance_audit.set_defaults(handler=_cmd_provenance_audit)

    provenance_diff = provenance_subparsers.add_parser("diff", help="Compare run environments.")
    provenance_diff.add_argument("left_run_id")
    provenance_diff.add_argument("right_run_id")
    provenance_diff.set_defaults(handler=_cmd_provenance_diff)

    artifact = subparsers.add_parser("artifact", help="Artifact operations.")
    artifact_subparsers = artifact.add_subparsers(dest="artifact_command")
    artifact_subparsers.required = True

    artifact_register = artifact_subparsers.add_parser("register", help="Register an artifact into the store.")
    artifact_register.add_argument("artifact_kind")
    artifact_register.add_argument("source_path")
    artifact_register.add_argument("--run", required=True, dest="run_ref")
    artifact_register.add_argument("--stage", dest="stage_ref")
    artifact_register.add_argument("--artifact-ref")
    artifact_register.add_argument("--mode", choices=("copy", "move", "adopt"), default="copy")
    artifact_register.set_defaults(handler=_cmd_artifact_register)

    artifact_put = artifact_subparsers.add_parser("put", help="Alias for artifact register.")
    artifact_put.add_argument("artifact_kind")
    artifact_put.add_argument("source_path")
    artifact_put.add_argument("--run", required=True, dest="run_ref")
    artifact_put.add_argument("--stage", dest="stage_ref")
    artifact_put.add_argument("--artifact-ref")
    artifact_put.add_argument("--mode", choices=("copy", "move", "adopt"), default="copy")
    artifact_put.set_defaults(handler=_cmd_artifact_register)

    backup = subparsers.add_parser("backup", help="Create workspace backups.")
    backup_subparsers = backup.add_subparsers(dest="backup_command")
    backup_subparsers.required = True
    backup_create = backup_subparsers.add_parser("create", help="Create a workspace zip backup.")
    backup_create.add_argument("--label")
    backup_create.add_argument("--output")
    backup_create.set_defaults(handler=_cmd_backup_create)

    restore = subparsers.add_parser("restore", help="Restore workspace backups.")
    restore_subparsers = restore.add_subparsers(dest="restore_command")
    restore_subparsers.required = True
    restore_apply = restore_subparsers.add_parser("apply", help="Restore a backup into a workspace.")
    restore_apply.add_argument("backup_ref")
    restore_apply.add_argument("--target-workspace")
    restore_apply.add_argument("--verify-only", action="store_true")
    restore_apply.set_defaults(handler=_cmd_restore_apply)

    recover = subparsers.add_parser("recover", help="Record recovery operations.")
    recover_subparsers = recover.add_subparsers(dest="recover_command")
    recover_subparsers.required = True
    recover_replay = recover_subparsers.add_parser("replay", help="Replay stored records.")
    recover_replay.add_argument("--mode", choices=("strict", "tolerant"), default="tolerant")
    recover_replay.add_argument("--run")
    recover_replay.add_argument("--stage")
    recover_replay.add_argument("--record-type", choices=("event", "metric", "span", "degraded"))
    recover_replay.set_defaults(handler=_cmd_recover_replay)

    return parser


def run_cli(argv: Sequence[str] | None = None, *, prog: str = "contexta") -> int:
    parser = build_parser(prog=prog)
    args = parser.parse_args(list(argv) if argv is not None else None)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    try:
        return int(handler(args))
    except KeyboardInterrupt:
        if not getattr(args, "quiet", False):
            print("Interrupted.", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, ContextaError):
            payload = {"error": {"code": getattr(exc, "code", "contexta_error"), "message": str(exc), "details": getattr(exc, "details", None)}}
        else:
            payload = {"error": {"code": type(exc).__name__, "message": str(exc)}}
        if getattr(args, "format", "text") == "json":
            print(json_dumps(to_jsonable(payload), indent=2, sort_keys=True), file=sys.stderr)
        else:
            print(f"ERROR [{payload['error']['code']}]: {payload['error']['message']}", file=sys.stderr)
        return 1
    finally:
        _close_cli_context(getattr(args, "_contexta", None))


def main(argv: Sequence[str] | None = None) -> int:
    return run_cli(argv)


def _add_run_list_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project")
    parser.add_argument("--status")
    parser.add_argument("--after")
    parser.add_argument("--before")
    parser.add_argument("--sort", choices=("started_at", "ended_at", "name"), default="started_at")
    parser.add_argument("--desc", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)


def _add_metric_query_options(parser: argparse.ArgumentParser, *, include_output: bool = False) -> None:
    parser.add_argument("metric_key")
    parser.add_argument("--project")
    parser.add_argument("--stage")
    parser.add_argument("--status")
    parser.add_argument("--after")
    parser.add_argument("--before")
    parser.add_argument("--sort", choices=("started_at", "ended_at", "name"), default="started_at")
    parser.add_argument("--desc", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    if include_output:
        parser.add_argument("--output")


def _resolve_context(args: argparse.Namespace) -> Contexta:
    direct_patch = _parse_set_values(args.set_values)
    resolved: UnifiedConfig = load_config(
        profile=args.profile,
        config_file=args.config_file,
        config=direct_patch or None,
        workspace=args.workspace,
    )
    ctx = Contexta.open(config=resolved)
    setattr(args, "_contexta", ctx)
    return ctx


def _parse_set_values(items: Sequence[str]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError("--set values must use key=value form.")
        key, raw_value = item.split("=", 1)
        dotted = key.strip()
        if not dotted:
            raise ValueError("--set key must not be blank.")
        value = _coerce_cli_value(raw_value.strip())
        _merge_nested_patch(patch, dotted.split("."), value)
    return patch


def _coerce_cli_value(text: str) -> Any:
    lowered = text.lower()
    if lowered in {"null", "none"}:
        return None
    if lowered in {"true", "false"}:
        return lowered == "true"
    if text == "[]":
        return []
    if text and text[0] in {'"', "{", "["}:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def _merge_nested_patch(target: dict[str, Any], keys: list[str], value: Any) -> None:
    cursor = target
    for key in keys[:-1]:
        next_value = cursor.get(key)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[key] = next_value
        cursor = next_value
    cursor[keys[-1]] = value


def _run_query_from_args(args: argparse.Namespace, *, allow_project: bool = True) -> RunListQuery | None:
    project_name = getattr(args, "project", None) if allow_project else None
    status = getattr(args, "status", None)
    after = getattr(args, "after", None)
    before = getattr(args, "before", None)
    limit = getattr(args, "limit", None)
    offset = getattr(args, "offset", 0)
    sort_by = getattr(args, "sort", "started_at")
    sort_desc = bool(getattr(args, "desc", False))
    if all(value is None for value in (project_name, status, after, before, limit)) and offset == 0 and sort_by == "started_at" and sort_desc is False:
        return None
    time_range = None
    if after is not None or before is not None:
        time_range = TimeRange(started_after=after, started_before=before)
    return RunListQuery(
        project_name=project_name,
        status=status,
        time_range=time_range,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )


def _emit(args: argparse.Namespace, *, payload: Any, text: str | None = None, output: str | None = None) -> int:
    if args.format == "json":
        rendered = json_dumps(to_jsonable(payload), indent=2, sort_keys=True)
    else:
        rendered = text if text is not None else _render_text_payload(payload)
    if output:
        write_text(output, rendered + ("" if rendered.endswith("\n") else "\n"))
        if not args.quiet and args.format == "text":
            print(f"Wrote output to {resolve_path(output)}")
        return 0
    print(rendered)
    return 0


def _render_text_payload(payload: Any) -> str:
    value = to_jsonable(payload)
    if isinstance(value, dict):
        return "\n".join(f"{key}: {_render_scalar_or_json(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "\n".join(f"- {_render_scalar_or_json(item)}" for item in value)
    return _render_scalar_or_json(value)


def _render_scalar_or_json(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return str(value)
    return json_dumps(value, indent=2, sort_keys=True)


def _render_report(report: Any, render: str) -> str:
    if render == "json":
        return json_dumps(report.to_json(), indent=2, sort_keys=True)
    if render == "html":
        return report.to_html()
    if render == "csv":
        return report.to_csv()
    return report.to_markdown()


def _severity_exit_code(issues: Sequence[Any], *, fail_on: str | None) -> int:
    if fail_on is None:
        return 0
    order = {"info": 0, "warning": 1, "error": 2}
    threshold = order[fail_on]
    for issue in issues:
        if order.get(issue.severity, -1) >= threshold:
            return 1
    return 0


def _default_artifact_ref(run_ref: str, source_path: str) -> str:
    if ":" not in run_ref:
        raise ValueError("artifact register requires --run to use a canonical run ref like run:project.run-id")
    _, run_value = run_ref.split(":", 1)
    stem = Path(source_path).stem.strip().lower().replace("_", "-").replace(" ", "-")
    stem = "".join(char for char in stem if char.isalnum() or char in {"-", "."}).strip("-.") or "artifact"
    return f"artifact:{run_value}.{stem}"


def _utc_now_text() -> str:
    from ...common.time import iso_utc_now

    return iso_utc_now()


def _safe_timestamp() -> str:
    return _utc_now_text().replace(":", "-").replace(".", "_")


def _close_cli_context(ctx: Contexta | None) -> None:
    if ctx is None:
        return
    metadata_store = getattr(ctx, "_metadata_store", None)
    if metadata_store is not None:
        metadata_store.close()


def _cmd_run_list(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    query = _run_query_from_args(args)
    runs = ctx.list_runs(None, query=query)
    text_lines = ["Runs"]
    if not runs:
        text_lines.append("(empty)")
    else:
        for run in runs:
            text_lines.append(f"{run.run_id}  {run.status}  {run.started_at}  {run.name}")
    return _emit(args, payload={"runs": runs}, text="\n".join(text_lines))


def _cmd_run_show(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    snapshot = ctx.get_run_snapshot(args.run_id)
    text = "\n".join(
        (
            f"Run: {snapshot.run.run_id}",
            f"Project: {snapshot.run.project_name}",
            f"Status: {snapshot.run.status}",
            f"Stages: {len(snapshot.stages)}",
            f"Artifacts: {len(snapshot.artifacts)}",
            f"Records: {len(snapshot.records)}",
            f"Completeness notes: {len(snapshot.completeness_notes)}",
        )
    )
    return _emit(args, payload=snapshot, text=text)


def _cmd_compare(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    comparison = ctx.compare_runs(args.left_run_id, args.right_run_id)
    lines = [f"Compare: {comparison.left_run_id} vs {comparison.right_run_id}", comparison.summary]
    for stage in comparison.stage_comparisons:
        lines.append(f"[{stage.stage_name}] left={stage.left_status or '-'} right={stage.right_status or '-'} deltas={len(stage.metric_deltas)}")
    return _emit(args, payload=comparison, text="\n".join(lines))


def _cmd_compare_many(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    comparison = ctx.compare_multiple_runs(args.run_ids)
    lines = [f"Compare many: {', '.join(comparison.run_ids)}", comparison.summary]
    for row in comparison.metric_table:
        rendered_values = ", ".join("" if value is None else str(value) for value in row.values)
        lines.append(f"{row.stage_name or 'run'} | {row.metric_key} | {rendered_values} | best={row.best_run_id or '-'}")
    return _emit(args, payload=comparison, text="\n".join(lines))


def _cmd_diagnostics(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    diagnostics = ctx.diagnose_run(args.run_id)
    lines = [f"Diagnostics: {args.run_id}", f"Issues: {len(diagnostics.issues)}"]
    for issue in diagnostics.issues:
        lines.append(f"{issue.severity}: {issue.code} | {issue.summary} | {issue.subject_ref}")
    exit_code = _severity_exit_code(diagnostics.issues, fail_on=args.fail_on)
    _emit(args, payload=diagnostics, text="\n".join(lines))
    return exit_code


def _cmd_lineage(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    direction = args.direction
    if direction == "upstream":
        direction = "inbound"
    elif direction == "downstream":
        direction = "outbound"
    traversal = ctx.traverse_lineage(args.subject_ref, direction=direction, max_depth=args.depth)
    lines = [f"Lineage: {args.subject_ref}", f"Edges: {len(traversal.edges)}", f"Visited: {len(traversal.visited_refs)}"]
    return _emit(args, payload=traversal, text="\n".join(lines))


def _cmd_search_runs(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    runs = ctx.list_runs(args.project, status=args.status, limit=args.limit)
    needle = args.text.lower()
    matches = tuple(
        run
        for run in runs
        if needle in run.run_id.lower() or needle in run.name.lower() or needle in run.project_name.lower()
    )[: args.limit]
    text = "\n".join(["Run search"] + [f"{run.run_id}  {run.status}  {run.name}" for run in matches] or ["(empty)"])
    return _emit(args, payload={"runs": matches}, text=text)


def _cmd_search_artifacts(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    needle = args.text.lower()
    matches = []
    for artifact in ctx.repository.list_artifacts():
        if args.kind is not None and artifact.kind != args.kind:
            continue
        if needle in artifact.artifact_ref.lower() or needle in artifact.kind.lower() or needle in (artifact.location or "").lower():
            matches.append(artifact)
        if len(matches) >= args.limit:
            break
    text = "\n".join(["Artifact search"] + [f"{artifact.artifact_ref}  {artifact.kind}  {artifact.run_id}" for artifact in matches] or ["(empty)"])
    return _emit(args, payload={"artifacts": tuple(matches)}, text=text)


def _cmd_trend(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    query = _run_query_from_args(args)
    trend = ctx.get_metric_trend(args.metric_key, project_name=args.project, stage_name=args.stage, query=query)
    lines = [f"Trend: {trend.metric_key}", f"Points: {len(trend.points)}"]
    for point in trend.points:
        lines.append(f"{point.run_id}  {point.stage_name or '-'}  {point.value}  {point.captured_at or '-'}")
    return _emit(args, payload=trend, text="\n".join(lines))


def _cmd_aggregate(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    service = AggregationService(ctx.query_service, metric_aggregation=ctx.config.interpretation.trend.metric_aggregation)
    aggregate = service.aggregate_metric(
        args.metric_key,
        query=_run_query_from_args(args),
        project_name=args.project,
        stage_name=args.stage,
    )
    text = "\n".join(
        (
            f"Aggregate: {aggregate.metric_key}",
            f"Count: {aggregate.count}",
            f"Mean: {aggregate.mean}",
            f"Std: {aggregate.std}",
            f"Min: {aggregate.min}",
            f"Max: {aggregate.max}",
        )
    )
    return _emit(args, payload=aggregate, text=text)


def _cmd_anomaly(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    service = AnomalyService(
        ctx.query_service,
        z_score_threshold=ctx.config.interpretation.anomaly.z_score_threshold,
        min_baseline_runs=ctx.config.interpretation.anomaly.min_baseline_runs,
        monitored_metrics=ctx.config.interpretation.anomaly.monitored_metrics,
        metric_aggregation=ctx.config.interpretation.trend.metric_aggregation,
    )
    baseline_query = None if args.project is None else RunListQuery(project_name=args.project)
    metric_keys = tuple(args.metrics) or None
    results = service.detect_anomalies_in_run(
        args.run_id,
        baseline_query=baseline_query,
        metric_keys=metric_keys,
        stage_name=args.stage,
    )
    lines = [f"Anomalies: {args.run_id}", f"Count: {len(results)}"]
    for result in results:
        lines.append(f"{result.metric_key}  actual={result.actual_value}  z={result.z_score}  severity={result.severity}")
    return _emit(args, payload={"anomalies": results}, text="\n".join(lines))


def _cmd_alert(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    rule = AlertRule(
        metric_key=args.metric,
        operator=args.operator,
        threshold=args.threshold,
        stage_name=args.stage,
        severity=args.severity,
    )
    results = ctx.evaluate_alerts(args.run_id, [rule])
    lines = [f"Alerts: {args.run_id}"]
    for result in results:
        lines.append(f"{result.metric_key}  actual={result.actual_value}  threshold={result.threshold}  triggered={result.triggered}")
    return _emit(args, payload={"results": results}, text="\n".join(lines))


def _cmd_report_snapshot(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    report = ctx.build_snapshot_report(args.run_id)
    rendered = _render_report(report, args.render)
    payload = report.to_json() if args.render == "json" else {"title": report.title, "render": args.render}
    return _emit(args, payload=payload, text=rendered, output=args.output)


def _cmd_report_compare(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    report = ctx.build_run_report(args.left_run_id, args.right_run_id)
    rendered = _render_report(report, args.render)
    payload = report.to_json() if args.render == "json" else {"title": report.title, "render": args.render}
    return _emit(args, payload=payload, text=rendered, output=args.output)


def _cmd_export_html(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    if args.run:
        report = ctx.build_snapshot_report(args.run)
    elif args.left and args.right:
        report = ctx.build_run_report(args.left, args.right)
    else:
        raise ValueError("export html requires --run or --left/--right.")
    html = report.to_html()
    return _emit(args, payload={"title": report.title, "render": "html"}, text=html, output=args.output)


def _cmd_export_csv_runs(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    text = export_run_list_csv(ctx, project_name=args.project, query=_run_query_from_args(args))
    return _emit(args, payload={"render": "csv", "kind": "runs"}, text=text.rstrip("\n"), output=args.output)


def _cmd_export_csv_compare(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    text = export_comparison_csv(ctx, args.left_run_id, args.right_run_id)
    return _emit(args, payload={"render": "csv", "kind": "compare"}, text=text.rstrip("\n"), output=args.output)


def _cmd_export_csv_trend(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    text = export_trend_csv(
        ctx,
        args.metric_key,
        project_name=args.project,
        stage_name=args.stage,
        query=_run_query_from_args(args),
    )
    return _emit(args, payload={"render": "csv", "kind": "trend"}, text=text.rstrip("\n"), output=args.output)


def _cmd_export_csv_anomaly(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    baseline_query = None if args.project is None else RunListQuery(project_name=args.project)
    text = export_anomaly_csv(
        ctx,
        args.run_id,
        baseline_query=baseline_query,
        metric_keys=tuple(args.metrics) or None,
        stage_name=args.stage,
    )
    return _emit(args, payload={"render": "csv", "kind": "anomaly"}, text=text.rstrip("\n"), output=args.output)


def _cmd_serve_http(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    server = make_server(ctx, host=args.host, port=args.port)
    host, port = server.server_address
    startup_payload = {"host": host, "port": port, "workspace": ctx.workspace}
    if not args.quiet:
        if args.format == "json":
            print(json_dumps(startup_payload, indent=2, sort_keys=True))
        else:
            print(f"Serving HTTP on http://{host}:{port} (workspace={ctx.workspace})")
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


def _cmd_provenance_audit(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    audit = ctx.audit_reproducibility(args.run_id)
    text = "\n".join(
        (
            f"Provenance audit: {audit.run_id}",
            f"Status: {audit.reproducibility_status}",
            f"Environment ref: {audit.environment_ref or '-'}",
            f"Package count: {audit.package_count}",
        )
    )
    return _emit(args, payload=audit, text=text)


def _cmd_provenance_diff(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    diff = ctx.compare_environments(args.left_run_id, args.right_run_id)
    text = "\n".join(
        (
            f"Environment diff: {diff.left_run_id} vs {diff.right_run_id}",
            f"Python changed: {diff.python_version_changed}",
            f"Platform changed: {diff.platform_changed}",
            f"Package changes: {len(diff.added_packages) + len(diff.removed_packages) + len(diff.changed_packages)}",
            f"Variable changes: {len(diff.added_variables) + len(diff.removed_variables) + len(diff.changed_variables)}",
        )
    )
    return _emit(args, payload=diff, text=text)


def _cmd_artifact_register(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    source_path = resolve_path(args.source_path)
    artifact_ref = args.artifact_ref or _default_artifact_ref(args.run_ref, args.source_path)
    manifest = ArtifactManifest(
        artifact_ref=artifact_ref,
        artifact_kind=args.artifact_kind,
        created_at=_utc_now_text(),
        producer_ref="cli.artifact-register",
        run_ref=args.run_ref,
        stage_execution_ref=args.stage_ref,
        location_ref=source_path.name,
    )
    receipt = ctx.artifact_store.put_artifact(manifest, source_path, mode=args.mode)
    text = "\n".join(
        (
            f"Artifact registered: {receipt.binding.artifact_ref}",
            f"Path: {receipt.path}",
            f"Bytes written: {receipt.bytes_written}",
        )
    )
    return _emit(args, payload=receipt, text=text)


def _cmd_backup_create(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    backup_root = ensure_directory(ctx.config.recovery.backup_root)
    label = args.label or Path(ctx.workspace).name
    archive_stem = resolve_path(args.output) if args.output else backup_root / f"{label}-{_safe_timestamp()}"
    archive_root = str(archive_stem.with_suffix(""))
    archive_path = shutil.make_archive(
        archive_root,
        "zip",
        root_dir=Path(ctx.workspace).parent,
        base_dir=Path(ctx.workspace).name,
    )
    payload = {"backup_path": archive_path, "workspace": ctx.workspace, "label": label}
    text = f"Backup created: {archive_path}"
    return _emit(args, payload=payload, text=text)


def _cmd_restore_apply(args: argparse.Namespace) -> int:
    backup_path = resolve_path(args.backup_ref)
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup does not exist: {backup_path}")
    target_workspace = resolve_path(args.target_workspace or ".contexta")
    if args.verify_only:
        payload = {"backup_path": str(backup_path), "target_workspace": str(target_workspace), "verified": True}
        return _emit(args, payload=payload, text=f"Verified backup: {backup_path}")
    if target_workspace.exists():
        shutil.rmtree(target_workspace)
    ensure_directory(target_workspace.parent)
    shutil.unpack_archive(str(backup_path), str(target_workspace.parent), format="zip")
    payload = {"backup_path": str(backup_path), "target_workspace": str(target_workspace), "restored": True}
    return _emit(args, payload=payload, text=f"Restored backup to {target_workspace}")


def _cmd_recover_replay(args: argparse.Namespace) -> int:
    ctx = _resolve_context(args)
    result = ctx.record_store.replay(
        ScanFilter(
            run_ref=args.run,
            stage_execution_ref=args.stage,
            record_type=args.record_type,
        ),
        mode=ReplayMode(args.mode),
    )
    text = "\n".join(
        (
            f"Replay mode: {result.mode.value}",
            f"Records: {result.record_count}",
            f"Warnings: {len(result.warnings)}",
            f"Known gaps: {len(result.known_gaps)}",
            f"Integrity: {result.integrity_state.value}",
        )
    )
    return _emit(args, payload=result, text=text)


__all__ = ["build_parser", "main", "run_cli"]
