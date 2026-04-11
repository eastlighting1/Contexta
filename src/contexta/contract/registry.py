"""Extension namespace registry for Contexta contract models."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence
import re

from ..common.errors import ConflictError, NotFoundError, ValidationError
from .extensions import ExtensionFieldSet, validate_extension_field_key, validate_extension_namespace


EXTENSION_OWNERSHIP_CLASSES = ("core", "compat", "adapter", "bridge", "plugin", "private")
EXTENSION_TARGET_MODELS = (
    "project",
    "run",
    "deployment_execution",
    "stage_execution",
    "batch_execution",
    "sample_observation",
    "operation_context",
    "environment_snapshot",
    "record_envelope",
    "event_payload",
    "metric_payload",
    "trace_span_payload",
    "degraded_payload",
    "artifact_manifest",
    "lineage_edge",
    "provenance_record",
)
RESERVED_NAMESPACE_SEGMENTS = {"contexta", "compat", "adapter", "bridge", "plugin"}
REGISTRY_STATUS_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
OWNER_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


def _raise_registry_error(
    message: str,
    *,
    code: str,
    details: Mapping[str, Any] | None = None,
) -> None:
    raise ValidationError(message, code=code, details=details)


def _validate_ownership(namespace: str, ownership_class: str) -> str:
    if ownership_class not in EXTENSION_OWNERSHIP_CLASSES:
        _raise_registry_error(
            f"Invalid extension ownership_class: {ownership_class!r}",
            code="extension_registry_invalid_ownership",
            details={"ownership_class": ownership_class, "allowed": EXTENSION_OWNERSHIP_CLASSES},
        )

    first_segment = namespace.split(".", 1)[0]
    if ownership_class == "core" and not namespace.startswith("contexta."):
        _raise_registry_error("core namespace must start with 'contexta.'.", code="extension_registry_invalid_namespace")
    if ownership_class == "compat" and not namespace.startswith("compat."):
        _raise_registry_error("compat namespace must start with 'compat.'.", code="extension_registry_invalid_namespace")
    if ownership_class == "adapter" and not namespace.startswith("adapter."):
        _raise_registry_error("adapter namespace must start with 'adapter.'.", code="extension_registry_invalid_namespace")
    if ownership_class == "bridge" and not namespace.startswith("bridge."):
        _raise_registry_error("bridge namespace must start with 'bridge.'.", code="extension_registry_invalid_namespace")
    if ownership_class == "plugin" and not namespace.startswith("plugin."):
        _raise_registry_error("plugin namespace must start with 'plugin.'.", code="extension_registry_invalid_namespace")
    if ownership_class == "private" and first_segment in RESERVED_NAMESPACE_SEGMENTS:
        _raise_registry_error(
            "private namespace must not use a reserved first segment.",
            code="extension_registry_invalid_namespace",
            details={"namespace": namespace, "reserved": sorted(RESERVED_NAMESPACE_SEGMENTS)},
        )
    return ownership_class


def _normalize_target_models(target_models: Sequence[str]) -> tuple[str, ...]:
    if not target_models:
        _raise_registry_error(
            "ExtensionRegistryEntry.target_models must not be empty.",
            code="extension_registry_invalid_target_models",
        )
    normalized = tuple(sorted({str(model) for model in target_models}))
    invalid = sorted(set(normalized) - set(EXTENSION_TARGET_MODELS))
    if invalid:
        _raise_registry_error(
            "ExtensionRegistryEntry.target_models contains unknown values.",
            code="extension_registry_invalid_target_models",
            details={"invalid": invalid, "allowed": EXTENSION_TARGET_MODELS},
        )
    return normalized


def _normalize_readonly_fields(
    readonly_fields: Sequence[str],
    *,
    field_specs: Mapping[str, str] | None,
) -> tuple[str, ...]:
    normalized = tuple(sorted({validate_extension_field_key(field) for field in readonly_fields}))
    if field_specs is not None:
        unknown = sorted(set(normalized) - set(field_specs))
        if unknown:
            _raise_registry_error(
                "Registry readonly_fields must be declared in field_specs.",
                code="extension_registry_invalid_readonly_fields",
                details={"unknown_fields": unknown},
            )
    return normalized


def _normalize_field_specs(field_specs: Mapping[str, str] | None) -> Mapping[str, str] | None:
    if field_specs is None:
        return None
    if not isinstance(field_specs, Mapping):
        _raise_registry_error(
            "ExtensionRegistryEntry.field_specs must be a mapping.",
            code="extension_registry_invalid_field_specs",
        )
    normalized: dict[str, str] = {}
    for key in sorted(field_specs):
        validate_extension_field_key(key)
        value = field_specs[key]
        if not isinstance(value, str) or not value.strip():
            _raise_registry_error(
                "ExtensionRegistryEntry.field_specs values must be non-blank strings.",
                code="extension_registry_invalid_field_specs",
                details={"field": key},
            )
        normalized[key] = value.strip()
    return MappingProxyType(normalized)


@dataclass(frozen=True, slots=True)
class ExtensionRegistryEntry:
    """A registered extension namespace."""

    namespace: str
    ownership_class: str
    owner_slug: str
    status: str
    target_models: tuple[str, ...]
    readonly_fields: tuple[str, ...] = ()
    field_specs: Mapping[str, str] | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        namespace = validate_extension_namespace(self.namespace)
        ownership_class = _validate_ownership(namespace, self.ownership_class)

        if not isinstance(self.owner_slug, str) or not OWNER_SLUG_PATTERN.fullmatch(self.owner_slug):
            _raise_registry_error(
                f"Invalid owner_slug: {self.owner_slug!r}",
                code="extension_registry_invalid_owner",
                details={"owner_slug": self.owner_slug},
            )
        if not isinstance(self.status, str) or not REGISTRY_STATUS_PATTERN.fullmatch(self.status):
            _raise_registry_error(
                f"Invalid registry status: {self.status!r}",
                code="extension_registry_invalid_status",
                details={"status": self.status},
            )

        field_specs = _normalize_field_specs(self.field_specs)
        readonly_fields = _normalize_readonly_fields(self.readonly_fields, field_specs=field_specs)
        target_models = _normalize_target_models(self.target_models)
        notes = None if self.notes is None else self.notes.strip() or None

        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "ownership_class", ownership_class)
        object.__setattr__(self, "field_specs", field_specs)
        object.__setattr__(self, "readonly_fields", readonly_fields)
        object.__setattr__(self, "target_models", target_models)
        object.__setattr__(self, "notes", notes)

    def allows_target_model(self, target_model: str) -> bool:
        """Return whether this entry can be used on the given model."""

        return target_model in self.target_models

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic transport representation."""

        payload: dict[str, Any] = {
            "namespace": self.namespace,
            "ownership_class": self.ownership_class,
            "owner_slug": self.owner_slug,
            "status": self.status,
            "target_models": list(self.target_models),
            "readonly_fields": list(self.readonly_fields),
        }
        if self.field_specs is not None:
            payload["field_specs"] = dict(self.field_specs)
        if self.notes is not None:
            payload["notes"] = self.notes
        return payload


@dataclass(frozen=True, slots=True)
class ExtensionRegistry:
    """Registry of extension namespaces and allowed target models."""

    entries: tuple[ExtensionRegistryEntry, ...] = ()

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.entries, key=lambda entry: entry.namespace))
        seen: set[str] = set()
        for entry in ordered:
            if entry.namespace in seen:
                raise ConflictError(
                    "Duplicate extension namespace registration.",
                    code="extension_registry_duplicate_namespace",
                    details={"namespace": entry.namespace},
                )
            seen.add(entry.namespace)
        object.__setattr__(self, "entries", ordered)

    def get_entry(self, namespace: str) -> ExtensionRegistryEntry | None:
        """Return an entry when registered."""

        normalized = validate_extension_namespace(namespace)
        for entry in self.entries:
            if entry.namespace == normalized:
                return entry
        return None

    def require_entry(self, namespace: str) -> ExtensionRegistryEntry:
        """Return an entry or raise when the namespace is unknown."""

        entry = self.get_entry(namespace)
        if entry is None:
            raise NotFoundError(
                f"Extension namespace is not registered: {namespace}",
                code="extension_registry_missing_namespace",
                details={"namespace": namespace},
            )
        return entry

    def register(self, entry: ExtensionRegistryEntry) -> "ExtensionRegistry":
        """Return a new registry with one additional entry."""

        if self.get_entry(entry.namespace) is not None:
            raise ConflictError(
                "Duplicate extension namespace registration.",
                code="extension_registry_duplicate_namespace",
                details={"namespace": entry.namespace},
            )
        return ExtensionRegistry(entries=self.entries + (entry,))

    def owner_for(self, namespace: str) -> str | None:
        """Return the owner slug for a namespace."""

        entry = self.get_entry(namespace)
        return None if entry is None else entry.owner_slug

    def allows_target_model(self, namespace: str, target_model: str) -> bool:
        """Return whether a namespace is registered for the given model."""

        entry = self.get_entry(namespace)
        return False if entry is None else entry.allows_target_model(target_model)

    def resolve_extension(
        self,
        extension: ExtensionFieldSet,
        *,
        target_model: str,
    ) -> ExtensionFieldSet:
        """Validate registry membership and apply registry readonly fields."""

        if target_model not in EXTENSION_TARGET_MODELS:
            _raise_registry_error(
                f"Unknown extension target model: {target_model!r}",
                code="extension_registry_invalid_target_models",
                details={"target_model": target_model, "allowed": EXTENSION_TARGET_MODELS},
            )

        entry = self.require_entry(extension.namespace)
        if not entry.allows_target_model(target_model):
            _raise_registry_error(
                "Extension namespace is not allowed on the target model.",
                code="extension_registry_target_model_mismatch",
                details={"namespace": extension.namespace, "target_model": target_model},
            )
        return extension.with_additional_readonly_fields(entry.readonly_fields)

    def normalize_extensions(
        self,
        extensions: Sequence[ExtensionFieldSet],
        *,
        target_model: str,
    ) -> tuple[ExtensionFieldSet, ...]:
        """Validate and canonicalize a collection of extensions for one model."""

        seen: set[str] = set()
        normalized: list[ExtensionFieldSet] = []
        for extension in sorted(extensions, key=lambda item: item.namespace):
            if extension.namespace in seen:
                raise ConflictError(
                    "Duplicate extension namespace on one object.",
                    code="extension_duplicate_namespace",
                    details={"namespace": extension.namespace, "target_model": target_model},
                )
            seen.add(extension.namespace)
            normalized.append(self.resolve_extension(extension, target_model=target_model))
        return tuple(normalized)


__all__ = [
    "EXTENSION_OWNERSHIP_CLASSES",
    "EXTENSION_TARGET_MODELS",
    "ExtensionRegistry",
    "ExtensionRegistryEntry",
    "OWNER_SLUG_PATTERN",
    "REGISTRY_STATUS_PATTERN",
    "RESERVED_NAMESPACE_SEGMENTS",
]
