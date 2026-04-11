"""Span capture service helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Sequence

from ..common.time import iso_utc_now, normalize_timestamp
from ..contract import TraceSpanPayload, TraceSpanRecord
from ._service_utils import make_record_envelope, make_span_id, make_trace_id
from .models import SpanEmission
from .results import BatchCaptureResult, CaptureResult, PayloadFamily

if TYPE_CHECKING:
    from ..config import UnifiedConfig
    from ..runtime.session import ActiveContext


def build_span_record(
    *,
    config: "UnifiedConfig",
    context: "ActiveContext",
    emission: SpanEmission,
) -> TraceSpanRecord:
    """Build a canonical trace/span record for the active context."""

    started_at = emission.started_at or iso_utc_now()
    ended_at = emission.ended_at or started_at
    normalized_started_at = normalize_timestamp(started_at)
    normalized_ended_at = normalize_timestamp(ended_at)
    envelope = make_record_envelope(
        config=config,
        context=context,
        record_type="span",
        family_prefix="span",
        observed_at=normalized_started_at,
    )
    payload = TraceSpanPayload(
        span_id=make_span_id(),
        trace_id=make_trace_id(),
        parent_span_id=emission.parent_span_id,
        span_name=emission.name,
        started_at=normalized_started_at,
        ended_at=normalized_ended_at,
        status=emission.status,
        span_kind=emission.span_kind,
        attributes=emission.attributes,
        linked_refs=emission.linked_refs or (),
    )
    return TraceSpanRecord(envelope=envelope, payload=payload)


def capture_span(
    *,
    config: "UnifiedConfig",
    context: "ActiveContext",
    name: str,
    started_at: str | None = None,
    ended_at: str | None = None,
    status: str = "ok",
    span_kind: str = "operation",
    attributes: Mapping[str, Any] | None = None,
    linked_refs: Sequence[str] | None = None,
    parent_span_id: str | None = None,
) -> CaptureResult:
    """Capture one trace/span record in the current context."""

    emission = SpanEmission(
        name=name,
        started_at=started_at,
        ended_at=ended_at,
        status=status,
        span_kind=span_kind,
        attributes=attributes,
        linked_refs=tuple(linked_refs or ()),
        parent_span_id=parent_span_id,
    )
    record = build_span_record(config=config, context=context, emission=emission)
    return CaptureResult.success(
        PayloadFamily.RECORD,
        payload=record,
        metadata={
            "service": "span",
            "record_ref": str(record.envelope.record_ref),
            "record_type": record.envelope.record_type,
            "dispatch_pending": True,
        },
    )


def emit_spans(
    *,
    config: "UnifiedConfig",
    context: "ActiveContext",
    emissions: Sequence[SpanEmission | Mapping[str, Any]],
) -> BatchCaptureResult:
    """Capture a validated span batch using ordered per-item processing."""

    normalized = tuple(
        item if isinstance(item, SpanEmission) else SpanEmission(**item)
        for item in emissions
    )
    results = tuple(
        capture_span(
            config=config,
            context=context,
            name=emission.name,
            started_at=emission.started_at,
            ended_at=emission.ended_at,
            status=emission.status,
            span_kind=emission.span_kind,
            attributes=emission.attributes,
            linked_refs=emission.linked_refs,
            parent_span_id=emission.parent_span_id,
        )
        for emission in normalized
    )
    return BatchCaptureResult.from_results(
        PayloadFamily.RECORD,
        results,
        metadata={"service": "span_batch", "dispatch_pending": True},
    )


__all__ = ["build_span_record", "capture_span", "emit_spans"]
