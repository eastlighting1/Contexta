"""Canonical lineage and provenance models for Contexta contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from ...common.errors import ValidationError
from ..extensions import ExtensionFieldSet
from ..refs import CORE_STABLE_REF_KINDS, StableRef, validate_core_stable_ref, validate_stable_ref_kind
from .context import (
    DEFAULT_CONTRACT_SCHEMA_VERSION,
    _coerce_ref,
    _normalize_extensions,
    _normalize_required_string,
    _normalize_timestamp_field,
)
from .records import (
    DOT_TOKEN_PATTERN,
    _normalize_marker,
    _normalize_ref_tuple,
    _normalize_token,
)


RELATION_TYPES = (
    "generated_from",
    "consumed_by",
    "produced_by",
    "packaged_from",
    "reported_by",
    "evaluated_on",
    "deployed_from",
    "used",
    "derived_from",
    "observed_in",
)
LINEAGE_ORIGIN_MARKERS = ("explicit", "imported", "inferred", "replayed")
CONFIDENCE_MARKERS = ("high", "medium", "low", "unknown")
ASSERTION_MODES = ("explicit", "imported", "inferred", "replayed")


def _raise_lineage_error(
    message: str,
    *,
    code: str,
    details: Mapping[str, Any] | None = None,
) -> None:
    raise ValidationError(message, code=code, details=details)


def _normalize_any_ref(field_name: str, value: StableRef | str) -> StableRef:
    ref = _coerce_ref(field_name, value)
    if ref.kind in CORE_STABLE_REF_KINDS:
        validate_core_stable_ref(ref)
    return ref


def _normalize_optional_any_ref(field_name: str, value: StableRef | str | None) -> StableRef | None:
    if value is None:
        return None
    return _normalize_any_ref(field_name, value)


def _normalize_artifact_ref_text(field_name: str, value: StableRef | str | None) -> str | None:
    if value is None:
        return None
    ref = _normalize_any_ref(field_name, value)
    validate_stable_ref_kind(ref, "artifact", field_name=field_name)
    return str(ref)


@dataclass(frozen=True, slots=True)
class LineageEdge:
    """Canonical directional lineage relation."""

    relation_ref: StableRef | str
    relation_type: str
    source_ref: StableRef | str
    target_ref: StableRef | str
    recorded_at: str | datetime
    origin_marker: str
    confidence_marker: str
    operation_context_ref: StableRef | str | None = None
    evidence_refs: tuple[StableRef | str, ...] = ()
    schema_version: str = DEFAULT_CONTRACT_SCHEMA_VERSION
    extensions: tuple[ExtensionFieldSet, ...] = ()

    def __post_init__(self) -> None:
        relation_ref = _coerce_ref("relation_ref", self.relation_ref)
        validate_stable_ref_kind(relation_ref, "relation", field_name="relation_ref")

        source_ref = _normalize_any_ref("source_ref", self.source_ref)
        target_ref = _normalize_any_ref("target_ref", self.target_ref)
        recorded_at = _normalize_timestamp_field("recorded_at", self.recorded_at)
        relation_type = _normalize_marker("relation_type", self.relation_type, RELATION_TYPES)
        origin_marker = _normalize_marker("origin_marker", self.origin_marker, LINEAGE_ORIGIN_MARKERS)
        confidence_marker = _normalize_marker(
            "confidence_marker",
            self.confidence_marker,
            CONFIDENCE_MARKERS,
        )
        operation_context_ref = _normalize_optional_any_ref("operation_context_ref", self.operation_context_ref)
        if operation_context_ref is not None:
            validate_stable_ref_kind(operation_context_ref, "op", field_name="operation_context_ref")

        if source_ref == target_ref:
            _raise_lineage_error(
                "source_ref and target_ref must differ.",
                code="lineage_self_relation",
                details={"source_ref": str(source_ref), "target_ref": str(target_ref)},
            )

        object.__setattr__(self, "relation_ref", relation_ref)
        object.__setattr__(self, "relation_type", relation_type)
        object.__setattr__(self, "source_ref", source_ref)
        object.__setattr__(self, "target_ref", target_ref)
        object.__setattr__(self, "recorded_at", recorded_at)
        object.__setattr__(self, "origin_marker", origin_marker)
        object.__setattr__(self, "confidence_marker", confidence_marker)
        object.__setattr__(self, "operation_context_ref", operation_context_ref)
        object.__setattr__(self, "evidence_refs", _normalize_ref_tuple("evidence_refs", self.evidence_refs))
        object.__setattr__(self, "schema_version", _normalize_required_string("schema_version", self.schema_version))
        object.__setattr__(self, "extensions", _normalize_extensions(self.extensions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_ref": str(self.relation_ref),
            "relation_type": self.relation_type,
            "source_ref": str(self.source_ref),
            "target_ref": str(self.target_ref),
            "recorded_at": self.recorded_at,
            "origin_marker": self.origin_marker,
            "confidence_marker": self.confidence_marker,
            "operation_context_ref": None
            if self.operation_context_ref is None
            else str(self.operation_context_ref),
            "evidence_refs": list(self.evidence_refs),
            "schema_version": self.schema_version,
            "extensions": [extension.to_dict() for extension in self.extensions],
        }


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    """Canonical provenance record attached to a lineage relation."""

    provenance_ref: StableRef | str
    relation_ref: StableRef | str
    assertion_mode: str
    asserted_at: str | datetime
    formation_context_ref: StableRef | str | None = None
    policy_ref: str | None = None
    evidence_bundle_ref: StableRef | str | None = None
    schema_version: str = DEFAULT_CONTRACT_SCHEMA_VERSION
    extensions: tuple[ExtensionFieldSet, ...] = ()

    def __post_init__(self) -> None:
        provenance_ref = _coerce_ref("provenance_ref", self.provenance_ref)
        validate_stable_ref_kind(provenance_ref, "provenance", field_name="provenance_ref")

        relation_ref = _coerce_ref("relation_ref", self.relation_ref)
        validate_stable_ref_kind(relation_ref, "relation", field_name="relation_ref")

        formation_context_ref = _normalize_optional_any_ref("formation_context_ref", self.formation_context_ref)
        policy_ref = None
        if self.policy_ref is not None:
            policy_ref = _normalize_token(
                "policy_ref",
                self.policy_ref,
                pattern=DOT_TOKEN_PATTERN,
                code="lineage_invalid_policy_ref",
            )
        evidence_bundle_ref = _normalize_artifact_ref_text("evidence_bundle_ref", self.evidence_bundle_ref)

        object.__setattr__(self, "provenance_ref", provenance_ref)
        object.__setattr__(self, "relation_ref", relation_ref)
        object.__setattr__(self, "assertion_mode", _normalize_marker("assertion_mode", self.assertion_mode, ASSERTION_MODES))
        object.__setattr__(self, "asserted_at", _normalize_timestamp_field("asserted_at", self.asserted_at))
        object.__setattr__(self, "formation_context_ref", formation_context_ref)
        object.__setattr__(self, "policy_ref", policy_ref)
        object.__setattr__(self, "evidence_bundle_ref", evidence_bundle_ref)
        object.__setattr__(self, "schema_version", _normalize_required_string("schema_version", self.schema_version))
        object.__setattr__(self, "extensions", _normalize_extensions(self.extensions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "provenance_ref": str(self.provenance_ref),
            "relation_ref": str(self.relation_ref),
            "assertion_mode": self.assertion_mode,
            "asserted_at": self.asserted_at,
            "formation_context_ref": None
            if self.formation_context_ref is None
            else str(self.formation_context_ref),
            "policy_ref": self.policy_ref,
            "evidence_bundle_ref": self.evidence_bundle_ref,
            "schema_version": self.schema_version,
            "extensions": [extension.to_dict() for extension in self.extensions],
        }


__all__ = [
    "ASSERTION_MODES",
    "CONFIDENCE_MARKERS",
    "LINEAGE_ORIGIN_MARKERS",
    "RELATION_TYPES",
    "LineageEdge",
    "ProvenanceRecord",
]
