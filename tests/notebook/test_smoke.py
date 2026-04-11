from __future__ import annotations

import sys
import types

from contexta.notebook import (
    NotebookFragment,
    display_metric_trend,
    display_run_comparison,
    display_run_snapshot,
    render_html_fragment,
    to_pandas,
    to_polars,
)


def test_public_notebook_module_exports_expected_names() -> None:
    import contexta.notebook as notebook

    assert notebook.__all__ == [
        "NotebookFragment",
        "NotebookSurface",
        "display_metric_trend",
        "display_run_comparison",
        "display_run_snapshot",
        "render_html_fragment",
        "to_pandas",
        "to_polars",
    ]


def test_notebook_fragment_html_repr() -> None:
    fragment = NotebookFragment(html="<div>ok</div>", text="ok")
    assert fragment._repr_html_() == "<div>ok</div>"
    assert str(fragment) == "ok"


def test_display_helpers_return_fragments_for_public_surface(ctx_with_repo) -> None:
    snapshot_fragment = display_run_snapshot(ctx_with_repo, "my-proj.run-01")
    comparison_fragment = display_run_comparison(ctx_with_repo, "my-proj.run-01", "my-proj.run-02")
    trend_fragment = display_metric_trend(ctx_with_repo, "loss", project_name="my-proj")

    assert isinstance(snapshot_fragment, NotebookFragment)
    assert isinstance(comparison_fragment, NotebookFragment)
    assert isinstance(trend_fragment, NotebookFragment)


def test_display_flag_uses_ipython_when_available(ctx_with_repo, monkeypatch) -> None:
    calls: list[str] = []

    def fake_html(value: str) -> str:
        calls.append(f"html:{value[:16]}")
        return value

    def fake_display(value: object) -> None:
        calls.append("display")

    display_module = types.ModuleType("IPython.display")
    display_module.HTML = fake_html
    display_module.display = fake_display

    ipython_module = types.ModuleType("IPython")
    ipython_module.display = display_module

    monkeypatch.setitem(sys.modules, "IPython", ipython_module)
    monkeypatch.setitem(sys.modules, "IPython.display", display_module)

    fragment = display_run_snapshot(ctx_with_repo, "my-proj.run-01", display=True)

    assert isinstance(fragment, NotebookFragment)
    assert any(item.startswith("html:") for item in calls)
    assert "display" in calls


def test_render_html_fragment_accepts_core_result_types(ctx_with_repo) -> None:
    snapshot = ctx_with_repo.get_run_snapshot("my-proj.run-01")
    comparison = ctx_with_repo.compare_runs("my-proj.run-01", "my-proj.run-02")
    trend = ctx_with_repo.get_metric_trend("loss", project_name="my-proj")

    assert "<article>" in render_html_fragment(snapshot)
    assert "<article>" in render_html_fragment(comparison)
    assert "<article>" in render_html_fragment(trend)


def test_dataframe_helpers_work_with_fake_optional_modules(ctx_with_repo, monkeypatch) -> None:
    snapshot = ctx_with_repo.get_run_snapshot("my-proj.run-01")
    trend = ctx_with_repo.get_metric_trend("loss", project_name="my-proj")

    class FakePandasModule:
        class DataFrame:
            @staticmethod
            def from_records(rows, columns=None):
                return {"rows": rows, "columns": columns, "engine": "pandas"}

    class FakePolarsModule:
        @staticmethod
        def DataFrame(rows, schema=None, orient=None):
            return {"rows": rows, "schema": schema, "orient": orient, "engine": "polars"}

    monkeypatch.setitem(sys.modules, "pandas", FakePandasModule())
    monkeypatch.setitem(sys.modules, "polars", FakePolarsModule())

    pandas_result = to_pandas(snapshot)
    polars_result = to_polars(trend)

    assert pandas_result["engine"] == "pandas"
    assert pandas_result["rows"][0]["run_id"] == "my-proj.run-01"
    assert polars_result["engine"] == "polars"
    assert polars_result["rows"][0]["run_id"] == "my-proj.run-01"
