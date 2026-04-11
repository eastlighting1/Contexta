"""Internal helpers shared by capture service modules."""

from __future__ import annotations

from re import sub
from typing import TYPE_CHECKING, Any, Mapping
from uuid import uuid4

from ..common.errors import ValidationError
from ..common.time import iso_utc_now
from ..contract import CorrelationRefs, RecordEnvelope, StableRef

if TYPE_CHECKING:
    from ..config import UnifiedConfig
    from ..runtime.session import ActiveContext


_KEBAB_SANITIZE_PATTERN = r"[^a-z0-9]+"


def _normalize_nonblank_string(field_name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(
            f"{field_name} must be a string.",
            code="capture_invalid_value",
            details={"field_name": field_name, "type": type(value).__name__},
        )
    text = value.strip()
    if not text:
        raise ValidationError(
            f"{field_name} must not be blank.",
            code="capture_invalid_value",
            details={"field_name": field_name},
        )
    return text


def _to_kebab(value: str) -> str:
    canonical = sub(_KEBAB_SANITIZE_PATTERN, "-", value.strip().lower()).strip("-")
    if not canonical:
        raise ValidationError(
            "Value must contain at least one alphanumeric character.",
            code="capture_invalid_component",
            details={"value": value},
        )
    return canonical


def subject_ref_text(context: "ActiveContext") -> str:
    """Return the deepest active subject ref text for the current context."""

    for candidate in (
        context.operation_context_ref,
        context.sample_observation_ref,
        context.batch_execution_ref,
        context.deployment_execution_ref,
        context.stage_execution_ref,
        context.run_ref,
    ):
        if candidate is not None:
            return str(candidate)
    return str(context.project_ref)


def make_record_ref(run_ref: StableRef, family_prefix: str) -> StableRef:
    """Return a session-local record ref for one run."""

    token = f"{_to_kebab(family_prefix)}-{uuid4().hex[:12]}"
    return StableRef("record", f"{run_ref.value}.{token}")


def make_artifact_ref(run_ref: StableRef, artifact_kind: str) -> StableRef:
    """Return a session-local artifact ref for one run."""

    token = f"{_to_kebab(artifact_kind)}-{uuid4().hex[:12]}"
    return StableRef("artifact", f"{run_ref.value}.{token}")


def make_trace_id() -> str:
    """Return a local trace identifier."""

    return f"trace-{uuid4().hex[:16]}"


def make_span_id() -> str:
    """Return a local span identifier."""

    return f"span-{uuid4().hex[:12]}"


def merge_event_attributes(
    attributes: Mapping[str, Any] | None,
    tags: Mapping[str, str] | None,
) -> Mapping[str, Any] | None:
    """Fold capture-surface event tags into the canonical attribute map."""

    if not tags:
        return attributes

    base = {} if attributes is None else dict(attributes)
    if "tags" in base:
        raise ValidationError(
            "event attributes must not contain a reserved 'tags' key when tags= is also provided.",
            code="capture_event_tags_conflict",
        )
    base["tags"] = dict(tags)
    return base


def make_record_envelope(
    *,
    config: "UnifiedConfig",
    context: "ActiveContext",
    record_type: str,
    family_prefix: str,
    observed_at: str | None = None,
    correlation_refs: CorrelationRefs | None = None,
) -> RecordEnvelope:
    """Build a canonical record envelope for the active context."""

    if context.run_ref is None:
        raise ValidationError(
            "Capture requires an active run context.",
            code="capture_run_context_required",
        )

    timestamp = observed_at or iso_utc_now()
    return RecordEnvelope(
        record_ref=make_record_ref(context.run_ref, family_prefix),
        record_type=record_type,
        recorded_at=iso_utc_now(),
        observed_at=timestamp,
        producer_ref=config.capture.producer_ref,
        run_ref=context.run_ref,
        deployment_execution_ref=context.deployment_execution_ref,
        stage_execution_ref=context.stage_execution_ref,
        batch_execution_ref=context.batch_execution_ref,
        sample_observation_ref=context.sample_observation_ref,
        operation_context_ref=context.operation_context_ref,
        correlation_refs=correlation_refs or CorrelationRefs(),
        schema_version=config.contract.schema_version,
    )
