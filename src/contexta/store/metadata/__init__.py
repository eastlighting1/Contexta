"""Metadata truth-plane package for Contexta."""

from .adapters import DuckDBAdapter, FrameAdapterProtocol, PandasAdapter, PolarsAdapter
from .config import MetadataStoreConfig
from .integrity import (
    IntegrityIssue,
    IntegrityReport,
    RepairCandidate,
    RepairPlan,
    RepairPreview,
    check_integrity,
    plan_repairs,
    preview_repairs,
)
from .migrations import (
    MigrationHistoryRow,
    MigrationPlan,
    MigrationResult,
    MigrationStep,
    SchemaInspection,
    dry_run_migration_for,
    inspect_schema,
    migrate_for,
    plan_migration_for,
)
from .snapshots import RunSnapshot, build_run_snapshot
from .store import CURRENT_METADATA_STORE_SCHEMA_VERSION, MetadataStore

__all__ = [
    "CURRENT_METADATA_STORE_SCHEMA_VERSION",
    "DuckDBAdapter",
    "FrameAdapterProtocol",
    "IntegrityIssue",
    "IntegrityReport",
    "MetadataStore",
    "MetadataStoreConfig",
    "MigrationHistoryRow",
    "MigrationPlan",
    "MigrationResult",
    "MigrationStep",
    "PandasAdapter",
    "PolarsAdapter",
    "RepairCandidate",
    "RepairPlan",
    "RepairPreview",
    "RunSnapshot",
    "SchemaInspection",
    "build_run_snapshot",
    "check_integrity",
    "dry_run_migration_for",
    "inspect_schema",
    "migrate_for",
    "plan_migration_for",
    "plan_repairs",
    "preview_repairs",
]
