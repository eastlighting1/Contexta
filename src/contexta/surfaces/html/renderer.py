"""Server-rendered HTML helpers for embedded Contexta views."""

from __future__ import annotations

from html import escape

from ...api import Contexta
from ...interpretation import AggregationService, RunListQuery
from .charts import DashboardConfig, render_line_chart, render_status_bar
from .templates import action_bar, note_block, page_header, page_shell, raw_section, stat_grid, table_card


def render_html_run_list(ctx: Contexta, *, project_name: str | None = None, query: RunListQuery | None = None) -> str:
    runs = tuple(ctx.list_runs(project_name, query=query))
    summary = stat_grid(
        (
            ("Project", project_name or "All projects"),
            ("Run Count", str(len(runs))),
            ("Status Filter", "any" if query is None or query.status is None else query.status),
        ),
        section_id="run-list-summary",
        title="Summary",
    )
    filters = note_block(
        section_id="run-list-filters",
        title="Filters",
        notes=tuple(
            value
            for value in (
                None if project_name is None else f"project={project_name}",
                None if query is None or query.status is None else f"status={query.status}",
                None if query is None or query.limit is None else f"limit={query.limit}",
            )
            if value is not None
        ),
        empty_text="No active filters.",
    )
    rows = tuple(
        (
            f'<a href="/ui/runs/{escape(run.run_id, quote=True)}">{escape(run.run_id)}</a>',
            escape(run.name),
            escape(run.project_name),
            escape(run.status),
            escape(run.started_at or ""),
        )
        for run in runs
    )
    table = table_card(
        section_id="runs-table",
        title="Runs",
        headers=("Run ID", "Name", "Project", "Status", "Started"),
        rows=rows,
        empty_text="No runs found.",
    )
    body = (
        page_header("Runs", "Project and run inventory")
        + action_bar((("Open Trend", "/ui/metrics/trend"),))
        + filters
        + summary
        + table
    )
    return page_shell(title="Runs", body=body)


def render_html_run_detail(ctx: Contexta, run_id: str) -> str:
    snapshot = ctx.get_run_snapshot(run_id)
    summary = stat_grid(
        (
            ("Run", snapshot.run.name),
            ("Run ID", snapshot.run.run_id),
            ("Project", snapshot.run.project_name),
            ("Status", snapshot.run.status),
            ("Stages", str(len(snapshot.stages))),
            ("Artifacts", str(len(snapshot.artifacts))),
            ("Records", str(len(snapshot.records))),
        ),
        section_id="run-summary",
        title="Run Summary",
    )
    actions = raw_section(
        section_id="run-actions",
        title="Actions",
        body=action_bar(
            (
                ("Diagnostics", f"/ui/runs/{escape(snapshot.run.run_id, quote=True)}/diagnostics"),
                ("Compare", f"/ui/compare?left={escape(snapshot.run.run_id, quote=True)}"),
                ("Trend", f"/ui/metrics/trend?metric=loss&project={escape(snapshot.run.project_name, quote=True)}"),
            )
        ),
    )
    stage_rows = tuple(
        (
            escape(stage.name),
            escape(stage.status),
            escape(stage.started_at or ""),
            escape(stage.ended_at or ""),
            escape(f"stage_id={stage.stage_id}"),
        )
        for stage in snapshot.stages
    )
    artifact_rows = tuple(
        (
            escape(artifact.artifact_ref),
            escape(artifact.kind),
            escape(artifact.stage_id or ""),
            escape(artifact.location or ""),
            escape(artifact.hash_value or ""),
        )
        for artifact in snapshot.artifacts
    )
    recent_records = tuple(snapshot.records[-10:])
    record_preview = table_card(
        section_id="record-preview",
        title="Record Preview",
        headers=("Type", "Key", "Value", "Observed At"),
        rows=tuple(
            (
                escape(record.record_type),
                escape(record.key),
                escape("" if record.value is None else str(record.value)),
                escape(record.observed_at),
            )
            for record in recent_records
        ),
        empty_text="No records available.",
    )
    provenance_lines = ()
    if snapshot.provenance is not None:
        provenance_lines = (
            f"provenance_ref={snapshot.provenance.provenance_ref}",
            f"relation_ref={snapshot.provenance.relation_ref}",
            f"assertion_mode={snapshot.provenance.assertion_mode}",
        )
    provenance_section = note_block(
        section_id="provenance-summary",
        title="Provenance",
        notes=provenance_lines,
        empty_text="No provenance summary.",
    )
    notes_section = note_block(
        section_id="completeness-notes",
        title="Completeness Notes",
        notes=tuple(snapshot.completeness_notes),
    )
    body = (
        page_header(f"Run: {snapshot.run.name}", snapshot.run.run_id)
        + summary
        + actions
        + table_card(
            section_id="stage-table",
            title="Stages",
            headers=("Stage", "Status", "Started", "Ended", "Summary"),
            rows=stage_rows,
            empty_text="No stages.",
        )
        + table_card(
            section_id="artifact-table",
            title="Artifacts",
            headers=("Artifact Ref", "Kind", "Stage", "Location", "Hash"),
            rows=artifact_rows,
            empty_text="No artifacts.",
        )
        + record_preview
        + provenance_section
        + notes_section
    )
    return page_shell(title=f"Run: {snapshot.run.name}", body=body)


def render_html_comparison(ctx: Contexta, left_run_id: str, right_run_id: str) -> str:
    comparison = ctx.compare_runs(left_run_id, right_run_id)
    header = raw_section(
        section_id="comparison-run-header",
        title="Run Header",
        body=(
            f"<p><strong>Left:</strong> {escape(comparison.left_run_id)}</p>"
            f"<p><strong>Right:</strong> {escape(comparison.right_run_id)}</p>"
        ),
    )
    summary = stat_grid(
        (
            ("Changed Stages", str(len(comparison.stage_comparisons))),
            ("Artifact Changes", str(len(comparison.artifact_changes))),
            ("Summary", comparison.summary),
        ),
        section_id="comparison-summary",
        title="Summary",
    )
    stage_rows = tuple(
        (
            escape(stage.stage_name),
            escape(stage.left_status or ""),
            escape(stage.right_status or ""),
            escape(
                ", ".join(
                    f"{delta.metric_key}:{delta.delta}"
                    for delta in stage.metric_deltas[:2]
                )
            ),
            escape(", ".join(note.summary for note in stage.completeness_notes)),
        )
        for stage in comparison.stage_comparisons
    )
    artifact_rows = tuple(
        (
            escape(change.artifact_kind),
            escape(change.left_ref or ""),
            escape(change.right_ref or ""),
            escape(change.change),
            escape(change.change_detail or ""),
        )
        for change in comparison.artifact_changes
    )
    provenance_notes = ()
    if comparison.provenance_comparison is not None:
        provenance_notes = (
            f"code_revision_changed={comparison.provenance_comparison.code_revision_changed}",
            f"config_hash_changed={comparison.provenance_comparison.config_hash_changed}",
            f"environment_changed={comparison.provenance_comparison.environment_changed}",
            f"dataset_refs_changed={comparison.provenance_comparison.dataset_refs_changed}",
        )
    body = (
        page_header(f"Compare: {left_run_id} vs {right_run_id}")
        + action_bar(
            (
                ("Left Run", f"/ui/runs/{escape(left_run_id, quote=True)}"),
                ("Right Run", f"/ui/runs/{escape(right_run_id, quote=True)}"),
            )
        )
        + header
        + summary
        + table_card(
            section_id="comparison-stage-table",
            title="Stage Comparison",
            headers=("Stage", "Left Status", "Right Status", "Key Metric Delta", "Notes"),
            rows=stage_rows,
            empty_text="No stage rows.",
        )
        + table_card(
            section_id="comparison-artifact-table",
            title="Artifact Changes",
            headers=("Artifact Kind", "Left Ref", "Right Ref", "Change", "Change Detail"),
            rows=artifact_rows,
            empty_text="No artifact changes.",
        )
        + note_block(
            section_id="comparison-provenance",
            title="Provenance",
            notes=provenance_notes,
            empty_text="No provenance comparison.",
        )
        + note_block(
            section_id="comparison-notes",
            title="Completeness Notes",
            notes=tuple(note.summary for note in comparison.completeness_notes),
        )
    )
    return page_shell(title=f"Compare: {left_run_id} vs {right_run_id}", body=body)


def render_html_trend(
    ctx: Contexta,
    metric_key: str,
    *,
    project_name: str | None = None,
    stage_name: str | None = None,
    query: RunListQuery | None = None,
) -> str:
    trend = ctx.get_metric_trend(metric_key, project_name=project_name, stage_name=stage_name, query=query)
    summary = stat_grid(
        (
            ("Metric", trend.metric_key),
            ("Project", trend.project_name or project_name or "n/a"),
            ("Stage", stage_name or "run"),
            ("Sample Count", str(len(trend.points))),
        ),
        section_id="trend-summary",
        title="Summary",
    )
    chart = raw_section(
        section_id="trend-chart",
        title="Chart",
        body=render_line_chart(trend),
    )
    rows = tuple(
        (
            f'<a href="/ui/runs/{escape(point.run_id, quote=True)}">{escape(point.run_id)}</a>',
            escape(point.run_name),
            escape(trend.project_name or project_name or ""),
            escape(point.stage_name or stage_name or ""),
            escape(str(point.value)),
            escape(point.captured_at or ""),
        )
        for point in trend.points
    )
    body = (
        page_header(f"Trend: {metric_key}", f"Project={project_name or 'all'} Stage={stage_name or 'run'}")
        + action_bar((("Runs", "/ui/runs"),))
        + summary
        + chart
        + table_card(
            section_id="trend-run-table",
            title="Runs",
            headers=("Run ID", "Run Name", "Project", "Stage", "Value", "Recorded At"),
            rows=rows,
            empty_text="No trend points.",
        )
        + note_block(
            section_id="trend-notes",
            title="Completeness Notes",
            notes=tuple(note.summary for note in trend.completeness_notes),
        )
    )
    return page_shell(title=f"Trend: {metric_key}", body=body)


def render_html_dashboard(ctx: Contexta, config: DashboardConfig | None = None) -> str:
    dashboard = DashboardConfig() if config is None else config
    aggregation_service = AggregationService(ctx.query_service, metric_aggregation=ctx.config.interpretation.trend.metric_aggregation)
    status_distribution = aggregation_service.run_status_distribution(project_name=dashboard.project_name)
    stage_summary = aggregation_service.aggregate_by_stage(project_name=dashboard.project_name)
    trend = ctx.get_metric_trend(
        dashboard.metric_key,
        project_name=dashboard.project_name,
        stage_name=dashboard.stage_name,
    )
    body = (
        page_header("Dashboard", "Overview of run status, stage summary, and representative metric trend")
        + stat_grid(
            (
                ("Project", dashboard.project_name or "All projects"),
                ("Total Runs", str(status_distribution.total)),
                ("Pass Rate", f"{status_distribution.pass_rate:.0%}"),
                ("Metric", dashboard.metric_key),
            ),
            title="Overview",
        )
        + raw_section(
            section_id="dashboard-status",
            title="Run Status",
            body=render_status_bar(status_distribution),
        )
        + table_card(
            section_id="dashboard-stage-summary",
            title="Stage Summary",
            headers=("Stage", "Metric", "Count", "Mean", "Min", "Max"),
            rows=tuple(
                (
                    escape(row.stage_name),
                    escape(row.metric_key),
                    escape(str(row.count)),
                    escape(f"{row.mean:.4f}"),
                    escape(f"{row.min:.4f}"),
                    escape(f"{row.max:.4f}"),
                )
                for row in stage_summary.by_stage
            ),
            empty_text="No stage aggregates.",
        )
        + raw_section(
            section_id="dashboard-trend",
            title="Representative Trend",
            body=render_line_chart(trend),
        )
    )
    return page_shell(title="Dashboard", body=body)


__all__ = [
    "DashboardConfig",
    "render_html_comparison",
    "render_html_dashboard",
    "render_html_run_detail",
    "render_html_run_list",
    "render_html_trend",
]
