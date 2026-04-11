"""Event capture service helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Sequence

from ..contract import StructuredEventPayload, StructuredEventRecord
from ._service_utils import make_record_envelope, merge_event_attributes, subject_ref_text
from .models import EventEmission
from .results import BatchCaptureResult, CaptureResult, PayloadFamily

if TYPE_CHECKING:
    from ..config import UnifiedConfig
    from ..runtime.session import ActiveContext


def build_event_record(
    *,
    config: "UnifiedConfig",
    context: "ActiveContext",
    emission: EventEmission,
) -> StructuredEventRecord:
    """Build a canonical structured event record for the active context."""

    envelope = make_record_envelope(
        config=config,
        context=context,
        record_type="event",
        family_prefix="event",
    )
    payload = StructuredEventPayload(
        event_key=emission.key,
        level=emission.level,
        message=emission.message,
        subject_ref=subject_ref_text(context),
        attributes=merge_event_attributes(emission.attributes, emission.tags),
    )
    return StructuredEventRecord(envelope=envelope, payload=payload)


def capture_event(
    *,
    config: "UnifiedConfig",
    context: "ActiveContext",
    key: str,
    message: str,
    level: str = "info",
    attributes: Mapping[str, Any] | None = None,
    tags: Mapping[str, str] | None = None,
) -> CaptureResult:
    """Capture one structured event in the current context."""

    emission = EventEmission(
        key=key,
        message=message,
        level=level,
        attributes=attributes,
        tags=tags,
    )
    record = build_event_record(config=config, context=context, emission=emission)
    return CaptureResult.success(
        PayloadFamily.RECORD,
        payload=record,
        metadata={
            "service": "event",
            "record_ref": str(record.envelope.record_ref),
            "record_type": record.envelope.record_type,
            "dispatch_pending": True,
        },
    )


def emit_events(
    *,
    config: "UnifiedConfig",
    context: "ActiveContext",
    emissions: Sequence[EventEmission | Mapping[str, Any]],
) -> BatchCaptureResult:
    """Capture a validated event batch using ordered per-item processing."""

    normalized = tuple(
        item if isinstance(item, EventEmission) else EventEmission(**item)
        for item in emissions
    )
    results = tuple(
        capture_event(
            config=config,
            context=context,
            key=emission.key,
            message=emission.message,
            level=emission.level,
            attributes=emission.attributes,
            tags=emission.tags,
        )
        for emission in normalized
    )
    return BatchCaptureResult.from_results(
        PayloadFamily.RECORD,
        results,
        metadata={"service": "event_batch", "dispatch_pending": True},
    )


__all__ = ["build_event_record", "capture_event", "emit_events"]
