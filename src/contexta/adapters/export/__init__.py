"""Built-in export adapter namespace for Contexta.

Provides lightweight CSV export helpers that require only stdlib (csv, io).
These are the canonical import home for export-oriented integrations.

    from contexta.adapters.export import export_run_list_csv, export_trend_csv
"""

from ...surfaces.export import (
    export_anomaly_csv,
    export_comparison_csv,
    export_run_list_csv,
    export_trend_csv,
)

__all__ = [
    "export_anomaly_csv",
    "export_comparison_csv",
    "export_run_list_csv",
    "export_trend_csv",
]
