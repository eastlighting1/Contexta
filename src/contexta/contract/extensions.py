"""Namespaced extension field sets for Contexta contract models."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping, Sequence
import re

from ..common.errors import ConflictError, ValidationError


EXTENSION_NAMESPACE_PATTERN = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+$")
EXTENSION_NAMESPACE_SEGMENT_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
EXTENSION_FIELD_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
MAX_EXTENSION_NAMESPACE_LENGTH = 128


def _raise_extension_error(
    message: str,
    *,
    code: str,
    details: Mapping[str, Any] | None = None,
) -> None:
    raise ValidationError(message, code=code, details=details)


def validate_extension_namespace(namespace: str) -> str:
    """Validate namespace grammar."""

    if not isinstance(namespace, str):
        _raise_extension_error("Extension namespace must be a string.", code="extension_invalid_namespace")
    if not namespace or namespace != namespace.strip():
        _raise_extension_error("Extension namespace must not be blank.", code="extension_invalid_namespace")
    if len(namespace) > MAX_EXTENSION_NAMESPACE_LENGTH:
        _raise_extension_error(
            "Extension namespace is too long.",
            code="extension_invalid_namespace",
            details={"namespace": namespace, "max_length": MAX_EXTENSION_NAMESPACE_LENGTH},
        )
    if not EXTENSION_NAMESPACE_PATTERN.fullmatch(namespace):
        _raise_extension_error(
            f"Invalid extension namespace: {namespace!r}",
            code="extension_invalid_namespace",
            details={"namespace": namespace},
        )
    return namespace


def validate_extension_field_key(field_key: str) -> str:
    """Validate an extension field key."""

    if not isinstance(field_key, str):
        _raise_extension_error("Extension field key must be a string.", code="extension_invalid_field_key")
    if not EXTENSION_FIELD_KEY_PATTERN.fullmatch(field_key):
        _raise_extension_error(
            f"Invalid extension field key: {field_key!r}",
            code="extension_invalid_field_key",
            details={"field_key": field_key},
        )
    return field_key


def _freeze_json_value(value: Any, *, path: str) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _raise_extension_error(
                f"Non-finite float is not allowed at {path}.",
                code="extension_invalid_value",
                details={"path": path, "value": value},
            )
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                _raise_extension_error(
                    f"Extension object key at {path} must be a string.",
                    code="extension_invalid_value",
                    details={"path": path, "key": key},
                )
            normalized[key] = _freeze_json_value(value[key], path=f"{path}.{key}")
        return MappingProxyType(normalized)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_freeze_json_value(item, path=f"{path}[{index}]") for index, item in enumerate(value))
    _raise_extension_error(
        f"Unsupported extension value at {path}.",
        code="extension_invalid_value",
        details={"path": path, "type": type(value).__name__},
    )


def _thaw_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json_value(item) for item in value]
    return value


def _normalize_fields(fields: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(fields, Mapping):
        _raise_extension_error("Extension fields must be a mapping.", code="extension_invalid_fields")
    if not fields:
        _raise_extension_error("Extension fields must not be empty.", code="extension_empty_fields")

    normalized: dict[str, Any] = {}
    for key in sorted(fields):
        validate_extension_field_key(key)
        normalized[key] = _freeze_json_value(fields[key], path=key)
    return MappingProxyType(normalized)


def _normalize_readonly_fields(
    readonly_fields: Sequence[str],
    *,
    field_names: Sequence[str],
) -> tuple[str, ...]:
    normalized = tuple(sorted({validate_extension_field_key(name) for name in readonly_fields}))
    unknown = sorted(set(normalized) - set(field_names))
    if unknown:
        _raise_extension_error(
            "readonly_fields must be a subset of fields.",
            code="extension_invalid_readonly_fields",
            details={"unknown_fields": unknown},
        )
    return normalized


@dataclass(frozen=True, slots=True)
class ExtensionFieldSet:
    """Namespaced extension data attached to a canonical model."""

    namespace: str
    fields: Mapping[str, Any]
    readonly_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        namespace = validate_extension_namespace(self.namespace)
        fields = _normalize_fields(self.fields)
        readonly_fields = _normalize_readonly_fields(self.readonly_fields, field_names=tuple(fields.keys()))
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "fields", fields)
        object.__setattr__(self, "readonly_fields", readonly_fields)

    def get(self, field_key: str, default: Any = None) -> Any:
        """Return a thawed field value."""

        if field_key not in self.fields:
            return default
        return _thaw_json_value(self.fields[field_key])

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly transport representation."""

        return {
            "namespace": self.namespace,
            "fields": {key: _thaw_json_value(value) for key, value in self.fields.items()},
            "readonly_fields": list(self.readonly_fields),
        }

    def with_additional_readonly_fields(self, field_names: Sequence[str]) -> "ExtensionFieldSet":
        """Return a copy with additional readonly fields applied."""

        merged = tuple(sorted(set(self.readonly_fields) | set(field_names)))
        return ExtensionFieldSet(namespace=self.namespace, fields=self.fields, readonly_fields=merged)

    def merge_fields(
        self,
        updates: Mapping[str, Any],
        *,
        allow_readonly: bool = False,
        additional_readonly_fields: Sequence[str] = (),
    ) -> "ExtensionFieldSet":
        """Merge field updates while respecting readonly constraints."""

        update_keys = {validate_extension_field_key(key) for key in updates}
        blocked = sorted(update_keys & set(self.readonly_fields))
        if blocked and not allow_readonly:
            raise ConflictError(
                "Cannot overwrite readonly extension fields.",
                code="extension_readonly_conflict",
                details={"namespace": self.namespace, "fields": blocked},
            )

        merged_fields = {key: _thaw_json_value(value) for key, value in self.fields.items()}
        for key, value in updates.items():
            merged_fields[key] = value
        readonly_fields = tuple(sorted(set(self.readonly_fields) | set(additional_readonly_fields)))
        return ExtensionFieldSet(
            namespace=self.namespace,
            fields=merged_fields,
            readonly_fields=readonly_fields,
        )

    def without_fields(
        self,
        field_names: Sequence[str],
        *,
        allow_readonly: bool = False,
    ) -> "ExtensionFieldSet":
        """Drop fields while respecting readonly constraints."""

        normalized = {validate_extension_field_key(name) for name in field_names}
        blocked = sorted(normalized & set(self.readonly_fields))
        if blocked and not allow_readonly:
            raise ConflictError(
                "Cannot remove readonly extension fields.",
                code="extension_readonly_conflict",
                details={"namespace": self.namespace, "fields": blocked},
            )

        remaining = {
            key: _thaw_json_value(value)
            for key, value in self.fields.items()
            if key not in normalized
        }
        readonly = tuple(sorted(set(self.readonly_fields) - normalized))
        return ExtensionFieldSet(namespace=self.namespace, fields=remaining, readonly_fields=readonly)


__all__ = [
    "EXTENSION_FIELD_KEY_PATTERN",
    "EXTENSION_NAMESPACE_PATTERN",
    "EXTENSION_NAMESPACE_SEGMENT_PATTERN",
    "ExtensionFieldSet",
    "MAX_EXTENSION_NAMESPACE_LENGTH",
    "validate_extension_field_key",
    "validate_extension_namespace",
]
