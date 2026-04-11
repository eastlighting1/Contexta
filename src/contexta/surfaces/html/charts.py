"""Small server-rendered chart helpers for HTML views."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from ...interpretation import MetricTrend, RunStatusDistribution


@dataclass(frozen=True, slots=True)
class DashboardConfig:
    project_name: str | None = None
    metric_key: str = "loss"
    stage_name: str | None = None


def render_line_chart(trend: MetricTrend, *, width: int = 820, height: int = 260) -> str:
    if not trend.points:
        return '<p class="empty">No trend data available.</p>'
    values = [point.value for point in trend.points]
    lo = min(values)
    hi = max(values)
    span = 1.0 if hi == lo else hi - lo
    inner_width = width - 80
    inner_height = height - 70
    step = inner_width / max(len(values) - 1, 1)
    points = []
    for index, point in enumerate(trend.points):
        x = 40 + index * step
        y = 20 + (hi - point.value) / span * inner_height
        points.append((x, y, point))
    polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y, _ in points)
    circles = "".join(
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#0b6e4f"><title>{escape(point.run_name)}: {point.value}</title></circle>'
        for x, y, point in points
    )
    labels = "".join(
        f'<text x="{x:.2f}" y="{height - 14}" text-anchor="middle" font-size="11" fill="#6b6f76">{escape(point.run_name)}</text>'
        for x, _, point in points
    )
    return (
        f'<div class="chart-wrap"><svg viewBox="0 0 {width} {height}" role="img" aria-label="Trend chart">'
        f'<line x1="40" y1="{height - 40}" x2="{width - 20}" y2="{height - 40}" stroke="#d9d1c3" />'
        f'<line x1="40" y1="20" x2="40" y2="{height - 40}" stroke="#d9d1c3" />'
        f'<polyline fill="none" stroke="#0b6e4f" stroke-width="3" points="{polyline}" />'
        f"{circles}{labels}</svg></div>"
    )


def render_status_bar(distribution: RunStatusDistribution) -> str:
    if distribution.total == 0:
        return '<p class="empty">No runs available.</p>'
    bars = []
    for item in distribution.by_status:
        width = 0 if distribution.total == 0 else (item.count / distribution.total) * 100
        bars.append(
            '<div style="margin-top:10px;">'
            f'<div class="muted">{escape(item.status)} ({item.count})</div>'
            f'<div style="background:#e8dfd0;border-radius:999px;height:10px;overflow:hidden;">'
            f'<div style="width:{width:.1f}%;height:10px;background:#d97706;"></div></div>'
            '</div>'
        )
    return "".join(bars)


__all__ = ["DashboardConfig", "render_line_chart", "render_status_bar"]
