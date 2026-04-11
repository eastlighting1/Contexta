"""StdoutSink demo — no extra packages required.

Demonstrates using StdoutSink to print captured records as JSON lines.

StdoutSink can be used in two ways:
1. Attached to a Contexta instance via `sinks=[sink]` — it will receive
   records dispatched through the runtime capture scope (run/stage/metric).
2. Called directly via `sink.capture(family=..., payload=...)` for records
   constructed manually and appended via record_store.

This demo uses direct calls so that the output is immediately visible
without needing the full runtime scope setup.

Run from the repository root:

    uv run python examples/adapters/stdout_sink_demo.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from contexta.capture.sinks import StdoutSink
from contexta.capture.results import PayloadFamily
from contexta.contract import (
    MetricPayload,
    MetricRecord,
    RecordEnvelope,
    StructuredEventPayload,
    StructuredEventRecord,
)


PROJECT_NAME = "sink-demo"
RUN_NAME = "run-01"
RUN_REF = f"run:{PROJECT_NAME}.{RUN_NAME}"


def main() -> None:
    # StdoutSink: prints every captured record as a JSON line.
    # Use stream="stderr" to separate capture output from application logs.
    sink = StdoutSink(name="console", stream="stdout", indent=2)

    print("=== Captured records (JSON) ===\n")

    # Capture a metric record
    metric = MetricRecord(
        envelope=RecordEnvelope(
            record_ref=f"record:{PROJECT_NAME}.{RUN_NAME}.m0001",
            record_type="metric",
            recorded_at="2025-01-01T00:02:00Z",
            observed_at="2025-01-01T00:02:00Z",
            producer_ref="contexta.stdout-demo",
            run_ref=RUN_REF,
            completeness_marker="complete",
            degradation_marker="none",
        ),
        payload=MetricPayload(
            metric_key="loss",
            value=0.42,
            value_type="float64",
        ),
    )
    receipt = sink.capture(family=PayloadFamily.RECORD, payload=metric)
    assert receipt.status.value == "SUCCESS"

    print()  # blank line between records

    # Capture a structured event record
    event = StructuredEventRecord(
        envelope=RecordEnvelope(
            record_ref=f"record:{PROJECT_NAME}.{RUN_NAME}.e0001",
            record_type="event",
            recorded_at="2025-01-01T00:03:00Z",
            observed_at="2025-01-01T00:03:00Z",
            producer_ref="contexta.stdout-demo",
            run_ref=RUN_REF,
            completeness_marker="complete",
            degradation_marker="none",
        ),
        payload=StructuredEventPayload(
            event_key="training.epoch-end",
            level="info",
            message="Epoch 1 complete - loss=0.42",
            origin_marker="explicit_capture",
        ),
    )
    receipt = sink.capture(family=PayloadFamily.RECORD, payload=event)
    assert receipt.status.value == "SUCCESS"

    print(f"\n=== Done ===")
    print(f"Sink name:  {sink.name}")
    print(f"Stream:     {sink.stream}")
    print(f"Records:    2 captured successfully")


if __name__ == "__main__":
    main()
