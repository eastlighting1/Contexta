"""Internal runtime session and lifecycle state for Contexta."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from importlib.metadata import distributions
from platform import platform as detect_platform
from re import sub
import sys
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from ..common.errors import ClosedScopeError, LifecycleError
from ..common.time import iso_utc_now
from ..capture.artifacts import register_artifact, register_artifacts
from ..capture.dispatch import CaptureDispatcher
from ..capture.events import capture_event, emit_events
from ..capture.metrics import capture_metric, emit_metrics
from ..capture.traces import capture_span, emit_spans
from ..config import UnifiedConfig, config_to_mapping
from ..contract import (
    BatchExecution,
    DeploymentExecution,
    EnvironmentSnapshot,
    OperationContext,
    Project,
    Run,
    SampleObservation,
    StableRef,
    StageExecution,
)
from ..contract.refs import validate_core_stable_ref, validate_stable_ref_kind

if TYPE_CHECKING:
    from ..capture.results import BatchCaptureResult, CaptureResult


_TERMINAL_SCOPE_STATUSES = ("completed", "failed", "cancelled")
_COMPONENT_SANITIZE_PATTERN = r"[^a-z0-9]+"


def _normalize_required_text(field_name: str, value: str) -> str:
    if not isinstance(value, str):
        raise LifecycleError(
            f"{field_name} must be a string.",
            code="runtime_invalid_value",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    text = value.strip()
    if not text:
        raise LifecycleError(
            f"{field_name} must not be blank.",
            code="runtime_invalid_value",
            details={"field_name": field_name},
        )
    return text


def _normalize_component(field_name: str, value: str) -> str:
    text = _normalize_required_text(field_name, value).lower()
    canonical = sub(_COMPONENT_SANITIZE_PATTERN, "-", text).strip("-")
    if not canonical:
        raise LifecycleError(
            f"{field_name} must contain at least one alphanumeric character.",
            code="runtime_invalid_component",
            details={"field_name": field_name, "value": value},
        )
    return canonical


def _normalize_optional_text(field_name: str, value: str | None) -> str | None:
    if value is None:
        return None
    return _normalize_required_text(field_name, value)


def _normalize_string_mapping(field_name: str, mapping: Mapping[str, str] | None) -> dict[str, str]:
    if mapping is None:
        return {}
    if not isinstance(mapping, Mapping):
        raise LifecycleError(
            f"{field_name} must be a mapping.",
            code="runtime_invalid_mapping",
            details={"field_name": field_name, "type": type(mapping).__name__},
        )

    normalized: dict[str, str] = {}
    for key, value in mapping.items():
        key_text = _normalize_required_text(f"{field_name}.key", key)
        value_text = _normalize_required_text(f"{field_name}[{key_text!r}]", value)
        normalized[key_text] = value_text
    return {key: normalized[key] for key in sorted(normalized)}


def _normalize_any_mapping(field_name: str, mapping: Mapping[str, Any] | None) -> dict[str, Any]:
    if mapping is None:
        return {}
    if not isinstance(mapping, Mapping):
        raise LifecycleError(
            f"{field_name} must be a mapping.",
            code="runtime_invalid_mapping",
            details={"field_name": field_name, "type": type(mapping).__name__},
        )

    normalized: dict[str, Any] = {}
    for key, value in mapping.items():
        key_text = _normalize_required_text(f"{field_name}.key", key)
        normalized[key_text] = value
    return {key: normalized[key] for key in sorted(normalized)}


def _normalize_dataset_ref(value: StableRef | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, StableRef):
        return str(value)
    return _normalize_required_text("dataset_ref", value)


def _coerce_optional_exact_ref(
    raw: StableRef | str | None,
    *,
    expected_kind: str,
    expected_value: str,
    field_name: str,
) -> StableRef:
    if raw is None:
        return StableRef(expected_kind, expected_value)

    ref = raw if isinstance(raw, StableRef) else StableRef.parse(raw)
    validate_core_stable_ref(ref)
    validate_stable_ref_kind(ref, expected_kind, field_name=field_name)
    if ref.value != expected_value:
        raise LifecycleError(
            f"{field_name} must equal {expected_kind}:{expected_value}.",
            code="runtime_ref_mismatch",
            details={"field_name": field_name, "expected": f"{expected_kind}:{expected_value}", "actual": str(ref)},
        )
    return ref


@dataclass(frozen=True, slots=True)
class ActiveContext:
    """Resolved capture context for one task-local runtime state."""

    project_ref: StableRef
    run_ref: StableRef | None = None
    deployment_execution_ref: StableRef | None = None
    stage_execution_ref: StableRef | None = None
    batch_execution_ref: StableRef | None = None
    sample_observation_ref: StableRef | None = None
    operation_context_ref: StableRef | None = None

    @property
    def scope_kind(self) -> str:
        if self.operation_context_ref is not None:
            return "operation"
        if self.sample_observation_ref is not None:
            return "sample"
        if self.batch_execution_ref is not None:
            return "batch"
        if self.deployment_execution_ref is not None:
            return "deployment"
        if self.stage_execution_ref is not None:
            return "stage"
        if self.run_ref is not None:
            return "run"
        return "project"

    @property
    def ref(self) -> str:
        for candidate in (
            self.operation_context_ref,
            self.sample_observation_ref,
            self.batch_execution_ref,
            self.deployment_execution_ref,
            self.stage_execution_ref,
            self.run_ref,
            self.project_ref,
        ):
            if candidate is not None:
                return str(candidate)
        return str(self.project_ref)


@dataclass(frozen=True, slots=True)
class ContextState:
    """Task-local runtime lifecycle state."""

    current: ActiveContext
    run_scope: Any | None = None
    deployment_scope: Any | None = None
    stage_scope: Any | None = None
    batch_scope: Any | None = None
    sample_scope: Any | None = None
    operation_scope: Any | None = None


class RuntimeSession:
    """Internal session kernel that owns scope lifecycle and active context state."""

    def __init__(self, *, config: UnifiedConfig, dispatcher: CaptureDispatcher | None = None) -> None:
        self.config = config
        self._dispatcher = dispatcher or CaptureDispatcher.with_default_local_sink(config=config)
        self.project_name = _normalize_required_text("project_name", config.project_name)
        self.project_ref = StableRef("project", _normalize_component("project_name", config.project_name))
        self.project_anchor = Project(
            project_ref=self.project_ref,
            name=self.project_name,
            created_at=iso_utc_now(),
            schema_version=config.contract.schema_version,
        )
        self._idle_state = ContextState(current=ActiveContext(project_ref=self.project_ref))
        self._state_var: ContextVar[ContextState] = ContextVar(
            "contexta_runtime_state",
            default=self._idle_state,
        )

    def current_run(self) -> Any:
        state = self._state_var.get()
        if state.run_scope is None:
            raise LifecycleError(
                "No active run scope is available.",
                code="runtime_run_required",
            )
        return state.run_scope

    def current_stage(self) -> Any:
        state = self._state_var.get()
        if state.stage_scope is None:
            raise LifecycleError(
                "No active stage scope is available.",
                code="runtime_stage_required",
            )
        return state.stage_scope

    def current_deployment(self) -> Any:
        state = self._state_var.get()
        if state.deployment_scope is None:
            raise LifecycleError(
                "No active deployment scope is available.",
                code="runtime_deployment_required",
            )
        return state.deployment_scope

    def current_operation(self) -> Any:
        state = self._state_var.get()
        if state.operation_scope is None:
            raise LifecycleError(
                "No active operation scope is available.",
                code="runtime_operation_required",
            )
        return state.operation_scope

    def current_sample(self) -> Any:
        state = self._state_var.get()
        if state.sample_scope is None:
            raise LifecycleError(
                "No active sample scope is available.",
                code="runtime_sample_required",
            )
        return state.sample_scope

    def current_batch(self) -> Any:
        state = self._state_var.get()
        if state.batch_scope is None:
            raise LifecycleError(
                "No active batch scope is available.",
                code="runtime_batch_required",
            )
        return state.batch_scope

    def start_deployment(
        self,
        name: str,
        *,
        deployment_ref: StableRef | str | None = None,
        run_ref: StableRef | str | None = None,
        artifact_ref: StableRef | str | None = None,
        environment_snapshot_ref: StableRef | str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        state = self._state_var.get()
        if any(
            scope is not None
            for scope in (
                state.run_scope,
                state.deployment_scope,
                state.stage_scope,
                state.batch_scope,
                state.sample_scope,
                state.operation_scope,
            )
        ):
            raise LifecycleError(
                "Deployment scopes cannot be nested with active run or deployment scopes.",
                code="runtime_nested_deployment",
            )

        deployment_name = _normalize_component("deployment_name", name)
        expected_value = f"{self.project_ref.value}.{deployment_name}"
        deployment_execution_ref = _coerce_optional_exact_ref(
            deployment_ref,
            expected_kind="deployment",
            expected_value=expected_value,
            field_name="deployment_ref",
        )
        linked_run_ref = None
        if run_ref is not None:
            linked_run_ref = run_ref if isinstance(run_ref, StableRef) else StableRef.parse(run_ref)
            validate_core_stable_ref(linked_run_ref)
            validate_stable_ref_kind(linked_run_ref, "run", field_name="run_ref")
        linked_artifact_ref = None
        if artifact_ref is not None:
            linked_artifact_ref = artifact_ref if isinstance(artifact_ref, StableRef) else StableRef.parse(artifact_ref)
            validate_core_stable_ref(linked_artifact_ref)
            validate_stable_ref_kind(linked_artifact_ref, "artifact", field_name="artifact_ref")
        linked_environment_ref = None
        if environment_snapshot_ref is not None:
            linked_environment_ref = (
                environment_snapshot_ref
                if isinstance(environment_snapshot_ref, StableRef)
                else StableRef.parse(environment_snapshot_ref)
            )
            validate_stable_ref_kind(
                linked_environment_ref,
                "environment",
                field_name="environment_snapshot_ref",
            )

        deployment_model = DeploymentExecution(
            deployment_execution_ref=deployment_execution_ref,
            project_ref=self.project_ref,
            deployment_name=deployment_name,
            status="open",
            started_at=iso_utc_now(),
            order_index=0,
            run_ref=linked_run_ref,
            artifact_ref=linked_artifact_ref,
            environment_snapshot_ref=linked_environment_ref,
            schema_version=self.config.contract.schema_version,
        )

        from .scopes import DeploymentScope

        bound_context = ActiveContext(
            project_ref=self.project_ref,
            run_ref=linked_run_ref,
            deployment_execution_ref=deployment_execution_ref,
        )
        scope = DeploymentScope(
            session=self,
            bound_context=bound_context,
            deployment_model=deployment_model,
            order_index=0,
            metadata=_normalize_any_mapping("metadata", metadata),
        )
        token = self._state_var.set(ContextState(current=bound_context, deployment_scope=scope))
        scope._bind_state_token(token)
        return scope

    def start_run(
        self,
        name: str,
        *,
        run_id: str | None = None,
        tags: Mapping[str, str] | None = None,
        metadata: Mapping[str, Any] | None = None,
        code_revision: str | None = None,
        config_snapshot: Mapping[str, Any] | None = None,
        dataset_ref: StableRef | str | None = None,
    ) -> Any:
        state = self._state_var.get()
        if state.run_scope is not None:
            raise LifecycleError(
                "Nested run scopes are not allowed in one runtime session.",
                code="runtime_nested_run",
            )
        if state.deployment_scope is not None:
            raise LifecycleError(
                "Run scopes cannot be opened while a deployment scope is active.",
                code="runtime_nested_run",
            )

        started_at = iso_utc_now()
        canonical_run_id = _normalize_component("run_id", run_id or name)
        run_ref = StableRef("run", f"{self.project_ref.value}.{canonical_run_id}")
        inline_config_snapshot = (
            _normalize_any_mapping("config_snapshot", config_snapshot)
            if config_snapshot is not None
            else (
                config_to_mapping(self.config)
                if self.config.capture.capture_config_snapshot
                else None
            )
        )
        config_snapshot_ref = (
            StableRef("artifact", f"{run_ref.value}.config-snapshot")
            if inline_config_snapshot is not None
            else None
        )
        run_model = Run(
            run_ref=run_ref,
            project_ref=self.project_ref,
            name=_normalize_required_text("name", name),
            status="open",
            started_at=started_at,
            schema_version=self.config.contract.schema_version,
        )
        environment_snapshot = self._build_environment_snapshot(run_ref) if self.config.capture.capture_environment_snapshot else None

        from .scopes import RunScope

        bound_context = ActiveContext(project_ref=self.project_ref, run_ref=run_ref)
        run_scope = RunScope(
            session=self,
            bound_context=bound_context,
            run_model=run_model,
            run_id=canonical_run_id,
            code_revision=_normalize_optional_text("code_revision", code_revision),
            config_snapshot_ref=config_snapshot_ref,
            config_snapshot=inline_config_snapshot,
            dataset_ref=_normalize_dataset_ref(dataset_ref),
            tags=_normalize_string_mapping("tags", tags),
            metadata=_normalize_any_mapping("metadata", metadata),
            environment_snapshot=environment_snapshot,
        )
        token = self._state_var.set(ContextState(current=bound_context, run_scope=run_scope))
        run_scope._bind_state_token(token)
        return run_scope

    def start_stage(
        self,
        run_scope: Any,
        name: str,
        *,
        stage_ref: StableRef | str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        self._ensure_open_scope(run_scope, action="start a stage")
        state = self._state_var.get()
        if state.run_scope is not run_scope:
            raise LifecycleError(
                "A stage can only be opened from the active run scope.",
                code="runtime_inactive_run_scope",
            )
        if state.stage_scope is not None:
            raise LifecycleError(
                "Only one active stage is allowed per run.",
                code="runtime_stage_already_open",
                details={"active_stage_ref": state.stage_scope.ref},
            )

        stage_name = _normalize_component("stage_name", name)
        expected_value = f"{run_scope._run_model.run_ref.value}.{stage_name}"
        stage_execution_ref = _coerce_optional_exact_ref(
            stage_ref,
            expected_kind="stage",
            expected_value=expected_value,
            field_name="stage_ref",
        )
        order_index = run_scope._consume_stage_order()
        stage_model = StageExecution(
            stage_execution_ref=stage_execution_ref,
            run_ref=run_scope._run_model.run_ref,
            stage_name=stage_name,
            status="open",
            started_at=iso_utc_now(),
            order_index=order_index,
            schema_version=self.config.contract.schema_version,
        )

        from .scopes import StageScope

        bound_context = ActiveContext(
            project_ref=self.project_ref,
            run_ref=run_scope._run_model.run_ref,
            stage_execution_ref=stage_execution_ref,
        )
        scope = StageScope(
            session=self,
            bound_context=bound_context,
            stage_model=stage_model,
            order_index=order_index,
            metadata=_normalize_any_mapping("metadata", metadata),
        )
        token = self._state_var.set(
            ContextState(
                current=bound_context,
                run_scope=run_scope,
                stage_scope=scope,
            )
        )
        scope._bind_state_token(token)
        return scope

    def start_batch(
        self,
        stage_scope: Any,
        name: str,
        *,
        batch_ref: StableRef | str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        self._ensure_open_scope(stage_scope, action="start a batch")
        state = self._state_var.get()
        if state.stage_scope is not stage_scope:
            raise LifecycleError(
                "A batch can only be opened from the active stage scope.",
                code="runtime_inactive_stage_scope",
            )
        if state.batch_scope is not None:
            raise LifecycleError(
                "Only one active batch is allowed per stage.",
                code="runtime_batch_already_open",
                details={"active_batch_ref": state.batch_scope.ref},
            )

        batch_name = _normalize_component("batch_name", name)
        expected_value = f"{stage_scope._stage_model.stage_execution_ref.value}.{batch_name}"
        batch_execution_ref = _coerce_optional_exact_ref(
            batch_ref,
            expected_kind="batch",
            expected_value=expected_value,
            field_name="batch_ref",
        )
        order_index = stage_scope._consume_batch_order()
        batch_model = BatchExecution(
            batch_execution_ref=batch_execution_ref,
            run_ref=stage_scope._stage_model.run_ref,
            stage_execution_ref=stage_scope._stage_model.stage_execution_ref,
            batch_name=batch_name,
            status="open",
            started_at=iso_utc_now(),
            order_index=order_index,
            schema_version=self.config.contract.schema_version,
        )

        from .scopes import BatchScope

        bound_context = ActiveContext(
            project_ref=self.project_ref,
            run_ref=stage_scope._stage_model.run_ref,
            stage_execution_ref=stage_scope._stage_model.stage_execution_ref,
            batch_execution_ref=batch_execution_ref,
        )
        scope = BatchScope(
            session=self,
            bound_context=bound_context,
            batch_model=batch_model,
            order_index=order_index,
            metadata=_normalize_any_mapping("metadata", metadata),
        )
        token = self._state_var.set(
            ContextState(
                current=bound_context,
                run_scope=state.run_scope,
                stage_scope=stage_scope,
                batch_scope=scope,
            )
        )
        scope._bind_state_token(token)
        return scope

    def start_sample(
        self,
        owner_scope: Any,
        name: str,
        *,
        sample_ref: StableRef | str | None = None,
        retention_class: str | None = None,
        redaction_profile: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        self._ensure_open_scope(owner_scope, action="start a sample")
        state = self._state_var.get()
        active_owner = state.batch_scope if state.batch_scope is not None else state.stage_scope
        if active_owner is not owner_scope:
            raise LifecycleError(
                "A sample can only be opened from the active stage or batch scope.",
                code="runtime_inactive_sample_owner_scope",
            )
        if state.sample_scope is not None:
            raise LifecycleError(
                "Only one active sample is allowed per owner scope.",
                code="runtime_sample_already_open",
                details={"active_sample_ref": state.sample_scope.ref},
            )
        if state.operation_scope is not None:
            raise LifecycleError(
                "Sample scopes cannot be opened while an operation scope is active.",
                code="runtime_sample_blocked_by_operation",
            )

        sample_name = _normalize_component("sample_name", name)
        if getattr(owner_scope, "scope_kind", None) == "batch":
            stage_model = owner_scope._stage_model
            batch_model = owner_scope._batch_model
            owner_ref = batch_model.batch_execution_ref
        else:
            stage_model = owner_scope._stage_model
            batch_model = None
            owner_ref = stage_model.stage_execution_ref
        expected_value = f"{owner_ref.value}.{sample_name}"
        sample_observation_ref = _coerce_optional_exact_ref(
            sample_ref,
            expected_kind="sample",
            expected_value=expected_value,
            field_name="sample_ref",
        )
        sample_model = SampleObservation(
            sample_observation_ref=sample_observation_ref,
            run_ref=stage_model.run_ref,
            stage_execution_ref=stage_model.stage_execution_ref,
            batch_execution_ref=None if batch_model is None else batch_model.batch_execution_ref,
            sample_name=sample_name,
            observed_at=iso_utc_now(),
            retention_class=retention_class,
            redaction_profile=redaction_profile,
            schema_version=self.config.contract.schema_version,
        )

        from .scopes import SampleScope

        bound_context = ActiveContext(
            project_ref=self.project_ref,
            run_ref=stage_model.run_ref,
            stage_execution_ref=stage_model.stage_execution_ref,
            batch_execution_ref=None if batch_model is None else batch_model.batch_execution_ref,
            sample_observation_ref=sample_observation_ref,
        )
        scope = SampleScope(
            session=self,
            bound_context=bound_context,
            sample_model=sample_model,
            metadata=_normalize_any_mapping("metadata", metadata),
        )
        token = self._state_var.set(
            ContextState(
                current=bound_context,
                run_scope=state.run_scope,
                stage_scope=state.stage_scope,
                batch_scope=state.batch_scope,
                sample_scope=scope,
            )
        )
        scope._bind_state_token(token)
        return scope

    def start_operation(
        self,
        owner_scope: Any,
        name: str,
        *,
        operation_ref: StableRef | str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        self._ensure_open_scope(owner_scope, action="start an operation")
        state = self._state_var.get()
        if state.sample_scope is not None:
            raise LifecycleError(
                "Operations cannot be opened while a sample scope is active.",
                code="runtime_operation_blocked_by_sample",
            )
        active_owner = state.batch_scope if state.batch_scope is not None else state.stage_scope
        if active_owner is not owner_scope:
            raise LifecycleError(
                "An operation can only be opened from the active stage or batch scope.",
                code="runtime_inactive_operation_owner_scope",
            )
        if state.operation_scope is not None:
            raise LifecycleError(
                "Only one active operation is allowed per stage.",
                code="runtime_operation_already_open",
                details={"active_operation_ref": state.operation_scope.ref},
            )

        operation_name = _normalize_component("operation_name", name)
        if getattr(owner_scope, "scope_kind", None) == "batch":
            stage_model = owner_scope._stage_model
            batch_model = owner_scope._batch_model
            owner_ref = batch_model.batch_execution_ref
        else:
            stage_model = owner_scope._stage_model
            batch_model = None
            owner_ref = stage_model.stage_execution_ref
        expected_value = f"{owner_ref.value}.{operation_name}"
        operation_context_ref = _coerce_optional_exact_ref(
            operation_ref,
            expected_kind="op",
            expected_value=expected_value,
            field_name="operation_ref",
        )
        observed_at = iso_utc_now()
        operation_context = OperationContext(
            operation_context_ref=operation_context_ref,
            run_ref=stage_model.run_ref,
            stage_execution_ref=stage_model.stage_execution_ref,
            batch_execution_ref=None if batch_model is None else batch_model.batch_execution_ref,
            operation_name=operation_name,
            observed_at=observed_at,
            schema_version=self.config.contract.schema_version,
        )

        from .scopes import OperationScope

        bound_context = ActiveContext(
            project_ref=self.project_ref,
            run_ref=stage_model.run_ref,
            stage_execution_ref=stage_model.stage_execution_ref,
            batch_execution_ref=None if batch_model is None else batch_model.batch_execution_ref,
            operation_context_ref=operation_context_ref,
        )
        scope = OperationScope(
            session=self,
            bound_context=bound_context,
            operation_context=operation_context,
            metadata=_normalize_any_mapping("metadata", metadata),
        )
        token = self._state_var.set(
            ContextState(
                current=bound_context,
                run_scope=state.run_scope,
                stage_scope=state.stage_scope,
                batch_scope=state.batch_scope,
                sample_scope=state.sample_scope,
                operation_scope=scope,
            )
        )
        scope._bind_state_token(token)
        return scope

    def close_run(self, run_scope: Any, *, status: str = "completed") -> None:
        terminal_status = self._normalize_terminal_status(status)
        self._ensure_scope_can_close(run_scope, expected_kind="run")

        state = self._state_var.get()
        if state.operation_scope is not None:
            self.close_operation(state.operation_scope, status=terminal_status)
            state = self._state_var.get()
        if state.sample_scope is not None:
            self.close_sample(state.sample_scope, status=terminal_status)
            state = self._state_var.get()
        if state.batch_scope is not None:
            self.close_batch(state.batch_scope, status=terminal_status)
            state = self._state_var.get()
        if state.stage_scope is not None:
            self.close_stage(state.stage_scope, status=terminal_status)

        state = self._state_var.get()
        if state.run_scope is not run_scope:
            raise LifecycleError(
                "Run scope is not active in this runtime session.",
                code="runtime_inactive_run_scope",
            )

        closed_at = iso_utc_now()
        run_scope._run_model = Run(
            run_ref=run_scope._run_model.run_ref,
            project_ref=run_scope._run_model.project_ref,
            name=run_scope._run_model.name,
            status=terminal_status,
            started_at=run_scope._run_model.started_at,
            ended_at=closed_at,
            description=run_scope._run_model.description,
            schema_version=run_scope._run_model.schema_version,
            extensions=run_scope._run_model.extensions,
        )
        token = run_scope._pop_state_token()
        self._state_var.reset(token)
        run_scope._mark_closed(status=terminal_status, closed_at=closed_at)

    def close_deployment(self, deployment_scope: Any, *, status: str = "completed") -> None:
        terminal_status = self._normalize_terminal_status(status)
        self._ensure_scope_can_close(deployment_scope, expected_kind="deployment")

        state = self._state_var.get()
        if state.deployment_scope is not deployment_scope:
            raise LifecycleError(
                "Deployment scope is not active in this runtime session.",
                code="runtime_inactive_deployment_scope",
            )

        closed_at = iso_utc_now()
        deployment_scope._deployment_model = DeploymentExecution(
            deployment_execution_ref=deployment_scope._deployment_model.deployment_execution_ref,
            project_ref=deployment_scope._deployment_model.project_ref,
            deployment_name=deployment_scope._deployment_model.deployment_name,
            status=terminal_status,
            started_at=deployment_scope._deployment_model.started_at,
            ended_at=closed_at,
            order_index=deployment_scope._deployment_model.order_index,
            run_ref=deployment_scope._deployment_model.run_ref,
            artifact_ref=deployment_scope._deployment_model.artifact_ref,
            environment_snapshot_ref=deployment_scope._deployment_model.environment_snapshot_ref,
            schema_version=deployment_scope._deployment_model.schema_version,
            extensions=deployment_scope._deployment_model.extensions,
        )
        token = deployment_scope._pop_state_token()
        self._state_var.reset(token)
        deployment_scope._mark_closed(status=terminal_status, closed_at=closed_at)

    def close_stage(self, stage_scope: Any, *, status: str = "completed") -> None:
        terminal_status = self._normalize_terminal_status(status)
        self._ensure_scope_can_close(stage_scope, expected_kind="stage")

        state = self._state_var.get()
        if state.operation_scope is not None:
            self.close_operation(state.operation_scope, status=terminal_status)
            state = self._state_var.get()
        if state.sample_scope is not None:
            self.close_sample(state.sample_scope, status=terminal_status)
            state = self._state_var.get()
        if state.batch_scope is not None:
            self.close_batch(state.batch_scope, status=terminal_status)
            state = self._state_var.get()
        if state.stage_scope is not stage_scope:
            raise LifecycleError(
                "Stage scope is not active in this runtime session.",
                code="runtime_inactive_stage_scope",
            )

        closed_at = iso_utc_now()
        stage_scope._stage_model = StageExecution(
            stage_execution_ref=stage_scope._stage_model.stage_execution_ref,
            run_ref=stage_scope._stage_model.run_ref,
            stage_name=stage_scope._stage_model.stage_name,
            status=terminal_status,
            started_at=stage_scope._stage_model.started_at,
            ended_at=closed_at,
            order_index=stage_scope._stage_model.order_index,
            schema_version=stage_scope._stage_model.schema_version,
            extensions=stage_scope._stage_model.extensions,
        )
        token = stage_scope._pop_state_token()
        self._state_var.reset(token)
        stage_scope._mark_closed(status=terminal_status, closed_at=closed_at)

    def close_batch(self, batch_scope: Any, *, status: str = "completed") -> None:
        terminal_status = self._normalize_terminal_status(status)
        self._ensure_scope_can_close(batch_scope, expected_kind="batch")

        state = self._state_var.get()
        if state.operation_scope is not None:
            self.close_operation(state.operation_scope, status=terminal_status)
            state = self._state_var.get()
        if state.sample_scope is not None:
            self.close_sample(state.sample_scope, status=terminal_status)
            state = self._state_var.get()
        if state.batch_scope is not batch_scope:
            raise LifecycleError(
                "Batch scope is not active in this runtime session.",
                code="runtime_inactive_batch_scope",
            )

        closed_at = iso_utc_now()
        batch_scope._batch_model = BatchExecution(
            batch_execution_ref=batch_scope._batch_model.batch_execution_ref,
            run_ref=batch_scope._batch_model.run_ref,
            stage_execution_ref=batch_scope._batch_model.stage_execution_ref,
            batch_name=batch_scope._batch_model.batch_name,
            status=terminal_status,
            started_at=batch_scope._batch_model.started_at,
            ended_at=closed_at,
            order_index=batch_scope._batch_model.order_index,
            schema_version=batch_scope._batch_model.schema_version,
            extensions=batch_scope._batch_model.extensions,
        )
        token = batch_scope._pop_state_token()
        self._state_var.reset(token)
        batch_scope._mark_closed(status=terminal_status, closed_at=closed_at)

    def close_operation(self, operation_scope: Any, *, status: str = "completed") -> None:
        terminal_status = self._normalize_terminal_status(status)
        self._ensure_scope_can_close(operation_scope, expected_kind="operation")

        state = self._state_var.get()
        if state.operation_scope is not operation_scope:
            raise LifecycleError(
                "Operation scope is not active in this runtime session.",
                code="runtime_inactive_operation_scope",
            )

        closed_at = iso_utc_now()
        token = operation_scope._pop_state_token()
        self._state_var.reset(token)
        operation_scope._mark_closed(status=terminal_status, closed_at=closed_at)

    def close_sample(self, sample_scope: Any, *, status: str = "completed") -> None:
        terminal_status = self._normalize_terminal_status(status)
        self._ensure_scope_can_close(sample_scope, expected_kind="sample")

        state = self._state_var.get()
        if state.sample_scope is not sample_scope:
            raise LifecycleError(
                "Sample scope is not active in this runtime session.",
                code="runtime_inactive_sample_scope",
            )

        closed_at = iso_utc_now()
        token = sample_scope._pop_state_token()
        self._state_var.reset(token)
        sample_scope._mark_closed(status=terminal_status, closed_at=closed_at)

    def event(
        self,
        key: str,
        *,
        message: str,
        level: str = "info",
        attributes: Mapping[str, Any] | None = None,
        tags: Mapping[str, str] | None = None,
        _context: ActiveContext | None = None,
    ) -> "CaptureResult":
        context = self._resolve_capture_context(_context)
        prepared = capture_event(
            config=self.config,
            context=context,
            key=key,
            message=message,
            level=level,
            attributes=attributes,
            tags=tags,
        )
        return self._dispatcher.dispatch_capture(prepared)

    def emit_events(self, emissions: Sequence[Any], *, _context: ActiveContext | None = None) -> "BatchCaptureResult":
        context = self._resolve_capture_context(_context)
        prepared = emit_events(config=self.config, context=context, emissions=emissions)
        return self._dispatcher.dispatch_batch(prepared)

    def metric(
        self,
        key: str,
        value: Any,
        *,
        unit: str | None = None,
        aggregation_scope: str = "step",
        tags: Mapping[str, str] | None = None,
        summary_basis: str = "raw_observation",
        _context: ActiveContext | None = None,
    ) -> "CaptureResult":
        context = self._resolve_capture_context(_context)
        prepared = capture_metric(
            config=self.config,
            context=context,
            key=key,
            value=value,
            unit=unit,
            aggregation_scope=aggregation_scope,
            tags=tags,
            summary_basis=summary_basis,
        )
        return self._dispatcher.dispatch_capture(prepared)

    def emit_metrics(self, emissions: Sequence[Any], *, _context: ActiveContext | None = None) -> "BatchCaptureResult":
        context = self._resolve_capture_context(_context)
        prepared = emit_metrics(config=self.config, context=context, emissions=emissions)
        return self._dispatcher.dispatch_batch(prepared)

    def span(
        self,
        name: str,
        *,
        started_at: str | None = None,
        ended_at: str | None = None,
        status: str = "ok",
        span_kind: str = "operation",
        attributes: Mapping[str, Any] | None = None,
        linked_refs: Sequence[str] | None = None,
        parent_span_id: str | None = None,
        _context: ActiveContext | None = None,
    ) -> "CaptureResult":
        context = self._resolve_capture_context(_context)
        prepared = capture_span(
            config=self.config,
            context=context,
            name=name,
            started_at=started_at,
            ended_at=ended_at,
            status=status,
            span_kind=span_kind,
            attributes=attributes,
            linked_refs=linked_refs,
            parent_span_id=parent_span_id,
        )
        return self._dispatcher.dispatch_capture(prepared)

    def emit_spans(self, emissions: Sequence[Any], *, _context: ActiveContext | None = None) -> "BatchCaptureResult":
        context = self._resolve_capture_context(_context)
        prepared = emit_spans(config=self.config, context=context, emissions=emissions)
        return self._dispatcher.dispatch_batch(prepared)

    def register_artifact(
        self,
        artifact_kind: str,
        path: str,
        *,
        artifact_ref: StableRef | str | None = None,
        attributes: Mapping[str, Any] | None = None,
        compute_hash: bool = True,
        allow_missing: bool = False,
        _context: ActiveContext | None = None,
    ) -> "CaptureResult":
        context = self._resolve_capture_context(_context)
        prepared = register_artifact(
            config=self.config,
            context=context,
            artifact_kind=artifact_kind,
            path=path,
            artifact_ref=artifact_ref,
            attributes=attributes,
            compute_hash=compute_hash,
            allow_missing=allow_missing,
        )
        return self._dispatcher.dispatch_capture(prepared)

    def register_artifacts(self, emissions: Sequence[Any], *, _context: ActiveContext | None = None) -> "BatchCaptureResult":
        context = self._resolve_capture_context(_context)
        prepared = register_artifacts(config=self.config, context=context, emissions=emissions)
        return self._dispatcher.dispatch_batch(prepared)

    def _resolve_capture_context(self, bound_context: ActiveContext | None) -> ActiveContext:
        if bound_context is not None:
            return bound_context

        state = self._state_var.get()
        if state.run_scope is None:
            raise LifecycleError(
                "Capture requires an active run scope.",
                code="runtime_capture_requires_run",
            )
        return state.current

    def _build_environment_snapshot(self, run_ref: StableRef) -> EnvironmentSnapshot:
        packages: dict[str, str] = {}
        if self.config.capture.capture_installed_packages:
            discovered: dict[str, str] = {}
            for distribution in distributions():
                name = distribution.metadata.get("Name")
                if not name:
                    continue
                discovered[name] = distribution.version
            packages = {key: discovered[key] for key in sorted(discovered)}

        return EnvironmentSnapshot(
            environment_snapshot_ref=StableRef("environment", f"{run_ref.value}.runtime"),
            run_ref=run_ref,
            captured_at=iso_utc_now(),
            python_version=sys.version.split()[0],
            platform=detect_platform(),
            packages=packages,
            environment_variables={},
            schema_version=self.config.contract.schema_version,
        )

    def _normalize_terminal_status(self, status: str) -> str:
        value = _normalize_required_text("status", status).lower()
        if value not in _TERMINAL_SCOPE_STATUSES:
            raise LifecycleError(
                "Scope close status must be one of completed/failed/cancelled.",
                code="runtime_invalid_close_status",
                details={"status": status, "allowed": _TERMINAL_SCOPE_STATUSES},
            )
        return value

    def _ensure_open_scope(self, scope: Any, *, action: str) -> None:
        if scope.is_closed:
            raise ClosedScopeError(
                f"Cannot {action} from a closed {scope.scope_kind} scope.",
                code="runtime_scope_closed",
                details={"scope_kind": scope.scope_kind, "ref": scope.ref},
            )

    def _ensure_scope_can_close(self, scope: Any, *, expected_kind: str) -> None:
        if scope.scope_kind != expected_kind:
            raise LifecycleError(
                f"Expected a {expected_kind} scope, got {scope.scope_kind}.",
                code="runtime_scope_kind_mismatch",
                details={"expected_kind": expected_kind, "actual_kind": scope.scope_kind},
            )
        if scope.is_closed:
            raise ClosedScopeError(
                f"{expected_kind.title()} scope is already closed.",
                code="runtime_scope_closed",
                details={"scope_kind": expected_kind, "ref": scope.ref},
            )


__all__ = ["ActiveContext", "ContextState", "RuntimeSession"]
