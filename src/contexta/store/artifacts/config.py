"""Artifact store-local configuration model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from ...common.errors import ConfigurationError
from ...common.io import resolve_path
from ...config import UnifiedConfig


class IngestMode(str, Enum):
    """Canonical ingest mode for artifact writes."""

    COPY = "copy"
    MOVE = "move"
    ADOPT = "adopt"


class VerificationMode(str, Enum):
    """Canonical verification posture for artifact ingest and checks."""

    NONE = "none"
    STORED = "stored"
    MANIFEST_IF_AVAILABLE = "manifest_if_available"
    STRICT = "strict"


def _normalize_bool(field_name: str, value: bool) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError(
            f"{field_name} must be a bool.",
            code="artifact_store_invalid_config",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    return value


def _normalize_positive_int(field_name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigurationError(
            f"{field_name} must be an integer.",
            code="artifact_store_invalid_config",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    if value <= 0:
        raise ConfigurationError(
            f"{field_name} must be greater than zero.",
            code="artifact_store_invalid_config",
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
        code="artifact_store_invalid_config",
        details={"field_name": "root_path", "type": type(value).__name__},
    )


def _normalize_ingest_mode(value: IngestMode | str) -> IngestMode:
    if isinstance(value, IngestMode):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        for candidate in IngestMode:
            if candidate.value == normalized:
                return candidate
    raise ConfigurationError(
        "Unsupported artifact ingest mode.",
        code="artifact_store_invalid_ingest_mode",
        details={"ingest_mode": value, "allowed": tuple(mode.value for mode in IngestMode)},
    )


def _normalize_verification_mode(value: VerificationMode | str) -> VerificationMode:
    if isinstance(value, VerificationMode):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        for candidate in VerificationMode:
            if candidate.value == normalized:
                return candidate
    raise ConfigurationError(
        "Unsupported artifact verification mode.",
        code="artifact_store_invalid_verification_mode",
        details={"verification_mode": value, "allowed": tuple(mode.value for mode in VerificationMode)},
    )


def _normalize_layout_version(value: str) -> str:
    if not isinstance(value, str):
        raise ConfigurationError(
            "layout_version must be a string.",
            code="artifact_store_invalid_config",
            details={"field_name": "layout_version", "type": type(value).__name__},
        )
    normalized = value.strip()
    if not normalized:
        raise ConfigurationError(
            "layout_version must not be blank.",
            code="artifact_store_invalid_config",
            details={"field_name": "layout_version"},
        )
    return normalized


@dataclass(frozen=True, slots=True)
class VaultConfig:
    """Plane-local config used by ``contexta.store.artifacts``."""

    root_path: Path | None = None
    default_ingest_mode: IngestMode | str = IngestMode.COPY
    verification_mode: VerificationMode | str = VerificationMode.MANIFEST_IF_AVAILABLE
    create_missing_dirs: bool = True
    layout_version: str = "v1"
    chunk_size_bytes: int = 1_048_576
    read_only: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_path", _normalize_root_path(self.root_path))
        object.__setattr__(self, "default_ingest_mode", _normalize_ingest_mode(self.default_ingest_mode))
        object.__setattr__(self, "verification_mode", _normalize_verification_mode(self.verification_mode))
        object.__setattr__(self, "create_missing_dirs", _normalize_bool("create_missing_dirs", self.create_missing_dirs))
        object.__setattr__(self, "layout_version", _normalize_layout_version(self.layout_version))
        object.__setattr__(self, "chunk_size_bytes", _normalize_positive_int("chunk_size_bytes", self.chunk_size_bytes))
        object.__setattr__(self, "read_only", _normalize_bool("read_only", self.read_only))

    @classmethod
    def from_unified_config(cls, config: UnifiedConfig) -> "VaultConfig":
        """Project the global config into artifact-plane local config."""

        return cls(
            root_path=config.artifacts.root_path or config.workspace.artifacts_path,
            default_ingest_mode=config.artifacts.default_ingest_mode,
            verification_mode=config.artifacts.verification_mode,
            create_missing_dirs=config.artifacts.create_missing_dirs,
            layout_version=config.artifacts.layout_version,
            chunk_size_bytes=config.artifacts.chunk_size_bytes,
            read_only=config.artifacts.read_only,
        )

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, Any],
        *,
        base: "VaultConfig | None" = None,
    ) -> "VaultConfig":
        """Build a config from a partial override mapping."""

        seed = base or cls()
        return cls(
            root_path=values.get("root_path", seed.root_path),
            default_ingest_mode=values.get("default_ingest_mode", seed.default_ingest_mode),
            verification_mode=values.get("verification_mode", seed.verification_mode),
            create_missing_dirs=values.get("create_missing_dirs", seed.create_missing_dirs),
            layout_version=values.get("layout_version", seed.layout_version),
            chunk_size_bytes=values.get("chunk_size_bytes", seed.chunk_size_bytes),
            read_only=values.get("read_only", seed.read_only),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a transport-friendly representation."""

        return {
            "root_path": None if self.root_path is None else str(self.root_path),
            "default_ingest_mode": self.default_ingest_mode.value,
            "verification_mode": self.verification_mode.value,
            "create_missing_dirs": self.create_missing_dirs,
            "layout_version": self.layout_version,
            "chunk_size_bytes": self.chunk_size_bytes,
            "read_only": self.read_only,
        }


ArtifactStoreConfig = VaultConfig


__all__ = [
    "ArtifactStoreConfig",
    "IngestMode",
    "VaultConfig",
    "VerificationMode",
]
