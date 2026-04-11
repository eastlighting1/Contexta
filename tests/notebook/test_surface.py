from __future__ import annotations

import builtins

import pytest

from contexta.common.errors import DependencyError, RenderingError
from contexta.notebook import (
    NotebookFragment,
    display_metric_trend,
    display_run_comparison,
    display_run_snapshot,
    render_html_fragment,
    to_pandas,
    to_polars,
)


def test_display_run_snapshot_from_contexta(ctx_with_repo) -> None:
    fragment = display_run_snapshot(ctx_with_repo, "my-proj.run-01")
    assert isinstance(fragment, NotebookFragment)
    assert "my-proj.run-01" in fragment.html


def test_display_run_snapshot_from_snapshot_object(ctx_with_repo) -> None:
    snapshot = ctx_with_repo.get_run_snapshot("my-proj.run-01")
    fragment = display_run_snapshot(snapshot)
    assert "Run ID:" in fragment.html


def test_display_run_comparison_from_contexta(ctx_with_repo) -> None:
    fragment = display_run_comparison(ctx_with_repo, "my-proj.run-01", "my-proj.run-02")
    assert "my-proj.run-02" in fragment.html


def test_display_metric_trend_from_contexta(ctx_with_repo) -> None:
    fragment = display_metric_trend(ctx_with_repo, "loss", project_name="my-proj")
    assert "Trend: loss" in fragment.html


def test_render_html_fragment_for_report(ctx_with_repo) -> None:
    report = ctx_with_repo.build_snapshot_report("my-proj.run-01")
    html = render_html_fragment(report)
    assert "<article>" in html


def test_render_html_fragment_unsupported_type_raises() -> None:
    with pytest.raises(RenderingError):
        render_html_fragment(object())


def test_to_pandas_missing_dependency_raises(ctx_with_repo, monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = ctx_with_repo.get_run_snapshot("my-proj.run-01")
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pandas":
            raise ImportError("missing pandas")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(DependencyError):
        to_pandas(snapshot)


def test_to_polars_missing_dependency_raises(ctx_with_repo, monkeypatch: pytest.MonkeyPatch) -> None:
    trend = ctx_with_repo.get_metric_trend("loss", project_name="my-proj")
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "polars":
            raise ImportError("missing polars")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(DependencyError):
        to_polars(trend)
