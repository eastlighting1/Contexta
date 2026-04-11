"""Export helpers for the artifact truth store."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from ...common.io import atomic_write_json, ensure_directory
from ...common.time import iso_utc_now
from .models import ExportReceipt

if TYPE_CHECKING:
    from .write import ArtifactStore


PACKAGE_FORMAT_VERSION = "contexta-artifact-export-v1"


def export_artifact(
    store: "ArtifactStore",
    artifact_ref: str,
    *,
    export_root: str | Path | None = None,
) -> ExportReceipt:
    handle = store.get_artifact(artifact_ref)
    root = store._normalize_path(export_root) if export_root is not None else store._exports_dir()
    export_directory = root / store._sanitize_component(artifact_ref)
    ensure_directory(export_directory)

    body_name = handle.path.name
    binding_name = f"{store._sanitize_component(artifact_ref)}.binding.json"
    body_path = export_directory / body_name
    binding_path = export_directory / binding_name
    manifest_path = export_directory / "manifest.snapshot.json"
    package_metadata_path = export_directory / "export.package.json"

    shutil.copy2(handle.path, body_path)
    atomic_write_json(binding_path, handle.binding.to_dict(), indent=2, sort_keys=True)
    atomic_write_json(manifest_path, handle.binding.manifest_snapshot.to_dict(), indent=2, sort_keys=True)
    atomic_write_json(
        package_metadata_path,
        {
            "package_format_version": PACKAGE_FORMAT_VERSION,
            "artifact_ref": artifact_ref,
            "artifact_kind": handle.binding.artifact_kind,
            "exported_at": iso_utc_now(),
            "body_file": body_name,
            "binding_file": binding_name,
            "manifest_file": manifest_path.name,
            "source_layout_version": handle.binding.layout_version,
        },
        indent=2,
        sort_keys=True,
    )
    _append_export_history(store, artifact_ref=artifact_ref, export_directory=export_directory)
    return ExportReceipt(
        artifact_ref=artifact_ref,
        export_directory=export_directory,
        body_path=body_path,
        binding_path=binding_path,
        package_metadata_path=package_metadata_path,
    )


def _append_export_history(store: "ArtifactStore", *, artifact_ref: str, export_directory: Path) -> None:
    history_dir = store.root_path / "history" / "exports" / store._sanitize_component(artifact_ref)
    ensure_directory(history_dir)
    event_path = history_dir / f"{iso_utc_now().replace(':', '-').replace('.', '_')}-{uuid4().hex}.json"
    atomic_write_json(
        event_path,
        {
            "artifact_ref": artifact_ref,
            "export_directory": str(export_directory),
            "exported_at": iso_utc_now(),
            "package_format_version": PACKAGE_FORMAT_VERSION,
        },
        indent=2,
        sort_keys=True,
    )


__all__ = ["PACKAGE_FORMAT_VERSION", "export_artifact"]
