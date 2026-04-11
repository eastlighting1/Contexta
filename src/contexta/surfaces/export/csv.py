"""CSV export helpers for Contexta analysis surfaces."""

from __future__ import annotations

import csv
from io import StringIO

from ...api import Contexta
from ...interpretation import AnomalyService, RunListQuery


def export_run_list_csv(
    ctx: Contexta,
    *,
    project_name: str | None = None,
    query: RunListQuery | None = None,
) -> str:
    runs = ctx.list_runs(project_name, query=query)
    return _write_csv(
        ("run_id", "name", "project_name", "status", "started_at", "ended_at"),
        (
            (
                run.run_id,
                run.name,
                run.project_name,
                run.status,
                run.started_at or "",
                run.ended_at or "",
            )
            for run in runs
        ),
    )


def export_comparison_csv(ctx: Contexta, left_run_id: str, right_run_id: str) -> str:
    comparison = ctx.compare_runs(left_run_id, right_run_id)
    return _write_csv(
        (
            "stage_name",
            "metric_key",
            "left_value",
            "right_value",
            "delta",
            "change_ratio",
            "left_status",
            "right_status",
            "notes",
        ),
        (
            (
                stage.stage_name,
                delta.metric_key,
                "" if delta.left_value is None else str(delta.left_value),
                "" if delta.right_value is None else str(delta.right_value),
                "" if delta.delta is None else str(delta.delta),
                "" if delta.change_ratio is None else str(delta.change_ratio),
                stage.left_status or "",
                stage.right_status or "",
                "; ".join(note.summary for note in delta.completeness_notes + stage.completeness_notes),
            )
            for stage in comparison.stage_comparisons
            for delta in stage.metric_deltas
        ),
    )


def export_trend_csv(
    ctx: Contexta,
    metric_key: str,
    *,
    project_name: str | None = None,
    stage_name: str | None = None,
    query: RunListQuery | None = None,
) -> str:
    trend = ctx.get_metric_trend(metric_key, project_name=project_name, stage_name=stage_name, query=query)
    return _write_csv(
        ("run_id", "run_name", "metric_key", "project_name", "stage_name", "value", "captured_at"),
        (
            (
                point.run_id,
                point.run_name,
                trend.metric_key,
                trend.project_name or project_name or "",
                point.stage_name or stage_name or "",
                str(point.value),
                point.captured_at or "",
            )
            for point in trend.points
        ),
    )


def export_anomaly_csv(
    ctx: Contexta,
    run_id: str,
    *,
    baseline_query: RunListQuery | None = None,
    metric_keys: tuple[str, ...] | None = None,
    stage_name: str | None = None,
) -> str:
    anomaly_service = AnomalyService(
        ctx.query_service,
        z_score_threshold=ctx.config.interpretation.anomaly.z_score_threshold,
        min_baseline_runs=ctx.config.interpretation.anomaly.min_baseline_runs,
        metric_aggregation=ctx.config.interpretation.trend.metric_aggregation,
        monitored_metrics=ctx.config.interpretation.anomaly.monitored_metrics,
    )
    results = anomaly_service.detect_anomalies_in_run(
        run_id,
        baseline_query=baseline_query,
        metric_keys=metric_keys,
        stage_name=stage_name,
    )
    return _write_csv(
        (
            "run_id",
            "metric_key",
            "actual_value",
            "expected_low",
            "expected_high",
            "z_score",
            "severity",
            "notes",
        ),
        (
            (
                result.run_id,
                result.metric_key,
                str(result.actual_value),
                str(result.expected_range[0]),
                str(result.expected_range[1]),
                str(result.z_score),
                result.severity,
                "; ".join(note.summary for note in result.completeness_notes),
            )
            for result in results
        ),
    )


def _write_csv(headers: tuple[str, ...], rows) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


__all__ = [
    "export_anomaly_csv",
    "export_comparison_csv",
    "export_run_list_csv",
    "export_trend_csv",
]
