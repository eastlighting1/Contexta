"""DataFrame export adapter hooks for the metadata store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence, runtime_checkable

from ....common.errors import DependencyError


@runtime_checkable
class FrameAdapterProtocol(Protocol):
    """Inspection-only protocol for DataFrame exports."""

    def query(self, sql: str, params: Sequence[Any] | None = None) -> Any: ...

    def table(self, table_name: str) -> Any: ...


@dataclass(slots=True)
class PandasAdapter:
    """Pandas inspection adapter hook."""

    sql_adapter: Any

    def query(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        try:
            import pandas as pd  # type: ignore
        except ImportError as exc:
            raise DependencyError(
                "pandas is required for the metadata pandas adapter.",
                code="metadata_pandas_adapter_not_ready",
                cause=exc,
            ) from exc
        rows = self.sql_adapter.query_all(sql, params)
        columns = [item[0] for item in self.sql_adapter.execute(sql, params or ()).description]
        return pd.DataFrame.from_records(rows, columns=columns)

    def table(self, table_name: str) -> Any:
        return self.query(f"SELECT * FROM {table_name}")


@dataclass(slots=True)
class PolarsAdapter:
    """Polars inspection adapter hook."""

    sql_adapter: Any

    def query(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        try:
            import polars as pl  # type: ignore
        except ImportError as exc:
            raise DependencyError(
                "polars is required for the metadata polars adapter.",
                code="metadata_polars_adapter_not_ready",
                cause=exc,
            ) from exc
        rows = self.sql_adapter.query_all(sql, params)
        columns = [item[0] for item in self.sql_adapter.execute(sql, params or ()).description]
        return pl.DataFrame(rows, schema=columns, orient="row")

    def table(self, table_name: str) -> Any:
        return self.query(f"SELECT * FROM {table_name}")


__all__ = ["FrameAdapterProtocol", "PandasAdapter", "PolarsAdapter"]
