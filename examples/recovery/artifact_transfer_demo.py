"""Artifact export/import recovery example for Contexta."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any

from contexta.contract import ArtifactManifest
from contexta.store.artifacts import ArtifactStore, VaultConfig, export_artifact, import_export_package, inspect_store


def _resolve_root(root: Path | str | None) -> Path:
    if root is None:
        return Path(tempfile.mkdtemp(prefix="contexta-artifact-transfer-demo-"))
    return Path(root)


def run_example(root: Path | str | None = None) -> dict[str, Any]:
    base_root = _resolve_root(root)
    base_root.mkdir(parents=True, exist_ok=True)
    source_root = base_root / "source-artifacts"
    target_root = base_root / "target-artifacts"
    export_root = base_root / "exports"
    model_path = base_root / "model.bin"
    model_path.write_bytes(b"artifact content for recovery example")

    source_store = ArtifactStore(VaultConfig(root_path=source_root))
    target_store = ArtifactStore(VaultConfig(root_path=target_root))

    manifest = ArtifactManifest(
        artifact_ref="artifact:my-proj.run-01.model",
        artifact_kind="checkpoint",
        created_at="2024-01-01T00:00:00Z",
        producer_ref="contexta.recovery.example",
        run_ref="run:my-proj.run-01",
        location_ref="vault://my-proj/run-01/model.bin",
    )

    put_receipt = source_store.put_artifact(manifest, model_path)
    export_receipt = export_artifact(source_store, "artifact:my-proj.run-01.model", export_root=export_root)
    import_receipt = import_export_package(target_store, export_receipt.export_directory)
    target_summary = inspect_store(target_store)

    return {
        "source_binding": put_receipt.binding.artifact_ref,
        "export_directory": str(export_receipt.export_directory),
        "import_outcome": import_receipt.outcome.value,
        "target_artifact_count": target_summary.artifact_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Contexta artifact transfer example.")
    parser.add_argument("--root", type=Path, default=None, help="Optional demo root directory.")
    args = parser.parse_args()

    result = run_example(args.root)
    print(f"Source artifact: {result['source_binding']}")
    print(f"Export directory: {result['export_directory']}")
    print(f"Import outcome: {result['import_outcome']}")
    print(f"Target artifact count: {result['target_artifact_count']}")


if __name__ == "__main__":
    main()
