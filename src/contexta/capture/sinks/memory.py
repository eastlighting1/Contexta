"""In-memory capture sink for development and tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .protocol import BaseSink, SinkCaptureReceipt, SinkCaptureRequest
from ..results import PayloadFamily


@dataclass(frozen=True, slots=True)
class InMemorySinkEntry:
    """Immutable snapshot of one captured payload."""

    request: SinkCaptureRequest

    @property
    def family(self) -> PayloadFamily:
        return self.request.family

    @property
    def payload(self) -> object:
        return self.request.payload

    @property
    def payload_type(self) -> str:
        return self.request.payload_type

    @property
    def payload_ref(self) -> str | None:
        return self.request.payload_ref

    def to_dict(self) -> dict[str, Any]:
        return self.request.to_dict()


class InMemorySink(BaseSink):
    """Append-only in-memory sink for local debugging and tests."""

    def __init__(
        self,
        *,
        name: str = "memory",
        supported_families: tuple[PayloadFamily | str, ...] | None = None,
    ) -> None:
        super().__init__(name=name, supported_families=supported_families)
        self._entries: list[InMemorySinkEntry] = []

    @property
    def entries(self) -> tuple[InMemorySinkEntry, ...]:
        return tuple(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def capture(self, *, family: PayloadFamily | str, payload: object) -> SinkCaptureReceipt:
        request = self.make_request(family=family, payload=payload)
        entry = InMemorySinkEntry(request=request)
        self._entries.append(entry)
        return SinkCaptureReceipt.success(
            detail=f"captured by in-memory sink as entry {len(self._entries)}",
            metadata={
                "entry_index": len(self._entries) - 1,
                "stored_entries": len(self._entries),
                "payload_ref": request.payload_ref,
                "payload_type": request.payload_type,
            },
        )


__all__ = ["InMemorySink", "InMemorySinkEntry"]
