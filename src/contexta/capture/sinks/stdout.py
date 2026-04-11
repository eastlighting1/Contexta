"""Stdout capture sink — lightweight built-in for development and CI logging."""

from __future__ import annotations

import json
import sys
from typing import Any

from .protocol import BaseSink, SinkCaptureReceipt
from ..results import PayloadFamily


class StdoutSink(BaseSink):
    """Print captured payloads as newline-delimited JSON to stdout or stderr.

    Requires only stdlib. Useful for local debugging, CI pipelines, or any
    environment where writing files is impractical.
    """

    def __init__(
        self,
        *,
        name: str = "stdout",
        stream: str = "stdout",
        supported_families: tuple[PayloadFamily | str, ...] | None = None,
        indent: int | None = None,
    ) -> None:
        super().__init__(name=name, supported_families=supported_families)
        if stream not in {"stdout", "stderr"}:
            raise ValueError("stream must be 'stdout' or 'stderr'.")
        self._stream = stream
        self._indent = indent

    @property
    def stream(self) -> str:
        return self._stream

    def capture(self, *, family: PayloadFamily | str, payload: object) -> SinkCaptureReceipt:
        request = self.make_request(family=family, payload=payload)
        entry: dict[str, Any] = {
            "sink": self.name,
            "family": request.family.value,
            "payload_type": request.payload_type,
            "payload_ref": request.payload_ref,
            "payload": request.serialized_payload,
        }
        line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"), indent=self._indent, default=str)
        target = sys.stderr if self._stream == "stderr" else sys.stdout
        print(line, file=target, flush=True)
        return SinkCaptureReceipt.success(
            detail=f"printed to {self._stream}",
            metadata={"stream": self._stream, "payload_ref": request.payload_ref},
        )


__all__ = ["StdoutSink"]
