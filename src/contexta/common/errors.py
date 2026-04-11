"""Shared exception bases for Contexta."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping


def _freeze_details(details: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    """Return a stable read-only mapping for exception details."""
    if not details:
        return None
    return MappingProxyType({key: details[key] for key in sorted(details)})


class ContextaError(Exception):
    """Broad catch base exception for the public Contexta surface."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "contexta_error",
        details: Mapping[str, Any] | None = None,
        retryable: bool = False,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = _freeze_details(details)
        self.retryable = retryable
        self.cause = cause
        if cause is not None:
            self.__cause__ = cause

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Return a stable payload for surface translation."""
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details) if self.details is not None else None,
            "retryable": self.retryable,
        }


class ConfigurationError(ContextaError):
    """Raised for configuration resolution or validation failures."""


class ContractError(ContextaError):
    """Raised for canonical contract failures."""


class CaptureError(ContextaError):
    """Raised for capture/runtime failures."""


class MetadataError(ContextaError):
    """Raised for metadata truth-plane failures."""


class RecordError(ContextaError):
    """Raised for record truth-plane failures."""


class ArtifactError(ContextaError):
    """Raised for artifact truth-plane failures."""


class InterpretationError(ContextaError):
    """Raised for interpretation/query failures."""


class RecoveryError(ContextaError):
    """Raised for recovery orchestration failures."""


class SurfaceError(ContextaError):
    """Raised for delivery surface failures."""


class ValidationError(ContextaError):
    """Raised when canonical validation fails."""


class SerializationError(ContextaError):
    """Raised when serialization or deserialization fails."""


class CompatibilityError(ContextaError):
    """Raised when compatibility bridging fails."""


class LifecycleError(ContextaError):
    """Raised when lifecycle transitions are invalid."""


class ClosedScopeError(ContextaError):
    """Raised when a closed scope is used again."""


class DispatchError(ContextaError):
    """Raised for dispatch or fan-out failures."""


class ConflictError(ContextaError):
    """Raised when identities or policies conflict."""


class NotFoundError(ContextaError):
    """Raised when a requested resource is absent."""


class StoreAccessError(ContextaError):
    """Raised for backend or filesystem access failures."""


class ReadOnlyStoreError(ContextaError):
    """Raised when a mutating store operation is attempted in read-only mode."""


class IntegrityError(ContextaError):
    """Raised for integrity failures."""


class SchemaVersionError(ContextaError):
    """Raised when a schema version is unsupported."""


class MigrationError(ContextaError):
    """Raised for migration or upgrade failures."""


class RenderingError(ContextaError):
    """Raised for CLI/HTTP/HTML/notebook rendering failures."""


class DependencyError(ContextaError):
    """Raised when an optional dependency or environment component is missing."""


__all__ = [
    "ArtifactError",
    "CaptureError",
    "CompatibilityError",
    "ConfigurationError",
    "ConflictError",
    "ClosedScopeError",
    "ContextaError",
    "ContractError",
    "DependencyError",
    "DispatchError",
    "IntegrityError",
    "InterpretationError",
    "LifecycleError",
    "MetadataError",
    "MigrationError",
    "NotFoundError",
    "ReadOnlyStoreError",
    "RecordError",
    "RecoveryError",
    "RenderingError",
    "SchemaVersionError",
    "SerializationError",
    "StoreAccessError",
    "SurfaceError",
    "ValidationError",
]
