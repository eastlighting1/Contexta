"""Public notebook API for Contexta."""

from ..surfaces.notebook import (
    NotebookFragment,
    NotebookSurface,
    display_metric_trend,
    display_run_comparison,
    display_run_snapshot,
    render_html_fragment,
    to_pandas,
    to_polars,
)

__all__ = [
    "NotebookFragment",
    "NotebookSurface",
    "display_metric_trend",
    "display_run_comparison",
    "display_run_snapshot",
    "render_html_fragment",
    "to_pandas",
    "to_polars",
]
