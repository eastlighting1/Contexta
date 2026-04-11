"""Optional notebook adapter namespace for Contexta.

Re-exports the notebook delivery surface so that notebook-aware code can
import from this canonical adapter boundary rather than from internal surfaces.

    from contexta.adapters.notebook import NotebookSurface, display_run_snapshot
"""

from ...surfaces.notebook import (
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
