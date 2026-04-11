"""OTelSink demo — requires opentelemetry-api.

Install the optional extra first:

    pip install 'contexta[otel]'
    # or:
    uv pip install 'contexta[otel]'

Then run from the repository root:

    uv run python examples/adapters/otel_sink_demo.py

What this demo does:
- Sets up an in-process OTel TracerProvider with a SimpleSpanProcessor
  that collects exported spans into a list (no external collector needed)
- Captures a TraceSpanRecord and a MetricRecord through OTelSink
- Prints the exported span names to confirm the bridge is working
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# --- Dependency check (friendly error before deep import) ---
try:
    import opentelemetry  # noqa: F401
except ImportError:
    print(
        "opentelemetry-api is not installed.\n"
        "Install it with:  pip install 'contexta[otel]'\n",
        file=sys.stderr,
    )
    sys.exit(1)

from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import]
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # type: ignore[import]
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter  # type: ignore[import]
from opentelemetry.sdk.metrics import MeterProvider  # type: ignore[import]

from contexta import Contexta
from contexta.adapters.otel import OTelSink
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    MetricPayload,
    MetricRecord,
    Project,
    RecordEnvelope,
    Run,
    TraceSpanPayload,
    TraceSpanRecord,
)
import uuid


PROJECT_NAME = "otel-demo"
RUN_NAME = "run-01"
RUN_REF = f"run:{PROJECT_NAME}.{RUN_NAME}"


def main() -> None:
    workspace = Path(tempfile.mkdtemp(prefix="contexta-otel-")) / ".contexta"

    # --- In-process OTel setup (no collector required) ---
    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

    meter_provider = MeterProvider()

    sink = OTelSink(
        service_name=PROJECT_NAME,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        name="otel",
    )

    ctx = Contexta(
        config=UnifiedConfig(
            project_name=PROJECT_NAME,
            workspace=WorkspaceConfig(root_path=workspace),
        ),
        sinks=[sink],
    )
    store = ctx.metadata_store

    try:
        store.projects.put_project(
            Project(
                project_ref=f"project:{PROJECT_NAME}",
                name=PROJECT_NAME,
                created_at="2025-01-01T00:00:00Z",
            )
        )
        store.runs.put_run(
            Run(
                run_ref=RUN_REF,
                project_ref=f"project:{PROJECT_NAME}",
                name=RUN_NAME,
                status="completed",
                started_at="2025-01-01T00:00:00Z",
                ended_at="2025-01-01T00:05:00Z",
            )
        )

        # Capture a span record → exported as an OTel span
        ctx.record_store.append(
            TraceSpanRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{PROJECT_NAME}.{RUN_NAME}.sp0001",
                    record_type="span",
                    recorded_at="2025-01-01T00:01:00Z",
                    observed_at="2025-01-01T00:01:00Z",
                    producer_ref="contexta.otel-demo",
                    run_ref=RUN_REF,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=TraceSpanPayload(
                    span_id=str(uuid.uuid4()),
                    trace_id=str(uuid.uuid4()),
                    parent_span_id=None,
                    span_name="model.train",
                    started_at="2025-01-01T00:01:00Z",
                    ended_at="2025-01-01T00:04:00Z",
                    status="ok",
                    span_kind="operation",
                    attributes={"framework": "pytorch", "epochs": "10"},
                    linked_refs=None,
                ),
            )
        )

        # Capture a metric → recorded as an OTel histogram observation
        ctx.record_store.append(
            MetricRecord(
                envelope=RecordEnvelope(
                    record_ref=f"record:{PROJECT_NAME}.{RUN_NAME}.m0001",
                    record_type="metric",
                    recorded_at="2025-01-01T00:03:00Z",
                    observed_at="2025-01-01T00:03:00Z",
                    producer_ref="contexta.otel-demo",
                    run_ref=RUN_REF,
                    completeness_marker="complete",
                    degradation_marker="none",
                ),
                payload=MetricPayload(
                    metric_key="loss",
                    value=0.38,
                    value_type="float64",
                    unit="1",
                ),
            )
        )

        # Inspect exported spans
        finished_spans = exporter.get_finished_spans()
        print(f"OTel spans exported:  {len(finished_spans)}")
        for span in finished_spans:
            print(f"  span: {span.name!r}  status: {span.status.status_code.name}")

        print(f"\nWorkspace:  {workspace}")

    finally:
        store.close()


if __name__ == "__main__":
    main()
