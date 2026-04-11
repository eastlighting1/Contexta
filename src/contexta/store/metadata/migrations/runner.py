"""Migration inspection and runner helpers for metadata storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from ....common.errors import MigrationError, ReadOnlyStoreError, StoreAccessError
from ....common.time import iso_utc_now
from ..config import MetadataStoreConfig
from .models import MigrationHistoryRow, MigrationPlan, MigrationResult, MigrationStep, SchemaInspection


MigrationCallable = Callable[[Any], None]


STEP_REGISTRY: dict[tuple[str, str], MigrationStep] = {}
STEP_IMPLEMENTATIONS: dict[str, MigrationCallable] = {}


def inspect_schema(
    config: MetadataStoreConfig,
    *,
    target_version: str | None = None,
) -> SchemaInspection:
    from ..store import CURRENT_METADATA_STORE_SCHEMA_VERSION, _load_duckdb

    target = target_version or CURRENT_METADATA_STORE_SCHEMA_VERSION
    database_path = config.resolved_database_path()
    if database_path == ":memory:":
        return SchemaInspection(
            exists=False,
            current_version=None,
            target_version=target,
            requires_migration=False,
            supported=True,
            notes=("in_memory_store",),
        )

    database_file = Path(database_path)
    if not database_file.exists():
        return SchemaInspection(
            exists=False,
            current_version=None,
            target_version=target,
            requires_migration=False,
            supported=True,
            notes=("store_missing",),
        )

    duckdb = _load_duckdb()
    try:
        connection = duckdb.connect(str(database_file), read_only=bool(config.read_only))
    except Exception as exc:  # pragma: no cover
        raise StoreAccessError(
            "Failed to inspect the metadata store schema.",
            code="metadata_schema_inspection_failed",
            details={"database_path": str(database_file)},
            cause=exc,
        ) from exc
    try:
        schema_table = connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = 'schema_metadata'
            """
        ).fetchone()
        if schema_table is None:
            return SchemaInspection(
                exists=True,
                current_version=None,
                target_version=target,
                requires_migration=False,
                supported=False,
                notes=("schema_metadata_missing",),
            )
        row = connection.execute("SELECT store_schema_version FROM schema_metadata LIMIT 1").fetchone()
        current_version = None if row is None else str(row[0])
    finally:
        connection.close()

    if current_version is None:
        return SchemaInspection(
            exists=True,
            current_version=None,
            target_version=target,
            requires_migration=False,
            supported=False,
            notes=("schema_version_row_missing",),
        )

    path = _resolve_path(current_version, target)
    supported = current_version == target or path is not None
    return SchemaInspection(
        exists=True,
        current_version=current_version,
        target_version=target,
        requires_migration=current_version != target,
        supported=supported,
        notes=() if supported else ("unsupported_migration_path",),
    )


def plan_migration_for(
    config: MetadataStoreConfig,
    *,
    target_version: str | None = None,
) -> MigrationPlan:
    inspection = inspect_schema(config, target_version=target_version)
    if not inspection.exists or inspection.current_version is None:
        if inspection.supported:
            return MigrationPlan(current_version=inspection.current_version, target_version=inspection.target_version)
        raise MigrationError(
            "The metadata store is not a supported Contexta metadata lineage.",
            code="metadata_migration_unsupported_store",
            details={"notes": inspection.notes},
        )
    path = _resolve_path(inspection.current_version, inspection.target_version)
    if inspection.current_version == inspection.target_version:
        return MigrationPlan(current_version=inspection.current_version, target_version=inspection.target_version)
    if path is None:
        raise MigrationError(
            "No supported migration path exists for this metadata store version.",
            code="metadata_migration_path_missing",
            details={
                "current_version": inspection.current_version,
                "target_version": inspection.target_version,
            },
        )
    return MigrationPlan(
        current_version=inspection.current_version,
        target_version=inspection.target_version,
        steps=path,
    )


def dry_run_migration_for(
    config: MetadataStoreConfig,
    *,
    target_version: str | None = None,
) -> MigrationResult:
    plan = plan_migration_for(config, target_version=target_version)
    warnings = _build_plan_warnings(plan, config=config)
    return MigrationResult(
        current_version=plan.current_version,
        target_version=plan.target_version,
        applied_steps=plan.steps,
        dry_run=True,
        changed=False,
        history_rows=(),
        warnings=warnings,
    )


def migrate_for(
    config: MetadataStoreConfig,
    *,
    target_version: str | None = None,
) -> MigrationResult:
    if config.read_only:
        raise ReadOnlyStoreError(
            "Cannot migrate a read-only metadata store.",
            code="metadata_migration_read_only",
        )

    plan = plan_migration_for(config, target_version=target_version)
    warnings = _build_plan_warnings(plan, config=config)
    if not plan.steps:
        return MigrationResult(
            current_version=plan.current_version,
            target_version=plan.target_version,
            applied_steps=(),
            dry_run=False,
            changed=False,
            history_rows=(),
            warnings=warnings,
        )

    from ..store import _load_duckdb

    database_path = config.resolved_database_path()
    if database_path == ":memory:":
        raise MigrationError(
            "Migration requires a persisted metadata store path.",
            code="metadata_migration_in_memory_unsupported",
        )

    duckdb = _load_duckdb()
    connection = duckdb.connect(str(database_path))
    history_rows: list[MigrationHistoryRow] = []
    applied_steps: list[MigrationStep] = []
    current_version = plan.current_version
    try:
        for step in plan.steps:
            implementation = STEP_IMPLEMENTATIONS.get(step.step_id)
            if implementation is None:
                raise MigrationError(
                    "Migration step implementation is missing.",
                    code="metadata_migration_step_missing",
                    details={"step_id": step.step_id},
                )
            applied_at = iso_utc_now()
            try:
                connection.begin()
                implementation(connection)
                connection.execute(
                    "UPDATE schema_metadata SET store_schema_version = ?, applied_at = ?",
                    (step.to_version, applied_at),
                )
                connection.execute(
                    """
                    INSERT INTO migration_history (
                        step_id,
                        from_version,
                        to_version,
                        description,
                        status,
                        applied_at,
                        notes_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        step.step_id,
                        step.from_version,
                        step.to_version,
                        step.description,
                        "applied",
                        applied_at,
                        json.dumps({}, sort_keys=True),
                    ),
                )
                connection.commit()
            except Exception as exc:
                connection.rollback()
                failure_notes = {"error_type": type(exc).__name__}
                failed_at = iso_utc_now()
                connection.execute(
                    """
                    INSERT INTO migration_history (
                        step_id,
                        from_version,
                        to_version,
                        description,
                        status,
                        applied_at,
                        notes_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        step.step_id,
                        step.from_version,
                        step.to_version,
                        step.description,
                        "failed",
                        failed_at,
                        json.dumps(failure_notes, sort_keys=True),
                    ),
                )
                raise MigrationError(
                    "Metadata migration step failed.",
                    code="metadata_migration_step_failed",
                    details={"step_id": step.step_id, "from_version": step.from_version, "to_version": step.to_version},
                    cause=exc,
                ) from exc

            history_rows.append(
                MigrationHistoryRow(
                    step_id=step.step_id,
                    from_version=step.from_version,
                    to_version=step.to_version,
                    description=step.description,
                    status="applied",
                    applied_at=applied_at,
                    notes={},
                )
            )
            applied_steps.append(step)
            current_version = step.to_version
    finally:
        connection.close()

    return MigrationResult(
        current_version=plan.current_version,
        target_version=current_version or plan.target_version,
        applied_steps=tuple(applied_steps),
        dry_run=False,
        changed=bool(applied_steps),
        history_rows=tuple(history_rows),
        warnings=warnings,
    )


def _resolve_path(current_version: str, target_version: str) -> tuple[MigrationStep, ...] | None:
    if current_version == target_version:
        return ()

    path: list[MigrationStep] = []
    version = current_version
    visited = {version}
    while version != target_version:
        next_step = None
        for (from_version, _to_version), step in STEP_REGISTRY.items():
            if from_version == version:
                next_step = step
                break
        if next_step is None:
            return None
        path.append(next_step)
        version = next_step.to_version
        if version in visited:
            return None
        visited.add(version)
    return tuple(path)


def _build_plan_warnings(plan: MigrationPlan, *, config: MetadataStoreConfig) -> tuple[str, ...]:
    warnings: list[str] = []
    if config.auto_migrate:
        warnings.append("config_auto_migrate_is_enabled")
    if not plan.steps:
        warnings.append("no_schema_changes_required")
    return tuple(warnings)


__all__ = [
    "STEP_IMPLEMENTATIONS",
    "STEP_REGISTRY",
    "dry_run_migration_for",
    "inspect_schema",
    "migrate_for",
    "plan_migration_for",
]
