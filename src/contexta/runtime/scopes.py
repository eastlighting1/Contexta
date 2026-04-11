"""Public scope implementations backed by the internal runtime session."""

from __future__ import annotations

from contextvars import Token
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from ..common.errors import ClosedScopeError, LifecycleError
from ..contract import StableRef

if TYPE_CHECKING:
    from .session import ActiveContext, ContextState, RuntimeSession


def _freeze_mapping(values: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not values:
        return MappingProxyType({})
    return MappingProxyType({key: values[key] for key in sorted(values)})


class BaseScope:
    """Common lifecycle and bound-context behavior for runtime scopes."""

    scope_kind = "base"

    def __init__(
        self,
        *,
        session: RuntimeSession,
        bound_context: ActiveContext,
        ref: StableRef,
        name: str,
        started_at: str,
    ) -> None:
        self._session = session
        self._bound_context = bound_context
        self._ref_obj = ref
        self._name = name
        self._started_at = started_at
        self._closed_at: str | None = None
        self._status = "open"
        self._state_token: Token[ContextState] | None = None

    @property
    def ref(self) -> str:
        return str(self._ref_obj)

    @property
    def name(self) -> str:
        return self._name

    @property
    def started_at(self) -> str:
        return self._started_at

    @property
    def closed_at(self) -> str | None:
        return self._closed_at

    @property
    def status(self) -> str:
        return self._status

    @property
    def is_closed(self) -> bool:
        return self._closed_at is not None

    def close(self, *, status: str = "completed") -> None:
        raise NotImplementedError

    def event(
        self,
        key: str,
        *,
        message: str,
        level: str = "info",
        attributes: Mapping[str, Any] | None = None,
        tags: Mapping[str, str] | None = None,
    ) -> Any:
        self._ensure_capture_allowed("event")
        return self._session.event(
            key,
            message=message,
            level=level,
            attributes=attributes,
            tags=tags,
            _context=self._bound_context,
        )

    def emit_events(self, emissions: Sequence[Any]) -> Any:
        self._ensure_capture_allowed("emit_events")
        return self._session.emit_events(emissions, _context=self._bound_context)

    def metric(
        self,
        key: str,
        value: Any,
        *,
        unit: str | None = None,
        aggregation_scope: str = "step",
        tags: Mapping[str, str] | None = None,
        summary_basis: str = "raw_observation",
    ) -> Any:
        self._ensure_capture_allowed("metric")
        return self._session.metric(
            key,
            value,
            unit=unit,
            aggregation_scope=aggregation_scope,
            tags=tags,
            summary_basis=summary_basis,
            _context=self._bound_context,
        )

    def emit_metrics(self, emissions: Sequence[Any]) -> Any:
        self._ensure_capture_allowed("emit_metrics")
        return self._session.emit_metrics(emissions, _context=self._bound_context)

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
    ) -> Any:
        self._ensure_capture_allowed("span")
        return self._session.span(
            name,
            started_at=started_at,
            ended_at=ended_at,
            status=status,
            span_kind=span_kind,
            attributes=attributes,
            linked_refs=linked_refs,
            parent_span_id=parent_span_id,
            _context=self._bound_context,
        )

    def emit_spans(self, emissions: Sequence[Any]) -> Any:
        self._ensure_capture_allowed("emit_spans")
        return self._session.emit_spans(emissions, _context=self._bound_context)

    def register_artifact(
        self,
        artifact_kind: str,
        path: str,
        *,
        artifact_ref: StableRef | str | None = None,
        attributes: Mapping[str, Any] | None = None,
        compute_hash: bool = True,
        allow_missing: bool = False,
    ) -> Any:
        self._ensure_capture_allowed("register_artifact")
        return self._session.register_artifact(
            artifact_kind,
            path,
            artifact_ref=artifact_ref,
            attributes=attributes,
            compute_hash=compute_hash,
            allow_missing=allow_missing,
            _context=self._bound_context,
        )

    def register_artifacts(self, emissions: Sequence[Any]) -> Any:
        self._ensure_capture_allowed("register_artifacts")
        return self._session.register_artifacts(emissions, _context=self._bound_context)

    def __enter__(self) -> "BaseScope":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> bool:
        if not self.is_closed:
            self.close(status="failed" if exc_type is not None else "completed")
        return False

    def _bind_state_token(self, token: Token[ContextState]) -> None:
        self._state_token = token

    def _pop_state_token(self) -> Token[ContextState]:
        if self._state_token is None:
            raise LifecycleError(
                "Scope has no active runtime state token.",
                code="runtime_scope_not_entered",
                details={"scope_kind": self.scope_kind, "ref": self.ref},
            )
        token = self._state_token
        self._state_token = None
        return token

    def _mark_closed(self, *, status: str, closed_at: str) -> None:
        self._status = status
        self._closed_at = closed_at

    def _ensure_capture_allowed(self, action: str) -> None:
        if self.is_closed:
            raise ClosedScopeError(
                f"Cannot {action} on a closed {self.scope_kind} scope.",
                code="runtime_scope_closed",
                details={"scope_kind": self.scope_kind, "ref": self.ref},
            )


class RunScope(BaseScope):
    """Run-bound scope surface."""

    scope_kind = "run"

    def __init__(
        self,
        *,
        session: RuntimeSession,
        bound_context: ActiveContext,
        run_model: Any,
        run_id: str,
        code_revision: str | None,
        config_snapshot_ref: StableRef | None,
        config_snapshot: Mapping[str, Any] | None,
        dataset_ref: str | None,
        tags: Mapping[str, str] | None,
        metadata: Mapping[str, Any] | None,
        environment_snapshot: Any | None,
    ) -> None:
        super().__init__(
            session=session,
            bound_context=bound_context,
            ref=run_model.run_ref,
            name=run_model.name,
            started_at=run_model.started_at,
        )
        self._run_model = run_model
        self._run_id = run_id
        self._code_revision = code_revision
        self._config_snapshot_ref = config_snapshot_ref
        self._config_snapshot = _freeze_mapping(config_snapshot)
        self._dataset_ref = dataset_ref
        self._tags = _freeze_mapping(tags)
        self._metadata = _freeze_mapping(metadata)
        self._environment_snapshot = environment_snapshot
        self._next_stage_order = 0

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def code_revision(self) -> str | None:
        return self._code_revision

    @property
    def config_snapshot_ref(self) -> str | None:
        if self._config_snapshot_ref is None:
            return None
        return str(self._config_snapshot_ref)

    @property
    def config_snapshot(self) -> Mapping[str, Any]:
        return self._config_snapshot

    @property
    def dataset_ref(self) -> str | None:
        return self._dataset_ref

    @property
    def tags(self) -> Mapping[str, Any]:
        return self._tags

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self._metadata

    def stage(
        self,
        name: str,
        *,
        stage_ref: StableRef | str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "StageScope":
        self._ensure_capture_allowed("open a stage")
        return self._session.start_stage(self, name, stage_ref=stage_ref, metadata=metadata)

    def close(self, *, status: str = "completed") -> None:
        self._session.close_run(self, status=status)

    def _consume_stage_order(self) -> int:
        order_index = self._next_stage_order
        self._next_stage_order += 1
        return order_index


class DeploymentScope(BaseScope):
    """Deployment-bound scope surface."""

    scope_kind = "deployment"

    def __init__(
        self,
        *,
        session: RuntimeSession,
        bound_context: ActiveContext,
        deployment_model: Any,
        order_index: int,
        metadata: Mapping[str, Any] | None,
    ) -> None:
        super().__init__(
            session=session,
            bound_context=bound_context,
            ref=deployment_model.deployment_execution_ref,
            name=deployment_model.deployment_name,
            started_at=deployment_model.started_at,
        )
        self._deployment_model = deployment_model
        self._order_index = order_index
        self._metadata = _freeze_mapping(metadata)

    @property
    def order_index(self) -> int:
        return self._order_index

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self._metadata

    def close(self, *, status: str = "completed") -> None:
        self._session.close_deployment(self, status=status)


class StageScope(BaseScope):
    """Stage-bound scope surface."""

    scope_kind = "stage"

    def __init__(
        self,
        *,
        session: RuntimeSession,
        bound_context: ActiveContext,
        stage_model: Any,
        order_index: int,
        metadata: Mapping[str, Any] | None,
    ) -> None:
        super().__init__(
            session=session,
            bound_context=bound_context,
            ref=stage_model.stage_execution_ref,
            name=stage_model.stage_name,
            started_at=stage_model.started_at,
        )
        self._stage_model = stage_model
        self._order_index = order_index
        self._metadata = _freeze_mapping(metadata)
        self._next_batch_order = 0

    @property
    def order_index(self) -> int:
        return self._order_index

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self._metadata

    def operation(
        self,
        name: str,
        *,
        operation_ref: StableRef | str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "OperationScope":
        self._ensure_capture_allowed("open an operation")
        return self._session.start_operation(self, name, operation_ref=operation_ref, metadata=metadata)

    def batch(
        self,
        name: str,
        *,
        batch_ref: StableRef | str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "BatchScope":
        self._ensure_capture_allowed("open a batch")
        return self._session.start_batch(self, name, batch_ref=batch_ref, metadata=metadata)

    def sample(
        self,
        name: str,
        *,
        sample_ref: StableRef | str | None = None,
        retention_class: str | None = None,
        redaction_profile: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "SampleScope":
        self._ensure_capture_allowed("open a sample")
        return self._session.start_sample(
            self,
            name,
            sample_ref=sample_ref,
            retention_class=retention_class,
            redaction_profile=redaction_profile,
            metadata=metadata,
        )

    def close(self, *, status: str = "completed") -> None:
        self._session.close_stage(self, status=status)

    def _consume_batch_order(self) -> int:
        order_index = self._next_batch_order
        self._next_batch_order += 1
        return order_index


class BatchScope(BaseScope):
    """Batch-bound scope surface."""

    scope_kind = "batch"

    def __init__(
        self,
        *,
        session: RuntimeSession,
        bound_context: ActiveContext,
        batch_model: Any,
        order_index: int,
        metadata: Mapping[str, Any] | None,
    ) -> None:
        super().__init__(
            session=session,
            bound_context=bound_context,
            ref=batch_model.batch_execution_ref,
            name=batch_model.batch_name,
            started_at=batch_model.started_at,
        )
        self._batch_model = batch_model
        self._stage_model = type("_BatchStageView", (), {
            "run_ref": batch_model.run_ref,
            "stage_execution_ref": batch_model.stage_execution_ref,
        })()
        self._order_index = order_index
        self._metadata = _freeze_mapping(metadata)

    @property
    def order_index(self) -> int:
        return self._order_index

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self._metadata

    def operation(
        self,
        name: str,
        *,
        operation_ref: StableRef | str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "OperationScope":
        self._ensure_capture_allowed("open an operation")
        return self._session.start_operation(self, name, operation_ref=operation_ref, metadata=metadata)

    def sample(
        self,
        name: str,
        *,
        sample_ref: StableRef | str | None = None,
        retention_class: str | None = None,
        redaction_profile: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "SampleScope":
        self._ensure_capture_allowed("open a sample")
        return self._session.start_sample(
            self,
            name,
            sample_ref=sample_ref,
            retention_class=retention_class,
            redaction_profile=redaction_profile,
            metadata=metadata,
        )

    def close(self, *, status: str = "completed") -> None:
        self._session.close_batch(self, status=status)


class OperationScope(BaseScope):
    """Operation-bound scope surface."""

    scope_kind = "operation"

    def __init__(
        self,
        *,
        session: RuntimeSession,
        bound_context: ActiveContext,
        operation_context: Any,
        metadata: Mapping[str, Any] | None,
    ) -> None:
        super().__init__(
            session=session,
            bound_context=bound_context,
            ref=operation_context.operation_context_ref,
            name=operation_context.operation_name,
            started_at=operation_context.observed_at,
        )
        self._operation_context = operation_context
        self._metadata = _freeze_mapping(metadata)

    @property
    def observed_at(self) -> str:
        return self._operation_context.observed_at

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self._metadata

    def close(self, *, status: str = "completed") -> None:
        self._session.close_operation(self, status=status)


class SampleScope(BaseScope):
    """Sample-bound scope surface."""

    scope_kind = "sample"

    def __init__(
        self,
        *,
        session: RuntimeSession,
        bound_context: ActiveContext,
        sample_model: Any,
        metadata: Mapping[str, Any] | None,
    ) -> None:
        super().__init__(
            session=session,
            bound_context=bound_context,
            ref=sample_model.sample_observation_ref,
            name=sample_model.sample_name,
            started_at=sample_model.observed_at,
        )
        self._sample_model = sample_model
        self._metadata = _freeze_mapping(metadata)

    @property
    def observed_at(self) -> str:
        return self._sample_model.observed_at

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self._metadata

    def close(self, *, status: str = "completed") -> None:
        self._session.close_sample(self, status=status)


__all__ = ["BaseScope", "BatchScope", "DeploymentScope", "OperationScope", "RunScope", "SampleScope", "StageScope"]
