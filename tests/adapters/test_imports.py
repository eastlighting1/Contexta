"""EXT-018: Adapter boundary import smoke tests."""

from __future__ import annotations

import io
import sys

import pytest

from contexta.adapters.dataframes import FrameAdapterProtocol, PandasAdapter, PolarsAdapter


# ---------------------------------------------------------------------------
# dataframes adapter (existing)
# ---------------------------------------------------------------------------

def test_dataframe_adapter_namespace_reexports() -> None:
    assert FrameAdapterProtocol.__name__ == "FrameAdapterProtocol"
    assert PandasAdapter.__name__ == "PandasAdapter"
    assert PolarsAdapter.__name__ == "PolarsAdapter"


# ---------------------------------------------------------------------------
# adapters __init__ lists all sub-packages
# ---------------------------------------------------------------------------

def test_optional_adapter_namespaces_import() -> None:
    import contexta.adapters as adapters

    assert set(adapters.__all__) == {"dataframes", "export", "html", "mlflow", "notebook", "otel"}


# ---------------------------------------------------------------------------
# notebook adapter
# ---------------------------------------------------------------------------

def test_notebook_adapter_exports_surface() -> None:
    from contexta.adapters.notebook import (
        NotebookFragment,
        NotebookSurface,
        display_metric_trend,
        display_run_comparison,
        display_run_snapshot,
        render_html_fragment,
        to_pandas,
        to_polars,
    )
    assert NotebookSurface.__name__ == "NotebookSurface"
    assert NotebookFragment.__name__ == "NotebookFragment"
    assert callable(display_run_snapshot)
    assert callable(display_run_comparison)
    assert callable(display_metric_trend)
    assert callable(render_html_fragment)
    assert callable(to_pandas)
    assert callable(to_polars)


def test_notebook_adapter_all_is_complete() -> None:
    import contexta.adapters.notebook as nb
    assert "NotebookSurface" in nb.__all__
    assert "NotebookFragment" in nb.__all__
    assert "display_run_snapshot" in nb.__all__


# ---------------------------------------------------------------------------
# export adapter (CSV, stdlib-only)
# ---------------------------------------------------------------------------

def test_export_adapter_imports() -> None:
    from contexta.adapters.export import (
        export_anomaly_csv,
        export_comparison_csv,
        export_run_list_csv,
        export_trend_csv,
    )
    assert callable(export_run_list_csv)
    assert callable(export_comparison_csv)
    assert callable(export_trend_csv)
    assert callable(export_anomaly_csv)


def test_export_adapter_all_is_complete() -> None:
    import contexta.adapters.export as exp
    assert set(exp.__all__) == {
        "export_anomaly_csv",
        "export_comparison_csv",
        "export_run_list_csv",
        "export_trend_csv",
    }


# ---------------------------------------------------------------------------
# html adapter (stdlib-only)
# ---------------------------------------------------------------------------

def test_html_adapter_imports() -> None:
    from contexta.adapters.html import (
        DashboardConfig,
        render_html_comparison,
        render_html_dashboard,
        render_html_run_detail,
        render_html_run_list,
        render_html_trend,
        render_line_chart,
        render_status_bar,
    )
    assert callable(render_html_run_detail)
    assert callable(render_html_trend)
    assert DashboardConfig.__name__ == "DashboardConfig"


def test_html_adapter_all_is_complete() -> None:
    import contexta.adapters.html as html
    assert "render_html_run_detail" in html.__all__
    assert "render_html_trend" in html.__all__
    assert "DashboardConfig" in html.__all__


# ---------------------------------------------------------------------------
# StdoutSink
# ---------------------------------------------------------------------------

def test_stdout_sink_imports_from_sinks() -> None:
    from contexta.capture.sinks import StdoutSink
    assert StdoutSink.__name__ == "StdoutSink"


def test_stdout_sink_default_stream_is_stdout() -> None:
    from contexta.capture.sinks import StdoutSink
    sink = StdoutSink()
    assert sink.stream == "stdout"
    assert sink.name == "stdout"


def test_stdout_sink_accepts_stderr_stream() -> None:
    from contexta.capture.sinks import StdoutSink
    sink = StdoutSink(stream="stderr", name="debug")
    assert sink.stream == "stderr"


def test_stdout_sink_invalid_stream_raises() -> None:
    from contexta.capture.sinks import StdoutSink
    with pytest.raises(ValueError, match="stream"):
        StdoutSink(stream="file")


def test_stdout_sink_capture_writes_json_line(capsys) -> None:
    from contexta.capture.sinks import StdoutSink
    from contexta.capture.results import PayloadFamily

    class FakePayload:
        def to_dict(self):
            return {"key": "loss", "value": 0.5}

    sink = StdoutSink()
    receipt = sink.capture(family=PayloadFamily.RECORD, payload=FakePayload())
    captured = capsys.readouterr()
    assert captured.out.strip() != ""
    import json
    data = json.loads(captured.out.strip())
    assert data["family"] == "RECORD"
    assert receipt.status.value == "SUCCESS"


def test_stdout_sink_stderr_goes_to_stderr(capsys) -> None:
    from contexta.capture.sinks import StdoutSink
    from contexta.capture.results import PayloadFamily

    class FakePayload:
        def to_dict(self):
            return {"key": "event"}

    sink = StdoutSink(stream="stderr")
    sink.capture(family=PayloadFamily.RECORD, payload=FakePayload())
    captured = capsys.readouterr()
    assert captured.err.strip() != ""
    assert captured.out.strip() == ""


def test_stdout_sink_supports_all_families() -> None:
    from contexta.capture.sinks import StdoutSink
    from contexta.capture.results import PayloadFamily
    sink = StdoutSink()
    for family in PayloadFamily:
        assert sink.supports(family)


# ---------------------------------------------------------------------------
# vendor-gated stubs still import cleanly
# ---------------------------------------------------------------------------

def test_otel_adapter_exports_otel_sink() -> None:
    import contexta.adapters.otel as otel
    assert otel.__all__ == ["OTelSink"]
    assert "OTelSink" in dir(otel)


def test_mlflow_adapter_exports_mlflow_sink() -> None:
    import sys
    import types
    # Inject fake mlflow so the import doesn't fail without the package
    if "mlflow" not in sys.modules:
        sys.modules["mlflow"] = types.ModuleType("mlflow")
        injected = True
    else:
        injected = False
    try:
        import importlib
        import contexta.adapters.mlflow as mlflow_adapter
        importlib.reload(mlflow_adapter)
        assert mlflow_adapter.__all__ == ["MLflowSink"]
    finally:
        if injected:
            del sys.modules["mlflow"]
