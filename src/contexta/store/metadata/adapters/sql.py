"""SQL inspection adapter for the metadata store."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, Sequence


@dataclass(slots=True)
class DuckDBAdapter:
    """Thin inspection adapter over the DuckDB metadata backend."""

    backend: Any

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        return self.backend.execute(sql, params or ())

    def query_one(self, sql: str, params: Sequence[Any] | None = None) -> tuple[Any, ...] | None:
        return self.backend.fetchone(sql, params or ())

    def query_all(self, sql: str, params: Sequence[Any] | None = None) -> tuple[tuple[Any, ...], ...]:
        return tuple(self.backend.fetchall(sql, params or ()))

    @contextmanager
    def transaction(self) -> Iterator["DuckDBAdapter"]:
        self.execute("BEGIN TRANSACTION")
        try:
            yield self
        except Exception:
            self.execute("ROLLBACK")
            raise
        else:
            self.execute("COMMIT")

    def get_schema_version(self) -> str:
        return self.backend.get_store_schema_version()


__all__ = ["DuckDBAdapter"]
