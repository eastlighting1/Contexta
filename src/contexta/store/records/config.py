"""Record store-local configuration model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from ...common.errors import ConfigurationError
from ...common.io import resolve_path
from ...config import UnifiedConfig


class DurabilityMode(str, Enum):
    """Canonical durability boundary for record writes."""

    FLUSH = "flush"
    FSYNC = "fsync"


class LayoutMode(str, Enum):
    """Canonical physical layout mode for the record truth plane."""

    JSONL_SEGMENTS = "jsonl_segments"


def _normalize_bool(field_name: str, value: bool) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError(
            f"{field_name} must be a bool.",
            code="record_store_invalid_config",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    return value


def _normalize_positive_int(field_name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigurationError(
            f"{field_name} must be an integer.",
            code="record_store_invalid_config",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    if value <= 0:
        raise ConfigurationError(
            f"{field_name} must be greater than zero.",
            code="record_store_invalid_config",
            details={"field_name": field_name, "value": value},
        )
    return value


def _normalize_root_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    if isinstance(value, (str, Path)):
        return resolve_path(value)
    raise ConfigurationError(
        "root_path must be None or a filesystem path.",
        code="record_store_invalid_config",
        details={"field_name": "root_path", "type": type(value).__name__},
    )


def _normalize_durability_mode(value: DurabilityMode | str) -> DurabilityMode:
    if isinstance(value, DurabilityMode):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        for candidate in DurabilityMode:
            if candidate.value == normalized:
                return candidate
    raise ConfigurationError(
        "Unsupported record durability mode.",
        code="record_store_invalid_durability_mode",
        details={"durability_mode": value, "allowed": tuple(mode.value for mode in DurabilityMode)},
    )


def _normalize_layout_mode(value: LayoutMode | str) -> LayoutMode:
    if isinstance(value, LayoutMode):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        for candidate in LayoutMode:
            if candidate.value == normalized:
                return candidate
    raise ConfigurationError(
        "Unsupported record layout mode.",
        code="record_store_invalid_layout_mode",
        details={"layout_mode": value, "allowed": tuple(mode.value for mode in LayoutMode)},
    )


def _normalize_layout_version(value: str) -> str:
    if not isinstance(value, str):
        raise ConfigurationError(
            "layout_version must be a string.",
            code="record_store_invalid_config",
            details={"field_name": "layout_version", "type": type(value).__name__},
        )
    normalized = value.strip()
    if not normalized:
        raise ConfigurationError(
            "layout_version must not be blank.",
            code="record_store_invalid_config",
            details={"field_name": "layout_version"},
        )
    return normalized


@dataclass(frozen=True, slots=True)
class StoreConfig:
    """Plane-local config used by ``contexta.store.records``."""

    root_path: Path | None = None
    max_segment_bytes: int = 1_048_576
    durability_mode: DurabilityMode | str = DurabilityMode.FSYNC
    layout_mode: LayoutMode | str = LayoutMode.JSONL_SEGMENTS
    layout_version: str = "1"
    enable_indexes: bool = True
    read_only: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_path", _normalize_root_path(self.root_path))
        object.__setattr__(self, "max_segment_bytes", _normalize_positive_int("max_segment_bytes", self.max_segment_bytes))
        object.__setattr__(self, "durability_mode", _normalize_durability_mode(self.durability_mode))
        object.__setattr__(self, "layout_mode", _normalize_layout_mode(self.layout_mode))
        object.__setattr__(self, "layout_version", _normalize_layout_version(self.layout_version))
        object.__setattr__(self, "enable_indexes", _normalize_bool("enable_indexes", self.enable_indexes))
        object.__setattr__(self, "read_only", _normalize_bool("read_only", self.read_only))

    @classmethod
    def from_unified_config(cls, config: UnifiedConfig) -> "StoreConfig":
        """Project the global config into record-plane local config."""

        return cls(
            root_path=config.records.root_path or config.workspace.records_path,
            max_segment_bytes=config.records.max_segment_bytes,
            durability_mode=config.records.durability_mode,
            layout_mode=config.records.layout_mode,
            layout_version=config.records.layout_version,
            enable_indexes=config.records.enable_indexes,
            read_only=config.records.read_only,
        )

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, Any],
        *,
        base: "StoreConfig | None" = None,
    ) -> "StoreConfig":
        """Build a config from a partial override mapping."""

        seed = base or cls()
        return cls(
            root_path=values.get("root_path", seed.root_path),
            max_segment_bytes=values.get("max_segment_bytes", seed.max_segment_bytes),
            durability_mode=values.get("durability_mode", seed.durability_mode),
            layout_mode=values.get("layout_mode", seed.layout_mode),
            layout_version=values.get("layout_version", seed.layout_version),
            enable_indexes=values.get("enable_indexes", seed.enable_indexes),
            read_only=values.get("read_only", seed.read_only),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a transport-friendly representation."""

        root_path: str | None
        if self.root_path is None:
            root_path = None
        else:
            root_path = str(self.root_path)
        return {
            "root_path": root_path,
            "max_segment_bytes": self.max_segment_bytes,
            "durability_mode": self.durability_mode.value,
            "layout_mode": self.layout_mode.value,
            "layout_version": self.layout_version,
            "enable_indexes": self.enable_indexes,
            "read_only": self.read_only,
        }


RecordStoreConfig = StoreConfig


__all__ = ["DurabilityMode", "LayoutMode", "RecordStoreConfig", "StoreConfig"]
