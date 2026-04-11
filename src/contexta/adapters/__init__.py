"""Internal optional adapter namespace for Contexta.

This package is the home for optional integrations that are not required for
the base local-first runtime path.

Built-in lightweight adapters (no external vendor dependencies):
- ``export``   — CSV export helpers (stdlib only)
- ``html``     — HTML rendering helpers (stdlib only)
- ``notebook`` — Notebook display surface (IPython optional, degrades cleanly)
- ``dataframes`` — pandas/polars metadata query adapters (optional deps)

Vendor-gated adapters (raise DependencyError when deps are absent):
- ``otel``   — OpenTelemetry bridge (requires opentelemetry-api extra)
- ``mlflow`` — MLflow bridge (requires mlflow extra)
"""

__all__ = ["dataframes", "export", "html", "mlflow", "notebook", "otel"]
