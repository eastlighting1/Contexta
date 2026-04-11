"""NotebookSurface facade bound to a Contexta instance."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .rendering import (
    NotebookFragment,
    display_metric_trend,
    display_run_comparison,
    display_run_snapshot,
    render_html_fragment,
    to_pandas,
    to_polars,
)

if TYPE_CHECKING:
    from ...api import Contexta
    from ...interpretation import RunListQuery


class NotebookSurface:
    """Notebook display helpers pre-bound to a Contexta instance.

    Accessed via ``ctx.notebook``. All methods accept the same optional
    ``display=True`` flag to trigger IPython.display automatically when
    running inside a Jupyter-compatible kernel.
    """

    __slots__ = ("_ctx",)

    def __init__(self, ctx: "Contexta") -> None:
        self._ctx = ctx

    def show_run(self, run_id: str, *, display: bool = True) -> NotebookFragment:
        """Display a run snapshot."""
        return display_run_snapshot(self._ctx, run_id, display=display)

    def compare_runs(
        self,
        left_run_id: str,
        right_run_id: str,
        *,
        display: bool = True,
    ) -> NotebookFragment:
        """Display a two-run comparison."""
        return display_run_comparison(self._ctx, left_run_id, right_run_id, display=display)

    def show_metric_trend(
        self,
        metric_key: str,
        *,
        project_name: str | None = None,
        stage_name: str | None = None,
        query: Any | None = None,
        display: bool = True,
    ) -> NotebookFragment:
        """Display a metric trend chart."""
        return display_metric_trend(
            self._ctx,
            metric_key,
            project_name=project_name,
            stage_name=stage_name,
            query=query,
            display=display,
        )

    def render(self, value: object) -> str:
        """Return embeddable HTML for any supported result object."""
        return render_html_fragment(value)

    def to_pandas(self, value: object) -> Any:
        """Convert a supported result object to a pandas DataFrame."""
        return to_pandas(value)

    def to_polars(self, value: object) -> Any:
        """Convert a supported result object to a polars DataFrame."""
        return to_polars(value)


__all__ = ["NotebookSurface"]
