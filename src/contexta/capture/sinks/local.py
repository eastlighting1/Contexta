"""Local JSONL capture sink."""

from __future__ import annotations

import json
from pathlib import Path

from ...common.errors import DispatchError
from ...common.io import ensure_directory, resolve_path
from ...common.time import iso_utc_now
from .protocol import BaseSink, SinkCaptureReceipt
from ..results import PayloadFamily


class LocalJsonlSink(BaseSink):
    """Append canonical payload snapshots to per-family local JSONL files."""

    def __init__(
        self,
        storage_root: str | Path,
        *,
        name: str = "local-jsonl",
        supported_families: tuple[PayloadFamily | str, ...] | None = None,
    ) -> None:
        super().__init__(name=name, supported_families=supported_families)
        self.storage_root = ensure_directory(storage_root)

    def file_path_for(self, family: PayloadFamily | str) -> Path:
        normalized = PayloadFamily(family) if isinstance(family, str) else family
        return resolve_path(f"{normalized.value.lower()}.jsonl", base=self.storage_root)

    def capture(self, *, family: PayloadFamily | str, payload: object) -> SinkCaptureReceipt:
        request = self.make_request(family=family, payload=payload)
        target = self.file_path_for(request.family)
        ensure_directory(target.parent)
        entry = {
            "captured_at": iso_utc_now(),
            "sink_name": self.name,
            "family": request.family.value,
            "payload_type": request.payload_type,
            "payload_ref": request.payload_ref,
            "payload": request.serialized_payload,
        }
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str) + "\n"
        try:
            with target.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
        except OSError as exc:
            raise DispatchError(
                f"LocalJsonlSink failed to append '{target}'.",
                code="local_jsonl_sink_write_failed",
                details={
                    "sink_name": self.name,
                    "path": str(target),
                    "family": request.family.value,
                },
                retryable=True,
                cause=exc,
            ) from exc
        return SinkCaptureReceipt.success(
            detail=f"appended payload to {target.name}",
            metadata={
                "path": str(target),
                "payload_ref": request.payload_ref,
                "payload_type": request.payload_type,
            },
        )


__all__ = ["LocalJsonlSink"]
