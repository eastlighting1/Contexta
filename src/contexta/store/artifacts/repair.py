"""Repair, quarantine, cleanup, and migration helpers for the artifact store."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from ...common.errors import ArtifactError, MigrationError, NotFoundError
from ...common.io import atomic_write_json, ensure_directory
from ...common.time import iso_utc_now
from .models import RepairPlan
from .verify import _evaluate_binding, _find_orphan_paths, _load_all_bindings, inspect_store

if TYPE_CHECKING:
    from .write import ArtifactStore


@dataclass(frozen=True, slots=True)
class ArtifactMigrationPlan:
    source_layout_version: str | None
    target_layout_version: str
    actions: tuple[str, ...]
    dry_run: bool = True


def refresh_verification(store: "ArtifactStore", artifact_ref: str):
    report = store.verify_artifact(artifact_ref)
    record = store._make_verification_record(report)
    store._append_verification_history(record=record, report=report)
    return record


def build_repair_plan(store: "ArtifactStore", *, dry_run: bool = True) -> RepairPlan:
    summary = inspect_store(store)
    actions: list[str] = []
    bindings = _load_all_bindings(store)
    for binding in bindings:
        report = _evaluate_binding(store, binding=binding, manifest=binding.manifest_snapshot)
        if report.status.value == "missing":
            actions.append(f"refresh_verification:{binding.artifact_ref}")
        elif report.status.value in {"size_mismatch", "hash_mismatch"}:
            actions.append(f"refresh_verification:{binding.artifact_ref}")
            actions.append(f"quarantine_bound_artifact:{binding.artifact_ref}")
    for orphan_path in _find_orphan_paths(store, bindings):
        actions.append(f"quarantine_orphan_body:{orphan_path}")
    abandoned = _find_abandoned_staging_paths(store)
    for path in abandoned:
        actions.append(f"remove_abandoned_staging:{path}")
    if summary.artifact_count == 0 and not actions:
        actions.append("noop:artifact_store_healthy_or_empty")
    return RepairPlan(actions=tuple(actions if dry_run else actions))


def quarantine_bound_artifact(store: "ArtifactStore", artifact_ref: str) -> Path:
    store._ensure_writable()
    handle = store.get_artifact(artifact_ref)
    destination = _quarantine_destination(
        store,
        category="bound",
        source_path=handle.path,
    )
    ensure_directory(destination.parent)
    os.replace(handle.path, destination)
    store._append_quarantine_history(
        kind="bound_artifact",
        source_path=handle.path,
        destination_path=destination,
        details={"artifact_ref": artifact_ref},
    )
    return destination


def quarantine_orphan_body(store: "ArtifactStore", orphan_path: str | Path) -> Path:
    store._ensure_writable()
    candidate = store._normalize_path(orphan_path)
    object_root = store._objects_dir()
    try:
        relative = candidate.relative_to(object_root)
    except ValueError as exc:
        raise ArtifactError(
            "orphan_path must point inside the artifact objects directory.",
            code="artifact_store_invalid_orphan_path",
            details={"orphan_path": str(candidate), "objects_dir": str(object_root)},
        ) from exc
    if not candidate.exists() or not candidate.is_file():
        raise NotFoundError(
            "orphan body was not found.",
            code="artifact_store_orphan_not_found",
            details={"orphan_path": str(candidate)},
        )
    if candidate in _find_orphan_paths(store, _load_all_bindings(store)):
        destination = store._quarantine_dir() / "orphans" / iso_utc_now().replace(":", "-").replace(".", "_") / relative
        ensure_directory(destination.parent)
        os.replace(candidate, destination)
        store._append_quarantine_history(
            kind="orphan_body",
            source_path=candidate,
            destination_path=destination,
            details={"orphan_path": str(candidate)},
        )
        return destination
    raise ArtifactError(
        "The provided path is not currently an orphan body.",
        code="artifact_store_not_an_orphan",
        details={"orphan_path": str(candidate)},
    )


def remove_abandoned_staging(store: "ArtifactStore") -> list[str]:
    store._ensure_writable()
    removed: list[str] = []
    for path in _find_abandoned_staging_paths(store):
        resolved = store._normalize_path(path)
        resolved.unlink(missing_ok=True)
        removed.append(str(resolved))
        metadata_path = resolved.with_suffix(".session.json")
        metadata_path.unlink(missing_ok=True)
        if metadata_path.exists():
            removed.append(str(metadata_path))
    for metadata_path in sorted(store._staging_dir().glob("*.session.json")):
        part_path = metadata_path.with_suffix(".part")
        if not part_path.exists():
            metadata_path.unlink(missing_ok=True)
            removed.append(str(metadata_path))
    return removed


def plan_migration(store: "ArtifactStore", *, target_layout_version: str | None = None) -> ArtifactMigrationPlan:
    target = target_layout_version or store.config.layout_version
    current = _detect_layout_version(store)
    actions: list[str] = []
    if current is None:
        actions.append("bootstrap:new_store")
    elif current != target:
        actions.append(f"migrate_layout:{current}->{target}")
    else:
        actions.append("noop:layout_already_current")
    return ArtifactMigrationPlan(
        source_layout_version=current,
        target_layout_version=target,
        actions=tuple(actions),
        dry_run=True,
    )


def migrate_bindings(store: "ArtifactStore", *, target_layout_version: str | None = None, dry_run: bool = True) -> ArtifactMigrationPlan:
    plan = plan_migration(store, target_layout_version=target_layout_version)
    if dry_run:
        return plan
    if plan.source_layout_version is None or plan.source_layout_version == plan.target_layout_version:
        return ArtifactMigrationPlan(
            source_layout_version=plan.source_layout_version,
            target_layout_version=plan.target_layout_version,
            actions=plan.actions,
            dry_run=False,
        )
    raise MigrationError(
        "Artifact binding migration is not implemented beyond baseline inspection.",
        code="artifact_store_migration_not_implemented",
        details={
            "source_layout_version": plan.source_layout_version,
            "target_layout_version": plan.target_layout_version,
        },
    )


def _find_abandoned_staging_paths(store: "ArtifactStore") -> list[Path]:
    staging_dir = store._staging_dir()
    if not staging_dir.exists():
        return []
    active_sessions = {path.stem for path in staging_dir.glob("*.session.json")}
    abandoned: list[Path] = []
    for part in sorted(staging_dir.glob("*.part")):
        if part.stem not in active_sessions:
            abandoned.append(part)
    return abandoned


def _quarantine_destination(store: "ArtifactStore", *, category: str, source_path: Path) -> Path:
    timestamp = iso_utc_now().replace(":", "-").replace(".", "_")
    return store._quarantine_dir() / category / timestamp / f"{uuid4().hex}-{source_path.name}"


def _detect_layout_version(store: "ArtifactStore") -> str | None:
    bindings_dir = store._bindings_dir()
    if not bindings_dir.exists():
        return None
    for path in sorted(bindings_dir.glob("*.binding.json")):
        binding = store._load_binding_from_path(path)
        return binding.layout_version
    return None


__all__ = [
    "ArtifactMigrationPlan",
    "build_repair_plan",
    "migrate_bindings",
    "plan_migration",
    "quarantine_bound_artifact",
    "quarantine_orphan_body",
    "refresh_verification",
    "remove_abandoned_staging",
]
