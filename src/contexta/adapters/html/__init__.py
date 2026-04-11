"""Built-in HTML adapter namespace for Contexta.

Re-exports the HTML delivery surface for embedding run data in web UIs,
static reports, or custom dashboards. Requires only stdlib (html, string).

    from contexta.adapters.html import render_html_run_detail, render_html_trend
"""

from ...surfaces.html import (
    DashboardConfig,
    render_html_comparison,
    render_html_dashboard,
    render_html_run_detail,
    render_html_run_list,
    render_html_trend,
    render_line_chart,
    render_status_bar,
)

__all__ = [
    "DashboardConfig",
    "render_html_comparison",
    "render_html_dashboard",
    "render_html_run_detail",
    "render_html_run_list",
    "render_html_trend",
    "render_line_chart",
    "render_status_bar",
]
