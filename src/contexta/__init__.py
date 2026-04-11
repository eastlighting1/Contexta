"""Public root package for Contexta."""

from .api import Contexta, __version__
from .common.errors import ContextaError

__all__ = ["Contexta", "ContextaError", "__version__"]
