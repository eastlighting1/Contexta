"""Internal HTML delivery surface for Contexta."""

from .charts import DashboardConfig, render_line_chart, render_status_bar
from .renderer import (
    render_html_comparison,
    render_html_dashboard,
    render_html_run_detail,
    render_html_run_list,
    render_html_trend,
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
