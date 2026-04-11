# Adapters

This page explains Contexta's optional sink adapters — integrations with
external observability and experiment-tracking systems.

## Architecture

Contexta separates the core runtime from vendor integrations through a strict
boundary. Core packages (`contract`, `runtime`, `capture`, `store`,
`interpretation`) have no dependency on any external vendor library.

Adapters live in `contexta.adapters.*`. They implement the `Sink` protocol
and are inserted into the `CaptureDispatcher` at construction time:

```python
ctx = Contexta(sinks=[MySink(), AnotherSink()])
```

When a record is captured, the dispatcher fans it out to all registered sinks.

## Dependency policy

Vendor-gated adapters raise `DependencyError` at **construction time** if the
required package is absent — not on the first `capture()` call. This ensures
that a misconfigured sink fails loudly before any data flows.

```python
from contexta.common.errors import DependencyError

try:
    sink = OTelSink()
except DependencyError as e:
    print(e.code)  # "otel_api_not_ready"
```

Install optional extras to enable them:

```bash
pip install 'contexta[otel]'
pip install 'contexta[mlflow]'
```

---

## StdoutSink

**Extra:** none — stdlib only.

Prints every captured record as a JSON line. Useful for local debugging
and CI log inspection.

```python
from contexta.capture.sinks import StdoutSink

sink = StdoutSink(
    name="console",     # sink name in dispatcher
    stream="stdout",    # "stdout" or "stderr"
    indent=None,        # None = compact, 2 = pretty-print
)
ctx = Contexta(sinks=[sink])
```

`StdoutSink` supports all `PayloadFamily` values — it prints everything it
receives.

---

## OTelSink

**Extra:** `pip install 'contexta[otel]'`

Exports Contexta capture payloads to the OpenTelemetry API.

```python
from contexta.adapters.otel import OTelSink

sink = OTelSink(
    service_name="my-ml-service",  # OTel tracer/meter scope name
    tracer_provider=None,          # None → use global OTel provider
    meter_provider=None,           # None → use global OTel provider
    name="otel",
)
ctx = Contexta(sinks=[sink])
```

### What gets exported

| Contexta record | OTel concept |
|---|---|
| `TraceSpanRecord` | Span (via `tracer.start_span`) |
| `MetricRecord` | Histogram observation |
| `StructuredEventRecord` | Event on the current active span |
| `DegradedRecord` | Event (`contexta.degraded`) on the current active span |

### Span kind mapping

| Contexta `span_kind` | OTel `SpanKind` |
|---|---|
| `operation`, `internal` | `INTERNAL` |
| `io`, `network` | `CLIENT` |
| `process` | `PRODUCER` |

### Provider setup

OTelSink does not configure exporters, samplers, or resources — that is the
caller's responsibility. When `tracer_provider=None`, the globally registered
provider is used.

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

sink = OTelSink(tracer_provider=provider)
```

OTelSink only supports `PayloadFamily.RECORD`. Context payloads are silently
skipped.

---

## MLflowSink

**Extra:** `pip install 'contexta[mlflow]'`

Exports Contexta capture payloads to the MLflow Tracking API.

```python
from contexta.adapters.mlflow import MLflowSink

sink = MLflowSink(
    run_id=None,    # None → log to the active mlflow.start_run() context
    name="mlflow",
)
ctx = Contexta(sinks=[sink])
```

### What gets exported

| Contexta record | MLflow concept |
|---|---|
| `MetricRecord` | `mlflow.log_metric` |
| `StructuredEventRecord` | `mlflow.set_tag` (`contexta.event.<key>`) |
| `DegradedRecord` | `mlflow.set_tag` (`contexta.degraded.<key>`) |

`TraceSpanRecord` is silently skipped (MLflow tracing API is version-gated;
reserved for future extension).

### Active run vs explicit run_id

When `run_id=None`, all calls target the currently active MLflow run:

```python
with mlflow.start_run():
    sink = MLflowSink()
    ctx = Contexta(sinks=[sink])
    # ... all captures go to the active run
```

When `run_id` is provided, all calls include it explicitly:

```python
sink = MLflowSink(run_id="abc123def456")
```

### Tag write behaviour

To avoid write amplification on high-frequency metrics, MLflowSink writes
unit tags and metric tags at most once per `(metric_key)` per sink instance.
The `contexta.run_ref` tag is also written once.

MLflowSink only supports `PayloadFamily.RECORD`. Context payloads are silently
skipped.

---

## Thread safety

All three adapters are **not thread-safe** by default. Pass a separate sink
instance per thread or protect access externally.

---

## Examples

See [`examples/adapters/`](../../examples/adapters/) for runnable demos of
each sink.
