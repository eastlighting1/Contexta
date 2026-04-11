"""Metric capture service helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Sequence

from ..contract import MetricPayload, MetricRecord
from ._service_utils import make_record_envelope, subject_ref_text
from .models import MetricEmission
from .results import BatchCaptureResult, CaptureResult, PayloadFamily

if TYPE_CHECKING:
    from ..config import UnifiedConfig
    from ..runtime.session import ActiveContext


def _infer_value_type(value: int | float) -> str:
    return "int" if isinstance(value, int) and not isinstance(value, bool) else "float"


def build_metric_record(
    *,
    config: "UnifiedConfig",
    context: "ActiveContext",
    emission: MetricEmission,
) -> MetricRecord:
    """Build a canonical metric record for the active context."""

    envelope = make_record_envelope(
        config=config,
        context=context,
        record_type="metric",
        family_prefix="metric",
    )
    payload = MetricPayload(
        metric_key=emission.key,
        value=emission.value,
        value_type=_infer_value_type(emission.value),
        unit=emission.unit,
        aggregation_scope=emission.aggregation_scope,
        subject_ref=subject_ref_text(context),
        tags=emission.tags,
        summary_basis=emission.summary_basis,
    )
    return MetricRecord(envelope=envelope, payload=payload)


def capture_metric(
    *,
    config: "UnifiedConfig",
    context: "ActiveContext",
    key: str,
    value: int | float,
    unit: str | None = None,
    aggregation_scope: str = "step",
    tags: Mapping[str, str] | None = None,
    summary_basis: str = "raw_observation",
) -> CaptureResult:
    """Capture one metric in the current context."""

    emission = MetricEmission(
        key=key,
        value=value,
        unit=unit,
        aggregation_scope=aggregation_scope,
        tags=tags,
        summary_basis=summary_basis,
    )
    record = build_metric_record(config=config, context=context, emission=emission)
    return CaptureResult.success(
        PayloadFamily.RECORD,
        payload=record,
        metadata={
            "service": "metric",
            "record_ref": str(record.envelope.record_ref),
            "record_type": record.envelope.record_type,
            "dispatch_pending": True,
        },
    )


def emit_metrics(
    *,
    config: "UnifiedConfig",
    context: "ActiveContext",
    emissions: Sequence[MetricEmission | Mapping[str, Any]],
) -> BatchCaptureResult:
    """Capture a validated metric batch using ordered per-item processing."""

    normalized = tuple(
        item if isinstance(item, MetricEmission) else MetricEmission(**item)
        for item in emissions
    )
    results = tuple(
        capture_metric(
            config=config,
            context=context,
            key=emission.key,
            value=emission.value,
            unit=emission.unit,
            aggregation_scope=emission.aggregation_scope,
            tags=emission.tags,
            summary_basis=emission.summary_basis,
        )
        for emission in normalized
    )
    return BatchCaptureResult.from_results(
        PayloadFamily.RECORD,
        results,
        metadata={"service": "metric_batch", "dispatch_pending": True},
    )


__all__ = ["build_metric_record", "capture_metric", "emit_metrics"]
