"""Inspection adapters for the metadata store."""

from .frame import FrameAdapterProtocol, PandasAdapter, PolarsAdapter
from .sql import DuckDBAdapter

__all__ = ["DuckDBAdapter", "FrameAdapterProtocol", "PandasAdapter", "PolarsAdapter"]
