"""Internal notebook delivery surface for Contexta."""

from .rendering import (
    NotebookFragment,
    display_metric_trend,
    display_run_comparison,
    display_run_snapshot,
    render_html_fragment,
    to_pandas,
    to_polars,
)
from .surface import NotebookSurface

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
