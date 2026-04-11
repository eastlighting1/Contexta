"""Read helpers for the artifact truth store."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Iterator

from ...common.errors import NotFoundError
from .models import ArtifactHandle

if TYPE_CHECKING:
    from .write import ArtifactStore


def get_artifact(store: "ArtifactStore", artifact_ref: str) -> ArtifactHandle:
    binding = store._load_binding(artifact_ref)
    if binding is None:
        raise NotFoundError(
            "Artifact binding was not found.",
            code="artifact_store_binding_not_found",
            details={"artifact_ref": artifact_ref},
        )
    path = store._expected_object_path(
        binding.manifest_snapshot,
        suffix=store._infer_suffix(None, binding.manifest_snapshot.location_ref),
    )
    if not path.exists():
        raise NotFoundError(
            "Artifact body was not found at the canonical object path.",
            code="artifact_store_body_not_found",
            details={"artifact_ref": artifact_ref, "path": str(path)},
        )
    return ArtifactHandle(binding=binding, path=path)


def artifact_exists(store: "ArtifactStore", artifact_ref: str) -> bool:
    try:
        get_artifact(store, artifact_ref)
    except NotFoundError:
        return False
    return True


def open_artifact(store: "ArtifactStore", artifact_ref: str, *, mode: str = "rb") -> BinaryIO:
    handle = get_artifact(store, artifact_ref)
    if "b" not in mode or any(flag in mode for flag in ("w", "a", "+")):
        raise ValueError("open_artifact() only supports binary read modes.")
    return handle.path.open(mode)


def read_artifact_bytes(store: "ArtifactStore", artifact_ref: str) -> bytes:
    handle = get_artifact(store, artifact_ref)
    return handle.path.read_bytes()


def iter_artifact_chunks(
    store: "ArtifactStore",
    artifact_ref: str,
    *,
    chunk_size: int | None = None,
) -> Iterator[bytes]:
    handle = get_artifact(store, artifact_ref)
    size = store.config.chunk_size_bytes if chunk_size is None else chunk_size
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError("chunk_size must be a positive integer.")
    with handle.path.open("rb") as stream:
        while True:
            chunk = stream.read(size)
            if not chunk:
                break
            yield chunk


def list_refs(store: "ArtifactStore") -> list[str]:
    refs: list[str] = []
    bindings_dir = store._bindings_dir()
    if not bindings_dir.exists():
        return refs
    for path in sorted(bindings_dir.glob("*.binding.json")):
        binding = store._load_binding_from_path(path)
        refs.append(binding.artifact_ref)
    return refs


__all__ = [
    "artifact_exists",
    "get_artifact",
    "iter_artifact_chunks",
    "list_refs",
    "open_artifact",
    "read_artifact_bytes",
]
