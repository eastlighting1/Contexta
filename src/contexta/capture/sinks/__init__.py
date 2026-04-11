"""Built-in sink implementations for capture dispatch."""

from .composite import CompositeSink
from .local import LocalJsonlSink
from .memory import InMemorySink, InMemorySinkEntry
from .protocol import BaseSink, Sink, SinkCaptureReceipt, SinkCaptureRequest, extract_payload_ref
from .stdout import StdoutSink

__all__ = [
    "BaseSink",
    "CompositeSink",
    "InMemorySink",
    "InMemorySinkEntry",
    "LocalJsonlSink",
    "Sink",
    "SinkCaptureReceipt",
    "SinkCaptureRequest",
    "StdoutSink",
    "extract_payload_ref",
]
