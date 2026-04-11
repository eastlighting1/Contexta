"""Metadata store bootstrap and backend connection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Sequence

from ...common.errors import (
    DependencyError,
    NotFoundError,
    ReadOnlyStoreError,
    SchemaVersionError,
    StoreAccessError,
)
from ...common.io import ensure_directory
from ...common.time import iso_utc_now
from .adapters import DuckDBAdapter, PandasAdapter, PolarsAdapter
from .config import MetadataStoreConfig
from .integrity import check_integrity, plan_repairs, preview_repairs
from .migrations import dry_run_migration_for, inspect_schema, migrate_for, plan_migration_for
from .snapshots import build_run_snapshot

if TYPE_CHECKING:
    import duckdb


CURRENT_METADATA_STORE_SCHEMA_VERSION = "1"


def _load_duckdb() -> Any:
    try:
        import duckdb  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise DependencyError(
            "duckdb is required for the metadata store backend.",
            code="metadata_store_backend_missing",
            cause=exc,
        ) from exc
    return duckdb


@dataclass(slots=True)
class DuckDBMetadataBackend:
    """Low-level DuckDB backend for the metadata plane."""

    config: MetadataStoreConfig
    connection: "duckdb.DuckDBPyConnection"

    @classmethod
    def open(cls, config: MetadataStoreConfig) -> "DuckDBMetadataBackend":
        duckdb = _load_duckdb()
        target = config.resolved_database_path()
        if target != ":memory:":
            ensure_directory(Path(target).parent)
        try:
            connection = duckdb.connect(str(target))
        except Exception as exc:  # pragma: no cover
            raise StoreAccessError(
                "Failed to open DuckDB metadata store.",
                code="metadata_store_open_failed",
                details={"database_path": str(target)},
                cause=exc,
            ) from exc
        backend = cls(config=config, connection=connection)
        backend._bootstrap()
        return backend

    def close(self) -> None:
        self.connection.close()

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        return self.connection.execute(sql, params)

    def fetchone(self, sql: str, params: Sequence[Any] = ()) -> tuple[Any, ...] | None:
        return self.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[tuple[Any, ...]]:
        return self.execute(sql, params).fetchall()

    def get_store_schema_version(self) -> str:
        row = self.fetchone("SELECT store_schema_version FROM schema_metadata LIMIT 1")
        if row is None:
            raise SchemaVersionError(
                "schema_metadata row is missing.",
                code="metadata_schema_metadata_missing",
            )
        return str(row[0])

    def upsert_payload_row(
        self,
        table: str,
        *,
        payload_json: str,
        values: dict[str, Any],
    ) -> None:
        columns = list(values.keys()) + ["payload_json"]
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "ref")
        sql = (
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT(ref) DO UPDATE SET {updates}"
        )
        params = [values[column] for column in values] + [payload_json]
        self.execute(sql, params)

    def get_payload_json(self, table: str, ref: str) -> str | None:
        row = self.fetchone(f"SELECT payload_json FROM {table} WHERE ref = ?", (ref,))
        return None if row is None else str(row[0])

    def exists_ref(self, table: str, ref: str) -> bool:
        row = self.fetchone(f"SELECT 1 FROM {table} WHERE ref = ? LIMIT 1", (ref,))
        return row is not None

    def list_payload_json(
        self,
        table: str,
        *,
        where: str = "",
        params: Sequence[Any] = (),
        order_by: str = "ref",
    ) -> tuple[str, ...]:
        sql = f"SELECT payload_json FROM {table}"
        if where:
            sql += f" WHERE {where}"
        sql += f" ORDER BY {order_by}"
        rows = self.fetchall(sql, params)
        return tuple(str(row[0]) for row in rows)

    def register_ref(self, ref: str, *, ref_kind: str, owner_kind: str) -> None:
        sql = """
            INSERT INTO structural_ref_registry (ref, ref_kind, owner_kind, registered_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ref) DO UPDATE SET
                ref_kind = excluded.ref_kind,
                owner_kind = excluded.owner_kind,
                registered_at = excluded.registered_at
        """
        self.execute(sql, (ref, ref_kind, owner_kind, iso_utc_now()))

    def registered_ref_exists(self, ref: str) -> bool:
        return self.exists_ref("structural_ref_registry", ref)

    def list_registered_refs(self) -> tuple[str, ...]:
        rows = self.fetchall("SELECT ref FROM structural_ref_registry ORDER BY ref")
        return tuple(str(row[0]) for row in rows)

    def _bootstrap(self) -> None:
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_metadata (
                store_schema_version TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS migration_history (
                step_id TEXT PRIMARY KEY,
                from_version TEXT NOT NULL,
                to_version TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                notes_json TEXT NOT NULL
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS structural_ref_registry (
                ref TEXT PRIMARY KEY,
                ref_kind TEXT NOT NULL,
                owner_kind TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                ref TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                ref TEXT PRIMARY KEY,
                project_ref TEXT NOT NULL,
                name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS deployment_executions (
                ref TEXT PRIMARY KEY,
                project_ref TEXT NOT NULL,
                deployment_name TEXT NOT NULL,
                run_ref TEXT,
                order_index INTEGER,
                started_at TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS stage_executions (
                ref TEXT PRIMARY KEY,
                run_ref TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                order_index INTEGER,
                started_at TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS batch_executions (
                ref TEXT PRIMARY KEY,
                run_ref TEXT NOT NULL,
                stage_ref TEXT NOT NULL,
                batch_name TEXT NOT NULL,
                order_index INTEGER,
                started_at TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS sample_observations (
                ref TEXT PRIMARY KEY,
                run_ref TEXT NOT NULL,
                stage_ref TEXT NOT NULL,
                batch_ref TEXT,
                sample_name TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                retention_class TEXT,
                redaction_profile TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS environment_snapshots (
                ref TEXT PRIMARY KEY,
                run_ref TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS relations (
                ref TEXT PRIMARY KEY,
                source_ref TEXT NOT NULL,
                target_ref TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS provenance_records (
                ref TEXT PRIMARY KEY,
                relation_ref TEXT NOT NULL,
                asserted_at TEXT NOT NULL,
                assertion_mode TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        row = self.fetchone("SELECT store_schema_version FROM schema_metadata LIMIT 1")
        if row is None:
            self.execute(
                "INSERT INTO schema_metadata (store_schema_version, applied_at) VALUES (?, ?)",
                (CURRENT_METADATA_STORE_SCHEMA_VERSION, iso_utc_now()),
            )
        else:
            current = str(row[0])
            if current != CURRENT_METADATA_STORE_SCHEMA_VERSION:
                raise SchemaVersionError(
                    "Unsupported metadata store schema version.",
                    code="metadata_store_schema_version_unsupported",
                    details={
                        "current_version": current,
                        "supported_version": CURRENT_METADATA_STORE_SCHEMA_VERSION,
                    },
                )


class MetadataStore:
    """Canonical metadata store entrypoint."""

    def __init__(self, config: MetadataStoreConfig | None = None) -> None:
        self.config = config or MetadataStoreConfig()
        self._backend = DuckDBMetadataBackend.open(self.config)
        self._duckdb_adapter = DuckDBAdapter(self._backend)
        self._pandas_adapter = PandasAdapter(self._duckdb_adapter)
        self._polars_adapter = PolarsAdapter(self._duckdb_adapter)

        from .repositories.environments import EnvironmentRepository
        from .repositories.batches import BatchRepository
        from .repositories.deployments import DeploymentRepository
        from .repositories.projects import ProjectRepository
        from .repositories.provenance import ProvenanceRepository
        from .repositories.relations import RelationRepository
        from .repositories.runs import RunRepository
        from .repositories.samples import SampleRepository
        from .repositories.stages import StageRepository

        self.projects = ProjectRepository(self)
        self.runs = RunRepository(self)
        self.deployments = DeploymentRepository(self)
        self.stages = StageRepository(self)
        self.batches = BatchRepository(self)
        self.samples = SampleRepository(self)
        self.environments = EnvironmentRepository(self)
        self.relations = RelationRepository(self)
        self.provenance = ProvenanceRepository(self)

    @property
    def duckdb(self) -> Any:
        return self._duckdb_adapter

    @property
    def pandas(self) -> Any:
        return self._pandas_adapter

    @property
    def polars(self) -> Any:
        return self._polars_adapter

    @classmethod
    def inspect_schema(
        cls,
        config: MetadataStoreConfig | None = None,
        *,
        target_version: str | None = None,
    ) -> Any:
        return inspect_schema(config or MetadataStoreConfig(), target_version=target_version)

    @classmethod
    def plan_migration_for(
        cls,
        config: MetadataStoreConfig | None = None,
        *,
        target_version: str | None = None,
    ) -> Any:
        return plan_migration_for(config or MetadataStoreConfig(), target_version=target_version)

    @classmethod
    def dry_run_migration_for(
        cls,
        config: MetadataStoreConfig | None = None,
        *,
        target_version: str | None = None,
    ) -> Any:
        return dry_run_migration_for(config or MetadataStoreConfig(), target_version=target_version)

    @classmethod
    def migrate_for(
        cls,
        config: MetadataStoreConfig | None = None,
        *,
        target_version: str | None = None,
    ) -> Any:
        return migrate_for(config or MetadataStoreConfig(), target_version=target_version)

    def get_store_schema_version(self) -> str:
        return self._backend.get_store_schema_version()

    def list_registered_refs(self) -> tuple[str, ...]:
        return self._backend.list_registered_refs()

    def check_integrity(self, *, full: bool = True) -> Any:
        return check_integrity(self, full=full)

    def plan_repairs(self, report: Any | None = None) -> Any:
        report = report or self.check_integrity(full=True)
        return plan_repairs(report)

    def preview_repairs(self, plan: Any | None = None) -> Any:
        plan = plan or self.plan_repairs()
        return preview_repairs(plan)

    def plan_migration(self, *, target_version: str | None = None) -> Any:
        return plan_migration_for(self.config, target_version=target_version)

    def dry_run_migration(self, *, target_version: str | None = None) -> Any:
        return dry_run_migration_for(self.config, target_version=target_version)

    def migrate(self, *, target_version: str | None = None) -> Any:
        return migrate_for(self.config, target_version=target_version)

    def build_run_snapshot(self, run_ref: str) -> Any:
        return build_run_snapshot(self, run_ref)

    def close(self) -> None:
        self._backend.close()

    def __enter__(self) -> "MetadataStore":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> bool:
        self.close()
        return False

    def _ensure_writable(self) -> None:
        if self.config.read_only:
            raise ReadOnlyStoreError(
                "Metadata store is read-only.",
                code="metadata_store_read_only",
            )

    def _require_registered_or_persisted_ref(self, ref: str) -> None:
        if self._backend.registered_ref_exists(ref):
            return
        tables = (
            "projects",
            "runs",
            "deployment_executions",
            "stage_executions",
            "batch_executions",
            "sample_observations",
            "environment_snapshots",
            "relations",
            "provenance_records",
        )
        if any(self._backend.exists_ref(table, ref) for table in tables):
            return
        raise NotFoundError(
            "Referenced structural ref does not exist.",
            code="metadata_ref_not_found",
            details={"ref": ref},
        )

    def _register_refs(self, refs: Iterable[tuple[str, str, str]]) -> None:
        for ref, ref_kind, owner_kind in refs:
            self._backend.register_ref(ref, ref_kind=ref_kind, owner_kind=owner_kind)


__all__ = [
    "CURRENT_METADATA_STORE_SCHEMA_VERSION",
    "DuckDBMetadataBackend",
    "MetadataStore",
]
