# Adapter Examples

Runnable demos for Contexta's optional sink adapters.

## stdout_sink_demo.py

**No extra packages required.**

Attaches `StdoutSink` to a Contexta instance. Every captured record is
printed as a JSON line to stdout.

```powershell
uv run python examples/adapters/stdout_sink_demo.py
```

Useful for local debugging and CI log inspection without any external tooling.

---

## otel_sink_demo.py

**Requires:** `opentelemetry-api` + `opentelemetry-sdk`

```powershell
uv pip install 'contexta[otel]'
uv pip install opentelemetry-sdk   # for in-process exporter used by demo
uv run python examples/adapters/otel_sink_demo.py
```

Sets up an in-process `InMemorySpanExporter` (no collector needed), routes
`TraceSpanRecord` and `MetricRecord` through `OTelSink`, then reads back
the exported spans to confirm the bridge is working.

If `opentelemetry-api` is absent, the script prints an installation hint
and exits cleanly.

---

## mlflow_sink_demo.py

**Requires:** `mlflow`

```powershell
uv pip install 'contexta[mlflow]'
uv run python examples/adapters/mlflow_sink_demo.py
```

Uses an on-disk MLflow tracking store (no MLflow server needed), logs
metrics and an event through `MLflowSink`, then reads the data back via
`MlflowClient` to confirm the bridge is working.

If `mlflow` is absent, the script prints an installation hint and exits cleanly.

---

## Sink comparison

| Sink | Extra | Use case |
|---|---|---|
| `StdoutSink` | none | local debugging, CI log capture |
| `OTelSink` | `[otel]` | production tracing + metrics via OTel collector |
| `MLflowSink` | `[mlflow]` | ML experiment tracking in MLflow UI |
