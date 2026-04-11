"""Notebook rendering helpers for Contexta."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any, Sequence

from ...api import Contexta
from ...common.errors import DependencyError, RenderingError
from ...interpretation import MetricTrend, MultiRunComparison, ReportDocument, RunComparison, RunSnapshot
from ..html import render_html_comparison, render_html_run_detail, render_html_trend


@dataclass(frozen=True, slots=True)
class NotebookFragment:
    """Notebook-friendly rich fragment with HTML and plain-text fallbacks."""

    html: str
    text: str

    def _repr_html_(self) -> str:
        return self.html

    def __str__(self) -> str:
        return self.text


def _maybe_display(fragment: NotebookFragment) -> None:
    try:
        from IPython.display import HTML, display  # type: ignore
    except ImportError:
        return
    display(HTML(fragment.html))


def _render_snapshot_fragment(snapshot: RunSnapshot) -> NotebookFragment:
    notes = "".join(f"<li>{escape(note)}</li>" for note in snapshot.completeness_notes)
    artifacts = "".join(
        "<tr>"
        f"<td>{escape(item.artifact_ref)}</td>"
        f"<td>{escape(item.kind)}</td>"
        f"<td>{escape(item.stage_id or '')}</td>"
        "</tr>"
        for item in snapshot.artifacts[:10]
    )
    html = (
        "<article>"
        f"<h1>{escape(snapshot.run.name)}</h1>"
        f"<p><strong>Run ID:</strong> {escape(snapshot.run.run_id)}</p>"
        f"<p><strong>Project:</strong> {escape(snapshot.run.project_name)}</p>"
        f"<p><strong>Status:</strong> {escape(snapshot.run.status)}</p>"
        "<section><h2>Summary</h2>"
        f"<p>Stages={len(snapshot.stages)} Artifacts={len(snapshot.artifacts)} Records={len(snapshot.records)}</p>"
        "</section>"
        "<section><h2>Artifacts</h2>"
        "<table><thead><tr><th>Ref</th><th>Kind</th><th>Stage</th></tr></thead>"
        f"<tbody>{artifacts}</tbody></table>"
        "</section>"
        "<section><h2>Completeness Notes</h2>"
        f"<ul>{notes}</ul>"
        "</section>"
        "</article>"
    )
    text = (
        f"Run {snapshot.run.run_id} ({snapshot.run.status}) "
        f"stages={len(snapshot.stages)} artifacts={len(snapshot.artifacts)} records={len(snapshot.records)}"
    )
    return NotebookFragment(html=html, text=text)


def _render_run_comparison_fragment(comparison: RunComparison) -> NotebookFragment:
    stage_rows = "".join(
        "<tr>"
        f"<td>{escape(stage.stage_name)}</td>"
        f"<td>{escape(stage.left_status or '')}</td>"
        f"<td>{escape(stage.right_status or '')}</td>"
        f"<td>{escape(str(len(stage.metric_deltas)))}</td>"
        "</tr>"
        for stage in comparison.stage_comparisons
    )
    html = (
        "<article>"
        f"<h1>Run Comparison</h1>"
        f"<p><strong>Left:</strong> {escape(comparison.left_run_id)}</p>"
        f"<p><strong>Right:</strong> {escape(comparison.right_run_id)}</p>"
        f"<p>{escape(comparison.summary)}</p>"
        "<table><thead><tr><th>Stage</th><th>Left</th><th>Right</th><th>Metric Deltas</th></tr></thead>"
        f"<tbody>{stage_rows}</tbody></table>"
        "</article>"
    )
    text = (
        f"Compare {comparison.left_run_id} vs {comparison.right_run_id}: "
        f"{comparison.summary} stages={len(comparison.stage_comparisons)}"
    )
    return NotebookFragment(html=html, text=text)


def _render_multi_run_comparison_fragment(comparison: MultiRunComparison) -> NotebookFragment:
    metric_rows = "".join(
        "<tr>"
        f"<td>{escape(row.metric_key)}</td>"
        f"<td>{escape(row.stage_name or '')}</td>"
        f"<td>{escape(', '.join('' if value is None else str(value) for value in row.values))}</td>"
        f"<td>{escape(row.best_run_id or '')}</td>"
        "</tr>"
        for row in comparison.metric_table[:20]
    )
    html = (
        "<article>"
        "<h1>Multi-Run Comparison</h1>"
        f"<p><strong>Runs:</strong> {escape(', '.join(comparison.run_ids))}</p>"
        f"<p>{escape(comparison.summary)}</p>"
        "<table><thead><tr><th>Metric</th><th>Stage</th><th>Values</th><th>Best Run</th></tr></thead>"
        f"<tbody>{metric_rows}</tbody></table>"
        "</article>"
    )
    text = f"Multi-run comparison runs={len(comparison.run_ids)} metrics={len(comparison.metric_table)}"
    return NotebookFragment(html=html, text=text)


def _render_metric_trend_fragment(trend: MetricTrend) -> NotebookFragment:
    rows = "".join(
        "<tr>"
        f"<td>{escape(point.run_id)}</td>"
        f"<td>{escape(point.run_name)}</td>"
        f"<td>{escape(point.stage_name or '')}</td>"
        f"<td>{escape(str(point.value))}</td>"
        f"<td>{escape(point.captured_at or '')}</td>"
        "</tr>"
        for point in trend.points
    )
    html = (
        "<article>"
        f"<h1>Metric Trend: {escape(trend.metric_key)}</h1>"
        f"<p><strong>Project:</strong> {escape(trend.project_name or '')}</p>"
        f"<p><strong>Points:</strong> {len(trend.points)}</p>"
        "<table><thead><tr><th>Run ID</th><th>Run Name</th><th>Stage</th><th>Value</th><th>Recorded At</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        "</article>"
    )
    text = f"Metric trend {trend.metric_key} points={len(trend.points)}"
    return NotebookFragment(html=html, text=text)


def _render_report_fragment(report: ReportDocument) -> NotebookFragment:
    return NotebookFragment(html=report.to_html(), text=report.to_markdown())


def render_html_fragment(value: object) -> str:
    """Render an embeddable HTML fragment for notebook display."""
    if isinstance(value, ReportDocument):
        return value.to_html()
    if isinstance(value, RunSnapshot):
        return _render_snapshot_fragment(value).html
    if isinstance(value, RunComparison):
        return _render_run_comparison_fragment(value).html
    if isinstance(value, MultiRunComparison):
        return _render_multi_run_comparison_fragment(value).html
    if isinstance(value, MetricTrend):
        return _render_metric_trend_fragment(value).html
    raise RenderingError(
        "Unsupported notebook render target.",
        code="notebook_render_target_unsupported",
        details={"type": type(value).__name__},
    )


def display_run_snapshot(
    value: Contexta | RunSnapshot,
    run_id: str | None = None,
    *,
    display: bool = False,
) -> NotebookFragment:
    """Return a notebook-friendly fragment for a run snapshot."""
    if isinstance(value, Contexta):
        if run_id is None:
            raise RenderingError(
                "run_id is required when rendering a snapshot from Contexta.",
                code="notebook_snapshot_run_id_required",
            )
        fragment = NotebookFragment(
            html=render_html_run_detail(value, run_id),
            text=f"Run snapshot for {run_id}",
        )
    elif isinstance(value, RunSnapshot):
        fragment = _render_snapshot_fragment(value)
    else:
        raise RenderingError(
            "Unsupported run snapshot input.",
            code="notebook_snapshot_input_unsupported",
            details={"type": type(value).__name__},
        )
    if display:
        _maybe_display(fragment)
    return fragment


def display_run_comparison(
    value: Contexta | RunComparison | MultiRunComparison,
    left_run_id: str | None = None,
    right_run_id: str | None = None,
    *,
    display: bool = False,
) -> NotebookFragment:
    """Return a notebook-friendly fragment for a run comparison."""
    if isinstance(value, Contexta):
        if left_run_id is None or right_run_id is None:
            raise RenderingError(
                "left_run_id and right_run_id are required when rendering a comparison from Contexta.",
                code="notebook_comparison_run_ids_required",
            )
        fragment = NotebookFragment(
            html=render_html_comparison(value, left_run_id, right_run_id),
            text=f"Run comparison for {left_run_id} vs {right_run_id}",
        )
    elif isinstance(value, RunComparison):
        fragment = _render_run_comparison_fragment(value)
    elif isinstance(value, MultiRunComparison):
        fragment = _render_multi_run_comparison_fragment(value)
    else:
        raise RenderingError(
            "Unsupported run comparison input.",
            code="notebook_comparison_input_unsupported",
            details={"type": type(value).__name__},
        )
    if display:
        _maybe_display(fragment)
    return fragment


def display_metric_trend(
    value: Contexta | MetricTrend,
    metric_key: str | None = None,
    *,
    project_name: str | None = None,
    stage_name: str | None = None,
    query: Any | None = None,
    display: bool = False,
) -> NotebookFragment:
    """Return a notebook-friendly fragment for a metric trend."""
    if isinstance(value, Contexta):
        if metric_key is None:
            raise RenderingError(
                "metric_key is required when rendering a trend from Contexta.",
                code="notebook_trend_metric_key_required",
            )
        fragment = NotebookFragment(
            html=render_html_trend(
                value,
                metric_key,
                project_name=project_name,
                stage_name=stage_name,
                query=query,
            ),
            text=f"Metric trend for {metric_key}",
        )
    elif isinstance(value, MetricTrend):
        fragment = _render_metric_trend_fragment(value)
    else:
        raise RenderingError(
            "Unsupported metric trend input.",
            code="notebook_trend_input_unsupported",
            details={"type": type(value).__name__},
        )
    if display:
        _maybe_display(fragment)
    return fragment


def _table_rows(value: object) -> list[dict[str, object]]:
    if isinstance(value, RunSnapshot):
        return [
            {
                "run_id": value.run.run_id,
                "run_name": value.run.name,
                "project_name": value.run.project_name,
                "status": value.run.status,
                "stage_count": len(value.stages),
                "artifact_count": len(value.artifacts),
                "record_count": len(value.records),
            }
        ]
    if isinstance(value, RunComparison):
        return [
            {
                "stage_name": stage.stage_name,
                "left_status": stage.left_status,
                "right_status": stage.right_status,
                "metric_delta_count": len(stage.metric_deltas),
            }
            for stage in value.stage_comparisons
        ]
    if isinstance(value, MultiRunComparison):
        return [
            {
                "metric_key": row.metric_key,
                "stage_name": row.stage_name,
                "best_run_id": row.best_run_id,
                **{f"value_{index}": item for index, item in enumerate(row.values)},
            }
            for row in value.metric_table
        ]
    if isinstance(value, MetricTrend):
        return [
            {
                "run_id": point.run_id,
                "run_name": point.run_name,
                "stage_name": point.stage_name,
                "value": point.value,
                "captured_at": point.captured_at,
            }
            for point in value.points
        ]
    if isinstance(value, ReportDocument):
        return [
            {
                "section_title": section.title,
                "body": section.body,
                "evidence_link_count": len(section.evidence_links),
            }
            for section in value.sections
        ]
    raise RenderingError(
        "Unsupported notebook table conversion target.",
        code="notebook_table_conversion_unsupported",
        details={"type": type(value).__name__},
    )


def _columns(rows: Sequence[dict[str, object]]) -> list[str]:
    ordered: list[str] = []
    for row in rows:
        for key in row:
            if key not in ordered:
                ordered.append(key)
    return ordered


def to_pandas(value: object) -> Any:
    """Convert a supported notebook-facing object to a pandas DataFrame."""
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise DependencyError(
            "pandas is required for notebook dataframe conversion.",
            code="notebook_pandas_not_ready",
            cause=exc,
        ) from exc
    rows = _table_rows(value)
    return pd.DataFrame.from_records(rows, columns=_columns(rows))


def to_polars(value: object) -> Any:
    """Convert a supported notebook-facing object to a polars DataFrame."""
    try:
        import polars as pl  # type: ignore
    except ImportError as exc:
        raise DependencyError(
            "polars is required for notebook dataframe conversion.",
            code="notebook_polars_not_ready",
            cause=exc,
        ) from exc
    rows = _table_rows(value)
    columns = _columns(rows)
    return pl.DataFrame(rows, schema=columns, orient="row")


__all__ = [
    "NotebookFragment",
    "display_metric_trend",
    "display_run_comparison",
    "display_run_snapshot",
    "render_html_fragment",
    "to_pandas",
    "to_polars",
]
