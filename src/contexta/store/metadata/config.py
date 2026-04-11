"""Metadata store-local configuration model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ...common.errors import ConfigurationError
from ...common.io import resolve_path
from ...config import UnifiedConfig


def _normalize_adapter(value: str) -> str:
    if not isinstance(value, str):
        raise ConfigurationError(
            "storage_adapter must be a string.",
            code="metadata_store_invalid_config",
            details={"field_name": "storage_adapter", "type": type(value).__name__},
        )
    text = value.strip().lower()
    if text not in {"duckdb"}:
        raise ConfigurationError(
            "Unsupported metadata storage adapter.",
            code="metadata_store_invalid_adapter",
            details={"storage_adapter": value, "allowed": ("duckdb",)},
        )
    return text


def _normalize_bool(field_name: str, value: bool) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError(
            f"{field_name} must be a bool.",
            code="metadata_store_invalid_config",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    return value


def _normalize_database_path(value: str | Path | None) -> str | Path | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == ":memory:":
        return ":memory:"
    if isinstance(value, (str, Path)):
        return resolve_path(value)
    raise ConfigurationError(
        "database_path must be None, ':memory:', or a filesystem path.",
        code="metadata_store_invalid_config",
        details={"field_name": "database_path", "type": type(value).__name__},
    )


@dataclass(frozen=True, slots=True)
class MetadataStoreConfig:
    """Plane-local config used by ``contexta.store.metadata``."""

    storage_adapter: str = "duckdb"
    database_path: str | Path | None = None
    auto_create: bool = True
    read_only: bool = False
    auto_migrate: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "storage_adapter", _normalize_adapter(self.storage_adapter))
        object.__setattr__(self, "database_path", _normalize_database_path(self.database_path))
        object.__setattr__(self, "auto_create", _normalize_bool("auto_create", self.auto_create))
        object.__setattr__(self, "read_only", _normalize_bool("read_only", self.read_only))
        object.__setattr__(self, "auto_migrate", _normalize_bool("auto_migrate", self.auto_migrate))

    @classmethod
    def from_unified_config(cls, config: UnifiedConfig) -> "MetadataStoreConfig":
        """Project the global config into metadata-plane local config."""

        return cls(
            storage_adapter=config.metadata.storage_adapter,
            database_path=config.metadata.database_path or (config.workspace.metadata_path / "ledger.db"),
            auto_create=config.metadata.auto_create,
            read_only=config.metadata.read_only,
            auto_migrate=config.metadata.auto_migrate,
        )

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, Any],
        *,
        base: "MetadataStoreConfig | None" = None,
    ) -> "MetadataStoreConfig":
        """Build a config from a partial override mapping."""

        seed = base or cls()
        return cls(
            storage_adapter=values.get("storage_adapter", seed.storage_adapter),
            database_path=values.get("database_path", seed.database_path),
            auto_create=values.get("auto_create", seed.auto_create),
            read_only=values.get("read_only", seed.read_only),
            auto_migrate=values.get("auto_migrate", seed.auto_migrate),
        )

    @property
    def backend(self) -> str:
        """Return the canonical backend identifier."""

        return self.storage_adapter

    @property
    def in_memory(self) -> bool:
        """Return whether this config targets an in-memory database."""

        return self.database_path == ":memory:"

    def resolved_database_path(self) -> str | Path:
        """Return the concrete database target for store bootstrap."""

        if self.database_path is None:
            raise ConfigurationError(
                "MetadataStoreConfig requires a concrete database_path before store bootstrap.",
                code="metadata_store_missing_database_path",
            )
        return self.database_path

    def to_dict(self) -> dict[str, Any]:
        """Return a transport-friendly representation."""

        database_path = self.database_path
        if isinstance(database_path, Path):
            database_path = str(database_path)
        return {
            "storage_adapter": self.storage_adapter,
            "database_path": database_path,
            "auto_create": self.auto_create,
            "read_only": self.read_only,
            "auto_migrate": self.auto_migrate,
        }


__all__ = ["MetadataStoreConfig"]
