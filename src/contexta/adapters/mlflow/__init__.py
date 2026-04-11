"""Optional MLflow adapter namespace for Contexta.

MLflow bridge code should enter through this package and remain outside the
base runtime dependency path.

Raises ``DependencyError`` at construction time when ``mlflow``
is not installed. Install it with: pip install 'contexta[mlflow]'
"""

from ._sink import MLflowSink

__all__ = ["MLflowSink"]
