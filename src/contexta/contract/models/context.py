"""Canonical context models for Contexta contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from ...common.errors import ConflictError, ValidationError
from ...common.time import normalize_timestamp
from ..extensions import ExtensionFieldSet
from ..refs import STABLE_REF_COMPONENT_PATTERN, StableRef, validate_core_stable_ref, validate_stable_ref_kind


DEFAULT_CONTRACT_SCHEMA_VERSION = "1.0.0"
RUN_STAGE_STATUSES = ("open", "completed", "failed", "cancelled")


def _raise_context_error(
    message: str,
    *,
    code: str,
    details: Mapping[str, Any] | None = None,
) -> None:
    raise ValidationError(message, code=code, details=details)


def _coerce_ref(field_name: str, value: StableRef | str) -> StableRef:
    if isinstance(value, StableRef):
        return value
    if isinstance(value, str):
        try:
            return StableRef.parse(value)
        except ValidationError as exc:
            raise ValidationError(
                f"Invalid {field_name}.",
                code=exc.code,
                details={"field_name": field_name, "value": value},
                cause=exc,
            ) from exc
    _raise_context_error(
        f"{field_name} must be StableRef or str.",
        code="context_invalid_ref",
        details={"field_name": field_name, "type": type(value).__name__},
    )


def _normalize_required_string(field_name: str, value: str) -> str:
    if not isinstance(value, str):
        _raise_context_error(
            f"{field_name} must be a string.",
            code="context_invalid_string",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    text = value.strip()
    if not text:
        _raise_context_error(
            f"{field_name} must not be blank.",
            code="context_invalid_string",
            details={"field_name": field_name},
        )
    return text


def _normalize_optional_string(field_name: str, value: str | None) -> str | None:
    if value is None:
        return None
    text = _normalize_required_string(field_name, value)
    return text or None


def _normalize_component_name(field_name: str, value: str) -> str:
    text = _normalize_required_string(field_name, value)
    if not STABLE_REF_COMPONENT_PATTERN.fullmatch(text):
        _raise_context_error(
            f"{field_name} must be lower-kebab canonical text.",
            code="context_invalid_component",
            details={"field_name": field_name, "value": value},
        )
    return text


def _normalize_timestamp_field(field_name: str, value: str | datetime) -> str:
    if isinstance(value, datetime):
        return normalize_timestamp(value)
    if not isinstance(value, str):
        _raise_context_error(
            f"{field_name} must be a timestamp string.",
            code="context_invalid_timestamp",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    text = value.strip()
    if not text:
        _raise_context_error(
            f"{field_name} must not be blank.",
            code="context_invalid_timestamp",
            details={"field_name": field_name},
        )
    if not text.endswith("Z"):
        _raise_context_error(
            f"{field_name} must be an ISO-8601 UTC 'Z' timestamp.",
            code="context_invalid_timestamp",
            details={"field_name": field_name, "value": value},
        )
    try:
        return normalize_timestamp(text)
    except Exception as exc:  # pragma: no cover
        raise ValidationError(
            f"Invalid {field_name}.",
            code="context_invalid_timestamp",
            details={"field_name": field_name, "value": value},
            cause=exc,
        ) from exc


def _normalize_string_mapping(
    field_name: str,
    mapping: Mapping[str, str] | None,
) -> Mapping[str, str]:
    if mapping is None:
        return MappingProxyType({})
    if not isinstance(mapping, Mapping):
        _raise_context_error(
            f"{field_name} must be a mapping.",
            code="context_invalid_mapping",
            details={"field_name": field_name, "type": type(mapping).__name__},
        )

    normalized: dict[str, str] = {}
    for key, value in mapping.items():
        if not isinstance(key, str) or not key.strip():
            _raise_context_error(
                f"{field_name} contains an invalid key.",
                code="context_invalid_mapping",
                details={"field_name": field_name, "key": key},
            )
        if not isinstance(value, str) or not value.strip():
            _raise_context_error(
                f"{field_name} contains an invalid value.",
                code="context_invalid_mapping",
                details={"field_name": field_name, "key": key, "value": value},
            )
        normalized[key.strip()] = value.strip()
    return MappingProxyType({key: normalized[key] for key in sorted(normalized)})


def _normalize_extensions(
    extensions: Sequence[ExtensionFieldSet] | None,
) -> tuple[ExtensionFieldSet, ...]:
    if extensions is None:
        return ()

    normalized: list[ExtensionFieldSet] = []
    items = tuple(extensions)
    for extension in items:
        if not isinstance(extension, ExtensionFieldSet):
            _raise_context_error(
                "extensions must contain ExtensionFieldSet objects.",
                code="context_invalid_extensions",
                details={"type": type(extension).__name__},
            )

    seen: set[str] = set()
    for extension in sorted(items, key=lambda item: item.namespace):
        if extension.namespace in seen:
            raise ConflictError(
                "Duplicate extension namespace on one object.",
                code="extension_duplicate_namespace",
                details={"namespace": extension.namespace},
            )
        seen.add(extension.namespace)
        normalized.append(extension)
    return tuple(normalized)


def _assert_status_ended_at(
    *,
    status: str,
    ended_at: str | None,
    field_name: str,
) -> None:
    if status == "open" and ended_at is not None:
        _raise_context_error(
            f"{field_name} must be None when status is 'open'.",
            code="context_invalid_status_transition",
            details={"status": status, "ended_at": ended_at},
        )
    if status != "open" and ended_at is None:
        _raise_context_error(
            f"{field_name} is required when status is closed.",
            code="context_invalid_status_transition",
            details={"status": status},
        )


def _assert_prefix_match(
    *,
    ref_value: str,
    prefix_value: str,
    field_name: str,
) -> None:
    if not ref_value.startswith(prefix_value + "."):
        _raise_context_error(
            f"{field_name} must start with {prefix_value!r}.",
            code="context_ref_prefix_mismatch",
            details={"field_name": field_name, "ref_value": ref_value, "prefix_value": prefix_value},
        )


def _serialize_extensions(extensions: Sequence[ExtensionFieldSet]) -> list[dict[str, Any]]:
    return [extension.to_dict() for extension in extensions]


@dataclass(frozen=True, slots=True)
class Project:
    """Canonical project context model."""

    project_ref: StableRef | str
    name: str
    created_at: str | datetime
    description: str | None = None
    tags: Mapping[str, str] | None = None
    schema_version: str = DEFAULT_CONTRACT_SCHEMA_VERSION
    extensions: tuple[ExtensionFieldSet, ...] = ()

    def __post_init__(self) -> None:
        project_ref = _coerce_ref("project_ref", self.project_ref)
        validate_core_stable_ref(project_ref)
        validate_stable_ref_kind(project_ref, "project", field_name="project_ref")

        object.__setattr__(self, "project_ref", project_ref)
        object.__setattr__(self, "name", _normalize_required_string("name", self.name))
        object.__setattr__(self, "created_at", _normalize_timestamp_field("created_at", self.created_at))
        object.__setattr__(self, "description", _normalize_optional_string("description", self.description))
        object.__setattr__(self, "tags", _normalize_string_mapping("tags", self.tags))
        object.__setattr__(self, "schema_version", _normalize_required_string("schema_version", self.schema_version))
        object.__setattr__(self, "extensions", _normalize_extensions(self.extensions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_ref": str(self.project_ref),
            "name": self.name,
            "created_at": self.created_at,
            "description": self.description,
            "tags": dict(self.tags),
            "schema_version": self.schema_version,
            "extensions": _serialize_extensions(self.extensions),
        }


@dataclass(frozen=True, slots=True)
class Run:
    """Canonical run context model."""

    run_ref: StableRef | str
    project_ref: StableRef | str
    name: str
    status: str
    started_at: str | datetime
    ended_at: str | datetime | None = None
    description: str | None = None
    schema_version: str = DEFAULT_CONTRACT_SCHEMA_VERSION
    extensions: tuple[ExtensionFieldSet, ...] = ()

    def __post_init__(self) -> None:
        run_ref = _coerce_ref("run_ref", self.run_ref)
        validate_core_stable_ref(run_ref)
        validate_stable_ref_kind(run_ref, "run", field_name="run_ref")

        project_ref = _coerce_ref("project_ref", self.project_ref)
        validate_core_stable_ref(project_ref)
        validate_stable_ref_kind(project_ref, "project", field_name="project_ref")

        status = _normalize_required_string("status", self.status)
        if status not in RUN_STAGE_STATUSES:
            _raise_context_error(
                "Run.status must be one of the canonical lifecycle values.",
                code="context_invalid_status",
                details={"status": status, "allowed": RUN_STAGE_STATUSES},
            )

        started_at = _normalize_timestamp_field("started_at", self.started_at)
        ended_at = None if self.ended_at is None else _normalize_timestamp_field("ended_at", self.ended_at)

        _assert_status_ended_at(status=status, ended_at=ended_at, field_name="ended_at")
        if ended_at is not None and ended_at < started_at:
            _raise_context_error(
                "Run.ended_at must be greater than or equal to started_at.",
                code="context_invalid_time_order",
                details={"started_at": started_at, "ended_at": ended_at},
            )
        if run_ref.components[0] != project_ref.value:
            _raise_context_error(
                "run_ref project prefix must match project_ref.",
                code="context_ref_prefix_mismatch",
                details={"run_ref": str(run_ref), "project_ref": str(project_ref)},
            )

        object.__setattr__(self, "run_ref", run_ref)
        object.__setattr__(self, "project_ref", project_ref)
        object.__setattr__(self, "name", _normalize_required_string("name", self.name))
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "ended_at", ended_at)
        object.__setattr__(self, "description", _normalize_optional_string("description", self.description))
        object.__setattr__(self, "schema_version", _normalize_required_string("schema_version", self.schema_version))
        object.__setattr__(self, "extensions", _normalize_extensions(self.extensions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_ref": str(self.run_ref),
            "project_ref": str(self.project_ref),
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "description": self.description,
            "schema_version": self.schema_version,
            "extensions": _serialize_extensions(self.extensions),
        }


@dataclass(frozen=True, slots=True)
class DeploymentExecution:
    """Canonical deployment execution model."""

    deployment_execution_ref: StableRef | str
    project_ref: StableRef | str
    deployment_name: str
    status: str
    started_at: str | datetime
    ended_at: str | datetime | None = None
    order_index: int | None = None
    run_ref: StableRef | str | None = None
    artifact_ref: StableRef | str | None = None
    environment_snapshot_ref: StableRef | str | None = None
    schema_version: str = DEFAULT_CONTRACT_SCHEMA_VERSION
    extensions: tuple[ExtensionFieldSet, ...] = ()

    def __post_init__(self) -> None:
        deployment_execution_ref = _coerce_ref("deployment_execution_ref", self.deployment_execution_ref)
        validate_core_stable_ref(deployment_execution_ref)
        validate_stable_ref_kind(deployment_execution_ref, "deployment", field_name="deployment_execution_ref")

        project_ref = _coerce_ref("project_ref", self.project_ref)
        validate_core_stable_ref(project_ref)
        validate_stable_ref_kind(project_ref, "project", field_name="project_ref")

        run_ref = None if self.run_ref is None else _coerce_ref("run_ref", self.run_ref)
        if run_ref is not None:
            validate_core_stable_ref(run_ref)
            validate_stable_ref_kind(run_ref, "run", field_name="run_ref")

        artifact_ref = None if self.artifact_ref is None else _coerce_ref("artifact_ref", self.artifact_ref)
        if artifact_ref is not None:
            validate_core_stable_ref(artifact_ref)
            validate_stable_ref_kind(artifact_ref, "artifact", field_name="artifact_ref")

        environment_snapshot_ref = None if self.environment_snapshot_ref is None else _coerce_ref(
            "environment_snapshot_ref",
            self.environment_snapshot_ref,
        )
        if environment_snapshot_ref is not None:
            validate_stable_ref_kind(
                environment_snapshot_ref,
                "environment",
                field_name="environment_snapshot_ref",
            )

        deployment_name = _normalize_component_name("deployment_name", self.deployment_name)
        status = _normalize_required_string("status", self.status)
        if status not in RUN_STAGE_STATUSES:
            _raise_context_error(
                "DeploymentExecution.status must be one of the canonical lifecycle values.",
                code="context_invalid_status",
                details={"status": status, "allowed": RUN_STAGE_STATUSES},
            )

        started_at = _normalize_timestamp_field("started_at", self.started_at)
        ended_at = None if self.ended_at is None else _normalize_timestamp_field("ended_at", self.ended_at)
        _assert_status_ended_at(status=status, ended_at=ended_at, field_name="ended_at")
        if ended_at is not None and ended_at < started_at:
            _raise_context_error(
                "DeploymentExecution.ended_at must be greater than or equal to started_at.",
                code="context_invalid_time_order",
                details={"started_at": started_at, "ended_at": ended_at},
            )

        if deployment_execution_ref.value != f"{project_ref.value}.{deployment_name}":
            _raise_context_error(
                "deployment_execution_ref must equal project_ref + '.' + deployment_name.",
                code="context_ref_prefix_mismatch",
                details={
                    "deployment_execution_ref": str(deployment_execution_ref),
                    "project_ref": str(project_ref),
                    "deployment_name": deployment_name,
                },
            )
        if run_ref is not None and run_ref.components[0] != project_ref.value:
            _raise_context_error(
                "run_ref project prefix must match project_ref.",
                code="context_ref_prefix_mismatch",
                details={"run_ref": str(run_ref), "project_ref": str(project_ref)},
            )
        if artifact_ref is not None and artifact_ref.components[0] != project_ref.value:
            _raise_context_error(
                "artifact_ref project prefix must match project_ref.",
                code="context_ref_prefix_mismatch",
                details={"artifact_ref": str(artifact_ref), "project_ref": str(project_ref)},
            )
        if environment_snapshot_ref is not None and run_ref is not None:
            _assert_prefix_match(
                ref_value=environment_snapshot_ref.value,
                prefix_value=run_ref.value,
                field_name="environment_snapshot_ref",
            )

        if self.order_index is not None:
            if not isinstance(self.order_index, int) or isinstance(self.order_index, bool):
                _raise_context_error(
                    "order_index must be an integer.",
                    code="context_invalid_order_index",
                    details={"order_index": self.order_index},
                )
            if self.order_index < 0:
                _raise_context_error(
                    "order_index must be greater than or equal to zero.",
                    code="context_invalid_order_index",
                    details={"order_index": self.order_index},
                )

        object.__setattr__(self, "deployment_execution_ref", deployment_execution_ref)
        object.__setattr__(self, "project_ref", project_ref)
        object.__setattr__(self, "deployment_name", deployment_name)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "ended_at", ended_at)
        object.__setattr__(self, "run_ref", run_ref)
        object.__setattr__(self, "artifact_ref", artifact_ref)
        object.__setattr__(self, "environment_snapshot_ref", environment_snapshot_ref)
        object.__setattr__(self, "schema_version", _normalize_required_string("schema_version", self.schema_version))
        object.__setattr__(self, "extensions", _normalize_extensions(self.extensions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment_execution_ref": str(self.deployment_execution_ref),
            "project_ref": str(self.project_ref),
            "deployment_name": self.deployment_name,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "order_index": self.order_index,
            "run_ref": None if self.run_ref is None else str(self.run_ref),
            "artifact_ref": None if self.artifact_ref is None else str(self.artifact_ref),
            "environment_snapshot_ref": None
            if self.environment_snapshot_ref is None
            else str(self.environment_snapshot_ref),
            "schema_version": self.schema_version,
            "extensions": _serialize_extensions(self.extensions),
        }


@dataclass(frozen=True, slots=True)
class StageExecution:
    """Canonical stage execution model."""

    stage_execution_ref: StableRef | str
    run_ref: StableRef | str
    stage_name: str
    status: str
    started_at: str | datetime
    ended_at: str | datetime | None = None
    order_index: int | None = None
    schema_version: str = DEFAULT_CONTRACT_SCHEMA_VERSION
    extensions: tuple[ExtensionFieldSet, ...] = ()

    def __post_init__(self) -> None:
        stage_execution_ref = _coerce_ref("stage_execution_ref", self.stage_execution_ref)
        validate_core_stable_ref(stage_execution_ref)
        validate_stable_ref_kind(stage_execution_ref, "stage", field_name="stage_execution_ref")

        run_ref = _coerce_ref("run_ref", self.run_ref)
        validate_core_stable_ref(run_ref)
        validate_stable_ref_kind(run_ref, "run", field_name="run_ref")

        stage_name = _normalize_component_name("stage_name", self.stage_name)
        status = _normalize_required_string("status", self.status)
        if status not in RUN_STAGE_STATUSES:
            _raise_context_error(
                "StageExecution.status must be one of the canonical lifecycle values.",
                code="context_invalid_status",
                details={"status": status, "allowed": RUN_STAGE_STATUSES},
            )

        started_at = _normalize_timestamp_field("started_at", self.started_at)
        ended_at = None if self.ended_at is None else _normalize_timestamp_field("ended_at", self.ended_at)
        _assert_status_ended_at(status=status, ended_at=ended_at, field_name="ended_at")
        if ended_at is not None and ended_at < started_at:
            _raise_context_error(
                "StageExecution.ended_at must be greater than or equal to started_at.",
                code="context_invalid_time_order",
                details={"started_at": started_at, "ended_at": ended_at},
            )

        if stage_execution_ref.value != f"{run_ref.value}.{stage_name}":
            _raise_context_error(
                "stage_execution_ref must equal run_ref + '.' + stage_name.",
                code="context_ref_prefix_mismatch",
                details={
                    "stage_execution_ref": str(stage_execution_ref),
                    "run_ref": str(run_ref),
                    "stage_name": stage_name,
                },
            )

        if self.order_index is not None:
            if not isinstance(self.order_index, int) or isinstance(self.order_index, bool):
                _raise_context_error(
                    "order_index must be an integer.",
                    code="context_invalid_order_index",
                    details={"order_index": self.order_index},
                )
            if self.order_index < 0:
                _raise_context_error(
                    "order_index must be greater than or equal to zero.",
                    code="context_invalid_order_index",
                    details={"order_index": self.order_index},
                )

        object.__setattr__(self, "stage_execution_ref", stage_execution_ref)
        object.__setattr__(self, "run_ref", run_ref)
        object.__setattr__(self, "stage_name", stage_name)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "ended_at", ended_at)
        object.__setattr__(self, "schema_version", _normalize_required_string("schema_version", self.schema_version))
        object.__setattr__(self, "extensions", _normalize_extensions(self.extensions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_execution_ref": str(self.stage_execution_ref),
            "run_ref": str(self.run_ref),
            "stage_name": self.stage_name,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "order_index": self.order_index,
            "schema_version": self.schema_version,
            "extensions": _serialize_extensions(self.extensions),
        }


@dataclass(frozen=True, slots=True)
class BatchExecution:
    """Canonical batch execution model."""

    batch_execution_ref: StableRef | str
    run_ref: StableRef | str
    stage_execution_ref: StableRef | str
    batch_name: str
    status: str
    started_at: str | datetime
    ended_at: str | datetime | None = None
    order_index: int | None = None
    schema_version: str = DEFAULT_CONTRACT_SCHEMA_VERSION
    extensions: tuple[ExtensionFieldSet, ...] = ()

    def __post_init__(self) -> None:
        batch_execution_ref = _coerce_ref("batch_execution_ref", self.batch_execution_ref)
        validate_core_stable_ref(batch_execution_ref)
        validate_stable_ref_kind(batch_execution_ref, "batch", field_name="batch_execution_ref")

        run_ref = _coerce_ref("run_ref", self.run_ref)
        validate_core_stable_ref(run_ref)
        validate_stable_ref_kind(run_ref, "run", field_name="run_ref")

        stage_execution_ref = _coerce_ref("stage_execution_ref", self.stage_execution_ref)
        validate_core_stable_ref(stage_execution_ref)
        validate_stable_ref_kind(stage_execution_ref, "stage", field_name="stage_execution_ref")

        batch_name = _normalize_component_name("batch_name", self.batch_name)
        status = _normalize_required_string("status", self.status)
        if status not in RUN_STAGE_STATUSES:
            _raise_context_error(
                "BatchExecution.status must be one of the canonical lifecycle values.",
                code="context_invalid_status",
                details={"status": status, "allowed": RUN_STAGE_STATUSES},
            )

        started_at = _normalize_timestamp_field("started_at", self.started_at)
        ended_at = None if self.ended_at is None else _normalize_timestamp_field("ended_at", self.ended_at)
        _assert_status_ended_at(status=status, ended_at=ended_at, field_name="ended_at")
        if ended_at is not None and ended_at < started_at:
            _raise_context_error(
                "BatchExecution.ended_at must be greater than or equal to started_at.",
                code="context_invalid_time_order",
                details={"started_at": started_at, "ended_at": ended_at},
            )

        _assert_prefix_match(
            ref_value=stage_execution_ref.value,
            prefix_value=run_ref.value,
            field_name="stage_execution_ref",
        )
        if batch_execution_ref.value != f"{stage_execution_ref.value}.{batch_name}":
            _raise_context_error(
                "batch_execution_ref must equal stage_execution_ref + '.' + batch_name.",
                code="context_ref_prefix_mismatch",
                details={
                    "batch_execution_ref": str(batch_execution_ref),
                    "stage_execution_ref": str(stage_execution_ref),
                    "batch_name": batch_name,
                },
            )

        if self.order_index is not None:
            if not isinstance(self.order_index, int) or isinstance(self.order_index, bool):
                _raise_context_error(
                    "order_index must be an integer.",
                    code="context_invalid_order_index",
                    details={"order_index": self.order_index},
                )
            if self.order_index < 0:
                _raise_context_error(
                    "order_index must be greater than or equal to zero.",
                    code="context_invalid_order_index",
                    details={"order_index": self.order_index},
                )

        object.__setattr__(self, "batch_execution_ref", batch_execution_ref)
        object.__setattr__(self, "run_ref", run_ref)
        object.__setattr__(self, "stage_execution_ref", stage_execution_ref)
        object.__setattr__(self, "batch_name", batch_name)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "ended_at", ended_at)
        object.__setattr__(self, "schema_version", _normalize_required_string("schema_version", self.schema_version))
        object.__setattr__(self, "extensions", _normalize_extensions(self.extensions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_execution_ref": str(self.batch_execution_ref),
            "run_ref": str(self.run_ref),
            "stage_execution_ref": str(self.stage_execution_ref),
            "batch_name": self.batch_name,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "order_index": self.order_index,
            "schema_version": self.schema_version,
            "extensions": _serialize_extensions(self.extensions),
        }


@dataclass(frozen=True, slots=True)
class SampleObservation:
    """Canonical sample observation model."""

    sample_observation_ref: StableRef | str
    run_ref: StableRef | str
    stage_execution_ref: StableRef | str
    sample_name: str
    observed_at: str | datetime
    batch_execution_ref: StableRef | str | None = None
    retention_class: str | None = None
    redaction_profile: str | None = None
    schema_version: str = DEFAULT_CONTRACT_SCHEMA_VERSION
    extensions: tuple[ExtensionFieldSet, ...] = ()

    def __post_init__(self) -> None:
        sample_observation_ref = _coerce_ref("sample_observation_ref", self.sample_observation_ref)
        validate_core_stable_ref(sample_observation_ref)
        validate_stable_ref_kind(sample_observation_ref, "sample", field_name="sample_observation_ref")

        run_ref = _coerce_ref("run_ref", self.run_ref)
        validate_core_stable_ref(run_ref)
        validate_stable_ref_kind(run_ref, "run", field_name="run_ref")

        stage_execution_ref = _coerce_ref("stage_execution_ref", self.stage_execution_ref)
        validate_core_stable_ref(stage_execution_ref)
        validate_stable_ref_kind(stage_execution_ref, "stage", field_name="stage_execution_ref")

        batch_execution_ref = None if self.batch_execution_ref is None else _coerce_ref(
            "batch_execution_ref",
            self.batch_execution_ref,
        )
        if batch_execution_ref is not None:
            validate_core_stable_ref(batch_execution_ref)
            validate_stable_ref_kind(batch_execution_ref, "batch", field_name="batch_execution_ref")

        sample_name = _normalize_component_name("sample_name", self.sample_name)
        observed_at = _normalize_timestamp_field("observed_at", self.observed_at)

        _assert_prefix_match(
            ref_value=stage_execution_ref.value,
            prefix_value=run_ref.value,
            field_name="stage_execution_ref",
        )
        owner_ref = stage_execution_ref
        if batch_execution_ref is not None:
            _assert_prefix_match(
                ref_value=batch_execution_ref.value,
                prefix_value=stage_execution_ref.value,
                field_name="batch_execution_ref",
            )
            owner_ref = batch_execution_ref
        if sample_observation_ref.value != f"{owner_ref.value}.{sample_name}":
            _raise_context_error(
                "sample_observation_ref must equal owning scope ref + '.' + sample_name.",
                code="context_ref_prefix_mismatch",
                details={
                    "sample_observation_ref": str(sample_observation_ref),
                    "owner_ref": str(owner_ref),
                    "sample_name": sample_name,
                },
            )

        object.__setattr__(self, "sample_observation_ref", sample_observation_ref)
        object.__setattr__(self, "run_ref", run_ref)
        object.__setattr__(self, "stage_execution_ref", stage_execution_ref)
        object.__setattr__(self, "batch_execution_ref", batch_execution_ref)
        object.__setattr__(self, "sample_name", sample_name)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "retention_class", _normalize_optional_string("retention_class", self.retention_class))
        object.__setattr__(self, "redaction_profile", _normalize_optional_string("redaction_profile", self.redaction_profile))
        object.__setattr__(self, "schema_version", _normalize_required_string("schema_version", self.schema_version))
        object.__setattr__(self, "extensions", _normalize_extensions(self.extensions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_observation_ref": str(self.sample_observation_ref),
            "run_ref": str(self.run_ref),
            "stage_execution_ref": str(self.stage_execution_ref),
            "batch_execution_ref": None if self.batch_execution_ref is None else str(self.batch_execution_ref),
            "sample_name": self.sample_name,
            "observed_at": self.observed_at,
            "retention_class": self.retention_class,
            "redaction_profile": self.redaction_profile,
            "schema_version": self.schema_version,
            "extensions": _serialize_extensions(self.extensions),
        }


@dataclass(frozen=True, slots=True)
class OperationContext:
    """Canonical operation context model."""

    operation_context_ref: StableRef | str
    run_ref: StableRef | str
    stage_execution_ref: StableRef | str
    operation_name: str
    observed_at: str | datetime
    batch_execution_ref: StableRef | str | None = None
    schema_version: str = DEFAULT_CONTRACT_SCHEMA_VERSION
    extensions: tuple[ExtensionFieldSet, ...] = ()

    def __post_init__(self) -> None:
        operation_context_ref = _coerce_ref("operation_context_ref", self.operation_context_ref)
        validate_core_stable_ref(operation_context_ref)
        validate_stable_ref_kind(operation_context_ref, "op", field_name="operation_context_ref")

        run_ref = _coerce_ref("run_ref", self.run_ref)
        validate_core_stable_ref(run_ref)
        validate_stable_ref_kind(run_ref, "run", field_name="run_ref")

        stage_execution_ref = _coerce_ref("stage_execution_ref", self.stage_execution_ref)
        validate_core_stable_ref(stage_execution_ref)
        validate_stable_ref_kind(stage_execution_ref, "stage", field_name="stage_execution_ref")

        batch_execution_ref = None if self.batch_execution_ref is None else _coerce_ref(
            "batch_execution_ref",
            self.batch_execution_ref,
        )
        if batch_execution_ref is not None:
            validate_core_stable_ref(batch_execution_ref)
            validate_stable_ref_kind(batch_execution_ref, "batch", field_name="batch_execution_ref")

        operation_name = _normalize_component_name("operation_name", self.operation_name)
        observed_at = _normalize_timestamp_field("observed_at", self.observed_at)

        _assert_prefix_match(
            ref_value=stage_execution_ref.value,
            prefix_value=run_ref.value,
            field_name="stage_execution_ref",
        )
        if batch_execution_ref is not None:
            _assert_prefix_match(
                ref_value=batch_execution_ref.value,
                prefix_value=stage_execution_ref.value,
                field_name="batch_execution_ref",
            )
        owner_ref = batch_execution_ref if batch_execution_ref is not None else stage_execution_ref
        if operation_context_ref.value != f"{owner_ref.value}.{operation_name}":
            _raise_context_error(
                "operation_context_ref must equal owning scope ref + '.' + operation_name.",
                code="context_ref_prefix_mismatch",
                details={
                    "operation_context_ref": str(operation_context_ref),
                    "owner_ref": str(owner_ref),
                    "operation_name": operation_name,
                },
            )

        object.__setattr__(self, "operation_context_ref", operation_context_ref)
        object.__setattr__(self, "run_ref", run_ref)
        object.__setattr__(self, "stage_execution_ref", stage_execution_ref)
        object.__setattr__(self, "batch_execution_ref", batch_execution_ref)
        object.__setattr__(self, "operation_name", operation_name)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "schema_version", _normalize_required_string("schema_version", self.schema_version))
        object.__setattr__(self, "extensions", _normalize_extensions(self.extensions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_context_ref": str(self.operation_context_ref),
            "run_ref": str(self.run_ref),
            "stage_execution_ref": str(self.stage_execution_ref),
            "batch_execution_ref": None if self.batch_execution_ref is None else str(self.batch_execution_ref),
            "operation_name": self.operation_name,
            "observed_at": self.observed_at,
            "schema_version": self.schema_version,
            "extensions": _serialize_extensions(self.extensions),
        }


@dataclass(frozen=True, slots=True)
class EnvironmentSnapshot:
    """Canonical environment snapshot model."""

    environment_snapshot_ref: StableRef | str
    run_ref: StableRef | str
    captured_at: str | datetime
    python_version: str
    platform: str
    packages: Mapping[str, str] | None = None
    environment_variables: Mapping[str, str] | None = None
    schema_version: str = DEFAULT_CONTRACT_SCHEMA_VERSION
    extensions: tuple[ExtensionFieldSet, ...] = ()

    def __post_init__(self) -> None:
        environment_snapshot_ref = _coerce_ref("environment_snapshot_ref", self.environment_snapshot_ref)
        validate_stable_ref_kind(environment_snapshot_ref, "environment", field_name="environment_snapshot_ref")

        run_ref = _coerce_ref("run_ref", self.run_ref)
        validate_core_stable_ref(run_ref)
        validate_stable_ref_kind(run_ref, "run", field_name="run_ref")

        _assert_prefix_match(
            ref_value=environment_snapshot_ref.value,
            prefix_value=run_ref.value,
            field_name="environment_snapshot_ref",
        )
        if len(environment_snapshot_ref.components) != len(run_ref.components) + 1:
            _raise_context_error(
                "environment_snapshot_ref must add exactly one snapshot key to run_ref.",
                code="context_ref_prefix_mismatch",
                details={
                    "environment_snapshot_ref": str(environment_snapshot_ref),
                    "run_ref": str(run_ref),
                },
            )

        object.__setattr__(self, "environment_snapshot_ref", environment_snapshot_ref)
        object.__setattr__(self, "run_ref", run_ref)
        object.__setattr__(self, "captured_at", _normalize_timestamp_field("captured_at", self.captured_at))
        object.__setattr__(self, "python_version", _normalize_required_string("python_version", self.python_version))
        object.__setattr__(self, "platform", _normalize_required_string("platform", self.platform))
        object.__setattr__(self, "packages", _normalize_string_mapping("packages", self.packages))
        object.__setattr__(
            self,
            "environment_variables",
            _normalize_string_mapping("environment_variables", self.environment_variables),
        )
        object.__setattr__(self, "schema_version", _normalize_required_string("schema_version", self.schema_version))
        object.__setattr__(self, "extensions", _normalize_extensions(self.extensions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_snapshot_ref": str(self.environment_snapshot_ref),
            "run_ref": str(self.run_ref),
            "captured_at": self.captured_at,
            "python_version": self.python_version,
            "platform": self.platform,
            "packages": dict(self.packages),
            "environment_variables": dict(self.environment_variables),
            "schema_version": self.schema_version,
            "extensions": _serialize_extensions(self.extensions),
        }


__all__ = [
    "DEFAULT_CONTRACT_SCHEMA_VERSION",
    "BatchExecution",
    "DeploymentExecution",
    "EnvironmentSnapshot",
    "OperationContext",
    "Project",
    "RUN_STAGE_STATUSES",
    "Run",
    "SampleObservation",
    "StageExecution",
]
