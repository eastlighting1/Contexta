"""Canonical artifact manifest model for Contexta contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from ...common.errors import ValidationError
from ..extensions import ExtensionFieldSet
from ..refs import StableRef, validate_core_stable_ref, validate_stable_ref_kind
from .context import (
    DEFAULT_CONTRACT_SCHEMA_VERSION,
    _coerce_ref,
    _normalize_extensions,
    _normalize_required_string,
    _normalize_timestamp_field,
)
from .records import (
    LOWER_SNAKE_TOKEN_PATTERN,
    PRODUCER_REF_PATTERN,
    _normalize_json_mapping,
    _normalize_optional_nonblank_string,
    _normalize_token,
    _serialize_json_mapping,
)


ARTIFACT_KINDS = (
    "dataset_snapshot",
    "feature_set",
    "checkpoint",
    "config_snapshot",
    "model_bundle",
    "report_bundle",
    "export_package",
    "evidence_bundle",
    "debug_bundle",
)


def _raise_artifact_error(
    message: str,
    *,
    code: str,
    details: Mapping[str, Any] | None = None,
) -> None:
    raise ValidationError(message, code=code, details=details)


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    """Canonical artifact manifest."""

    artifact_ref: StableRef | str
    artifact_kind: str
    created_at: str | datetime
    producer_ref: str
    run_ref: StableRef | str
    location_ref: str
    deployment_execution_ref: StableRef | str | None = None
    stage_execution_ref: StableRef | str | None = None
    batch_execution_ref: StableRef | str | None = None
    sample_observation_ref: StableRef | str | None = None
    operation_context_ref: StableRef | str | None = None
    hash_value: str | None = None
    size_bytes: int | None = None
    attributes: Mapping[str, Any] | None = None
    schema_version: str = DEFAULT_CONTRACT_SCHEMA_VERSION
    extensions: tuple[ExtensionFieldSet, ...] = ()

    def __post_init__(self) -> None:
        artifact_ref = _coerce_ref("artifact_ref", self.artifact_ref)
        validate_core_stable_ref(artifact_ref)
        validate_stable_ref_kind(artifact_ref, "artifact", field_name="artifact_ref")

        run_ref = _coerce_ref("run_ref", self.run_ref)
        validate_core_stable_ref(run_ref)
        validate_stable_ref_kind(run_ref, "run", field_name="run_ref")

        deployment_execution_ref = None if self.deployment_execution_ref is None else _coerce_ref(
            "deployment_execution_ref",
            self.deployment_execution_ref,
        )
        if deployment_execution_ref is not None:
            validate_core_stable_ref(deployment_execution_ref)
            validate_stable_ref_kind(
                deployment_execution_ref,
                "deployment",
                field_name="deployment_execution_ref",
            )

        stage_execution_ref = None if self.stage_execution_ref is None else _coerce_ref(
            "stage_execution_ref",
            self.stage_execution_ref,
        )
        if stage_execution_ref is not None:
            validate_core_stable_ref(stage_execution_ref)
            validate_stable_ref_kind(stage_execution_ref, "stage", field_name="stage_execution_ref")

        batch_execution_ref = None if self.batch_execution_ref is None else _coerce_ref(
            "batch_execution_ref",
            self.batch_execution_ref,
        )
        if batch_execution_ref is not None:
            validate_core_stable_ref(batch_execution_ref)
            validate_stable_ref_kind(batch_execution_ref, "batch", field_name="batch_execution_ref")

        sample_observation_ref = None if self.sample_observation_ref is None else _coerce_ref(
            "sample_observation_ref",
            self.sample_observation_ref,
        )
        if sample_observation_ref is not None:
            validate_core_stable_ref(sample_observation_ref)
            validate_stable_ref_kind(sample_observation_ref, "sample", field_name="sample_observation_ref")

        operation_context_ref = None if self.operation_context_ref is None else _coerce_ref(
            "operation_context_ref",
            self.operation_context_ref,
        )
        if operation_context_ref is not None:
            validate_core_stable_ref(operation_context_ref)
            validate_stable_ref_kind(operation_context_ref, "op", field_name="operation_context_ref")

        artifact_kind = _normalize_token(
            "artifact_kind",
            self.artifact_kind,
            pattern=LOWER_SNAKE_TOKEN_PATTERN,
            code="artifact_invalid_artifact_kind",
        )
        created_at = _normalize_timestamp_field("created_at", self.created_at)
        producer_ref = _normalize_token(
            "producer_ref",
            self.producer_ref,
            pattern=PRODUCER_REF_PATTERN,
            code="artifact_invalid_producer_ref",
        )
        location_ref = _normalize_required_string("location_ref", self.location_ref)
        hash_value = _normalize_optional_nonblank_string("hash_value", self.hash_value)
        attributes = _normalize_json_mapping("attributes", self.attributes)
        schema_version = _normalize_required_string("schema_version", self.schema_version)

        if (
            len(artifact_ref.components) != len(run_ref.components) + 1
            or artifact_ref.components[: len(run_ref.components)] != run_ref.components
        ):
            _raise_artifact_error(
                "artifact_ref must equal run_ref + '.' + artifact key.",
                code="artifact_ref_prefix_mismatch",
                details={"artifact_ref": str(artifact_ref), "run_ref": str(run_ref)},
            )

        if stage_execution_ref is not None and stage_execution_ref.components[: len(run_ref.components)] != run_ref.components:
            _raise_artifact_error(
                "stage_execution_ref must share the same run prefix as run_ref.",
                code="artifact_ref_prefix_mismatch",
                details={"stage_execution_ref": str(stage_execution_ref), "run_ref": str(run_ref)},
            )
        if batch_execution_ref is not None and stage_execution_ref is None:
            _raise_artifact_error(
                "batch_execution_ref requires stage_execution_ref.",
                code="artifact_missing_stage_context",
            )
        if batch_execution_ref is not None and stage_execution_ref is not None:
            if batch_execution_ref.components[: len(stage_execution_ref.components)] != stage_execution_ref.components:
                _raise_artifact_error(
                    "batch_execution_ref must share the same stage prefix as stage_execution_ref.",
                    code="artifact_ref_prefix_mismatch",
                    details={
                        "batch_execution_ref": str(batch_execution_ref),
                        "stage_execution_ref": str(stage_execution_ref),
                    },
                )
        if sample_observation_ref is not None and stage_execution_ref is None:
            _raise_artifact_error(
                "sample_observation_ref requires stage_execution_ref.",
                code="artifact_missing_stage_context",
            )
        if sample_observation_ref is not None and stage_execution_ref is not None:
            expected_prefix = batch_execution_ref.components if batch_execution_ref is not None else stage_execution_ref.components
            if sample_observation_ref.components[: len(expected_prefix)] != expected_prefix:
                _raise_artifact_error(
                    "sample_observation_ref must share the same owning prefix as stage/batch context.",
                    code="artifact_ref_prefix_mismatch",
                    details={
                        "sample_observation_ref": str(sample_observation_ref),
                        "owner_ref": str(batch_execution_ref or stage_execution_ref),
                    },
                )

        if operation_context_ref is not None and stage_execution_ref is None:
            _raise_artifact_error(
                "operation_context_ref requires stage_execution_ref.",
                code="artifact_missing_stage_context",
            )
        if operation_context_ref is not None and stage_execution_ref is not None:
            expected_prefix = batch_execution_ref.components if batch_execution_ref is not None else stage_execution_ref.components
            if operation_context_ref.components[: len(expected_prefix)] != expected_prefix:
                _raise_artifact_error(
                    "operation_context_ref must share the same owning prefix as stage/batch context.",
                    code="artifact_ref_prefix_mismatch",
                    details={
                        "operation_context_ref": str(operation_context_ref),
                        "owner_ref": str(batch_execution_ref or stage_execution_ref),
                    },
                )

        if self.size_bytes is not None:
            if not isinstance(self.size_bytes, int) or isinstance(self.size_bytes, bool):
                _raise_artifact_error(
                    "size_bytes must be an integer.",
                    code="artifact_invalid_size_bytes",
                    details={"size_bytes": self.size_bytes},
                )
            if self.size_bytes < 0:
                _raise_artifact_error(
                    "size_bytes must be greater than or equal to zero.",
                    code="artifact_invalid_size_bytes",
                    details={"size_bytes": self.size_bytes},
                )

        object.__setattr__(self, "artifact_ref", artifact_ref)
        object.__setattr__(self, "artifact_kind", artifact_kind)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "producer_ref", producer_ref)
        object.__setattr__(self, "run_ref", run_ref)
        object.__setattr__(self, "location_ref", location_ref)
        object.__setattr__(self, "deployment_execution_ref", deployment_execution_ref)
        object.__setattr__(self, "stage_execution_ref", stage_execution_ref)
        object.__setattr__(self, "batch_execution_ref", batch_execution_ref)
        object.__setattr__(self, "sample_observation_ref", sample_observation_ref)
        object.__setattr__(self, "operation_context_ref", operation_context_ref)
        object.__setattr__(self, "hash_value", hash_value)
        object.__setattr__(self, "attributes", attributes)
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "extensions", _normalize_extensions(self.extensions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_ref": str(self.artifact_ref),
            "artifact_kind": self.artifact_kind,
            "created_at": self.created_at,
            "producer_ref": self.producer_ref,
            "run_ref": str(self.run_ref),
            "location_ref": self.location_ref,
            "deployment_execution_ref": None
            if self.deployment_execution_ref is None
            else str(self.deployment_execution_ref),
            "stage_execution_ref": None if self.stage_execution_ref is None else str(self.stage_execution_ref),
            "batch_execution_ref": None if self.batch_execution_ref is None else str(self.batch_execution_ref),
            "sample_observation_ref": None
            if self.sample_observation_ref is None
            else str(self.sample_observation_ref),
            "operation_context_ref": None
            if self.operation_context_ref is None
            else str(self.operation_context_ref),
            "hash_value": self.hash_value,
            "size_bytes": self.size_bytes,
            "attributes": _serialize_json_mapping(self.attributes),
            "schema_version": self.schema_version,
            "extensions": [extension.to_dict() for extension in self.extensions],
        }


__all__ = [
    "ARTIFACT_KINDS",
    "ArtifactManifest",
]
