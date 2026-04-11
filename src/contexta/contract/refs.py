"""Canonical StableRef helpers for Contexta contract models."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence

from ..common.errors import ValidationError


MAX_STABLE_REF_TEXT_LENGTH = 255
MAX_STABLE_REF_COMPONENT_LENGTH = 63
STABLE_REF_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
STABLE_REF_COMPONENT_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CORE_STABLE_REF_KINDS = ("project", "run", "deployment", "stage", "batch", "sample", "op", "record", "artifact")
CORE_STABLE_REF_COMPONENT_COUNTS: Mapping[str, int] = {
    "project": 1,
    "run": 2,
    "deployment": 2,
    "stage": 3,
    "batch": 4,
    "sample": 4,
    "op": 4,
    "record": 3,
    "artifact": 3,
}
STABLE_REF_FIELD_KIND_MAP: Mapping[str, str | tuple[str, ...]] = {
    "project_ref": "project",
    "run_ref": "run",
    "deployment_execution_ref": "deployment",
    "stage_execution_ref": "stage",
    "batch_execution_ref": "batch",
    "sample_observation_ref": "sample",
    "operation_context_ref": "op",
    "record_ref": "record",
    "artifact_ref": "artifact",
    "subject_ref": CORE_STABLE_REF_KINDS,
}


def _raise_ref_error(message: str, *, code: str, details: Mapping[str, Any] | None = None) -> None:
    raise ValidationError(message, code=code, details=details)


def _validate_stable_ref_kind(kind: str) -> str:
    if not isinstance(kind, str):
        _raise_ref_error("StableRef kind must be a string.", code="stable_ref_invalid_kind")
    if not kind or kind != kind.strip():
        _raise_ref_error("StableRef kind must not be blank.", code="stable_ref_invalid_kind")
    if not STABLE_REF_KIND_PATTERN.fullmatch(kind):
        _raise_ref_error(
            f"Invalid StableRef kind: {kind!r}",
            code="stable_ref_invalid_kind",
            details={"kind": kind},
        )
    return kind


def _validate_stable_ref_value(value: str) -> str:
    if not isinstance(value, str):
        _raise_ref_error("StableRef value must be a string.", code="stable_ref_invalid_value")
    if not value or value != value.strip():
        _raise_ref_error("StableRef value must not be blank.", code="stable_ref_invalid_value")
    if any(char in value for char in (" ", "_", "/", ":")):
        _raise_ref_error(
            f"StableRef value contains forbidden characters: {value!r}",
            code="stable_ref_invalid_value",
            details={"value": value},
        )

    components = value.split(".")
    if any(component == "" for component in components):
        _raise_ref_error(
            f"StableRef value contains an empty component: {value!r}",
            code="stable_ref_invalid_value",
            details={"value": value},
        )

    for component in components:
        if len(component) > MAX_STABLE_REF_COMPONENT_LENGTH:
            _raise_ref_error(
                f"StableRef component is too long: {component!r}",
                code="stable_ref_invalid_value",
                details={"value": value, "component": component},
            )
        if not STABLE_REF_COMPONENT_PATTERN.fullmatch(component):
            _raise_ref_error(
                f"Invalid StableRef component: {component!r}",
                code="stable_ref_invalid_value",
                details={"value": value, "component": component},
            )

    return value


def _validate_stable_ref_text_length(kind: str, value: str) -> None:
    if len(f"{kind}:{value}") > MAX_STABLE_REF_TEXT_LENGTH:
        _raise_ref_error(
            "StableRef text exceeds the maximum length.",
            code="stable_ref_too_long",
            details={"kind": kind, "value": value, "max_length": MAX_STABLE_REF_TEXT_LENGTH},
        )


@dataclass(frozen=True, slots=True)
class StableRef:
    """Canonical `kind:value` reference."""

    kind: str
    value: str

    def __post_init__(self) -> None:
        kind = _validate_stable_ref_kind(self.kind)
        value = _validate_stable_ref_value(self.value)
        _validate_stable_ref_text_length(kind, value)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "value", value)

    @property
    def text(self) -> str:
        """Return the canonical text representation."""

        return f"{self.kind}:{self.value}"

    @property
    def components(self) -> tuple[str, ...]:
        """Return the value split into dotted components."""

        return tuple(self.value.split("."))

    @classmethod
    def parse(cls, raw: str) -> "StableRef":
        """Parse a canonical `kind:value` reference string."""

        if not isinstance(raw, str):
            _raise_ref_error("StableRef input must be a string.", code="stable_ref_invalid_text")
        if raw.count(":") != 1:
            _raise_ref_error(
                "StableRef text must contain exactly one ':' separator.",
                code="stable_ref_invalid_text",
                details={"raw": raw},
            )
        kind, value = raw.split(":", 1)
        return cls(kind=kind, value=value)

    def to_dict(self) -> dict[str, str]:
        """Return a transport-friendly object form."""

        return {"kind": self.kind, "value": self.value}

    def __str__(self) -> str:
        return self.text


def validate_core_stable_ref(ref: StableRef) -> StableRef:
    """Validate the core family component count when applicable."""

    expected_count = CORE_STABLE_REF_COMPONENT_COUNTS.get(ref.kind)
    if expected_count is None:
        return ref
    actual_count = len(ref.components)
    if ref.kind in {"sample", "op"}:
        if actual_count not in (4, 5):
            _raise_ref_error(
                f"StableRef kind {ref.kind!r} expects 4 or 5 component(s).",
                code="stable_ref_invalid_shape",
                details={"kind": ref.kind, "value": ref.value, "expected_count": (4, 5)},
            )
        return ref
    if actual_count != expected_count:
        _raise_ref_error(
            f"StableRef kind {ref.kind!r} expects {expected_count} component(s), got {actual_count}.",
            code="stable_ref_invalid_shape",
            details={"kind": ref.kind, "value": ref.value, "expected_count": expected_count},
        )
    return ref


def validate_stable_ref_kind(
    ref: StableRef,
    expected_kind: str | Sequence[str],
    *,
    field_name: str | None = None,
) -> StableRef:
    """Validate that a ref matches an expected kind or family."""

    allowed = (expected_kind,) if isinstance(expected_kind, str) else tuple(expected_kind)
    if ref.kind not in allowed:
        _raise_ref_error(
            f"StableRef kind mismatch for {field_name or 'field'}: expected {allowed}, got {ref.kind!r}.",
            code="stable_ref_kind_mismatch",
            details={"field_name": field_name, "allowed": allowed, "actual": ref.kind},
        )
    return ref


def validate_stable_ref_field(ref: StableRef, field_name: str) -> StableRef:
    """Validate a ref against the canonical field-kind mapping."""

    if field_name not in STABLE_REF_FIELD_KIND_MAP:
        _raise_ref_error(
            f"Unknown StableRef field mapping: {field_name!r}",
            code="stable_ref_unknown_field",
            details={"field_name": field_name},
        )
    expected = STABLE_REF_FIELD_KIND_MAP[field_name]
    validate_core_stable_ref(ref)
    return validate_stable_ref_kind(ref, expected, field_name=field_name)


__all__ = [
    "CORE_STABLE_REF_COMPONENT_COUNTS",
    "CORE_STABLE_REF_KINDS",
    "MAX_STABLE_REF_COMPONENT_LENGTH",
    "MAX_STABLE_REF_TEXT_LENGTH",
    "STABLE_REF_COMPONENT_PATTERN",
    "STABLE_REF_FIELD_KIND_MAP",
    "STABLE_REF_KIND_PATTERN",
    "StableRef",
    "validate_core_stable_ref",
    "validate_stable_ref_field",
    "validate_stable_ref_kind",
]
