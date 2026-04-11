"""Optional dataframe adapter namespace for Contexta.

The current dataframe hooks are backed by metadata inspection adapters and are
re-exported here so future adapter-owned code can converge on this namespace.
"""

from ...store.metadata.adapters.frame import FrameAdapterProtocol, PandasAdapter, PolarsAdapter

__all__ = ["FrameAdapterProtocol", "PandasAdapter", "PolarsAdapter"]
