"""Shared repository helpers for metadata persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from ....common.errors import NotFoundError
from ....contract import StableRef, to_json

if TYPE_CHECKING:
    from ..store import MetadataStore


def normalize_ref_text(value: StableRef | str, *, expected_kind: str | None = None) -> str:
    ref = value if isinstance(value, StableRef) else StableRef.parse(value)
    if expected_kind is not None and ref.kind != expected_kind:
        raise ValueError(f"Expected ref kind '{expected_kind}', got '{ref.kind}'.")
    return str(ref)


class BaseRepository:
    """Common helper behavior for metadata repositories."""

    table_name: str

    def __init__(self, store: "MetadataStore") -> None:
        self.store = store
        self._backend = store._backend

    def _serialize(self, model: Any) -> str:
        return to_json(model)

    def _fetch_one_payload(self, ref: StableRef | str, *, deserializer: Callable[[str], Any], entity_name: str) -> Any:
        ref_text = normalize_ref_text(ref)
        payload_json = self._backend.get_payload_json(self.table_name, ref_text)
        if payload_json is None:
            raise NotFoundError(
                f"{entity_name} was not found.",
                code="metadata_row_not_found",
                details={"table": self.table_name, "ref": ref_text},
            )
        return deserializer(payload_json)

    def _find_one_payload(self, ref: StableRef | str, *, deserializer: Callable[[str], Any]) -> Any | None:
        ref_text = normalize_ref_text(ref)
        payload_json = self._backend.get_payload_json(self.table_name, ref_text)
        if payload_json is None:
            return None
        return deserializer(payload_json)

    def _exists(self, ref: StableRef | str) -> bool:
        ref_text = normalize_ref_text(ref)
        return self._backend.exists_ref(self.table_name, ref_text)

    def _list_payloads(
        self,
        *,
        deserializer: Callable[[str], Any],
        where: str = "",
        params: tuple[Any, ...] = (),
        order_by: str = "ref",
    ) -> tuple[Any, ...]:
        payloads = self._backend.list_payload_json(
            self.table_name,
            where=where,
            params=params,
            order_by=order_by,
        )
        return tuple(deserializer(payload) for payload in payloads)


__all__ = ["BaseRepository", "normalize_ref_text"]
