"""Optional OpenTelemetry adapter namespace for Contexta.

OTel integration code should enter through this package and remain outside the
base runtime dependency path.

Raises ``DependencyError`` at construction time when ``opentelemetry-api``
is not installed. Install it with: pip install 'contexta[otel]'
"""

from ._sink import OTelSink

__all__ = ["OTelSink"]
