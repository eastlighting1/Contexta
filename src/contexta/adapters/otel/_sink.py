"""OTel bridge sink — exports Contexta capture payloads to OpenTelemetry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...capture.sinks.protocol import BaseSink, SinkCaptureReceipt
from ...capture.results import PayloadFamily
from ...common.errors import DependencyError

if TYPE_CHECKING:
    from ...contract import (
        DegradedRecord,
        MetricRecord,
        StructuredEventRecord,
        TraceSpanRecord,
    )


def _load_otel_trace():
    """Lazy import of opentelemetry.trace — raises DependencyError if absent."""
    try:
        import opentelemetry.trace as otel_trace
        return otel_trace
    except ImportError as exc:
        raise DependencyError(
            "opentelemetry-api is required for OTelSink. "
            "Install it with: pip install 'contexta[otel]'",
            code="otel_api_not_ready",
            cause=exc,
        ) from exc


def _load_otel_metrics():
    """Lazy import of opentelemetry.metrics — raises DependencyError if absent."""
    try:
        import opentelemetry.metrics as otel_metrics
        return otel_metrics
    except ImportError as exc:
        raise DependencyError(
            "opentelemetry-api is required for OTelSink. "
            "Install it with: pip install 'contexta[otel]'",
            code="otel_api_not_ready",
            cause=exc,
        ) from exc


def _map_span_kind(contexta_kind: str) -> Any:
    otel_trace = _load_otel_trace()
    mapping = {
        "operation": otel_trace.SpanKind.INTERNAL,
        "internal": otel_trace.SpanKind.INTERNAL,
        "io": otel_trace.SpanKind.CLIENT,
        "network": otel_trace.SpanKind.CLIENT,
        "process": otel_trace.SpanKind.PRODUCER,
    }
    return mapping.get(contexta_kind, otel_trace.SpanKind.INTERNAL)


def _map_status_code(contexta_status: str) -> Any:
    otel_trace = _load_otel_trace()
    if contexta_status == "ok":
        return otel_trace.StatusCode.OK
    return otel_trace.StatusCode.ERROR


class OTelSink(BaseSink):
    """Export Contexta capture payloads to the OpenTelemetry API.

    Implements the ``Sink`` protocol so it can be passed directly to
    ``Contexta(sinks=[OTelSink(...)])``.

    Raises ``DependencyError`` on construction when ``opentelemetry-api``
    is not installed.

    Thread safety: metric instrument cache is not thread-safe.
    Use one instance per thread or protect externally.
    """

    def __init__(
        self,
        *,
        service_name: str = "contexta",
        tracer_provider: Any = None,
        meter_provider: Any = None,
        name: str = "otel",
    ) -> None:
        super().__init__(
            name=name,
            supported_families=(PayloadFamily.RECORD,),
        )
        # Eager import check — fail loudly on construction, not on first capture.
        _load_otel_trace()
        _load_otel_metrics()

        self._service_name = service_name
        self._tracer_provider = tracer_provider
        self._meter_provider = meter_provider
        self._tracer: Any = None
        self._meter: Any = None
        # (metric_name, unit) → Histogram instrument
        self._histograms: dict[tuple[str, str], Any] = {}

    # ------------------------------------------------------------------
    # Sink protocol
    # ------------------------------------------------------------------

    def capture(self, *, family: PayloadFamily | str, payload: object) -> SinkCaptureReceipt:
        from ...contract import (
            DegradedRecord,
            MetricRecord,
            StructuredEventRecord,
            TraceSpanRecord,
        )

        if not self.supports(family):
            return SinkCaptureReceipt.success(detail="family not handled by OTelSink")

        if isinstance(payload, TraceSpanRecord):
            self._export_span(payload)
            return SinkCaptureReceipt.success(
                detail=f"exported span {payload.payload.span_name}",
                metadata={"span_name": payload.payload.span_name},
            )

        if isinstance(payload, MetricRecord):
            self._export_metric(payload)
            return SinkCaptureReceipt.success(
                detail=f"recorded metric {payload.payload.metric_key}",
                metadata={"metric_key": payload.payload.metric_key},
            )

        if isinstance(payload, StructuredEventRecord):
            self._export_event(payload)
            return SinkCaptureReceipt.success(
                detail=f"added event {payload.payload.event_key}",
                metadata={"event_key": payload.payload.event_key},
            )

        if isinstance(payload, DegradedRecord):
            self._export_degraded(payload)
            return SinkCaptureReceipt.success(
                detail=f"added degraded event {payload.payload.issue_key}",
                metadata={"issue_key": payload.payload.issue_key},
            )

        return SinkCaptureReceipt.success(detail="unrecognised record type; skipped")

    # ------------------------------------------------------------------
    # Lazy tracer / meter
    # ------------------------------------------------------------------

    def _get_tracer(self) -> Any:
        if self._tracer is None:
            otel_trace = _load_otel_trace()
            provider = self._tracer_provider or otel_trace.get_tracer_provider()
            self._tracer = provider.get_tracer(self._service_name)
        return self._tracer

    def _get_meter(self) -> Any:
        if self._meter is None:
            otel_metrics = _load_otel_metrics()
            provider = self._meter_provider or otel_metrics.get_meter_provider()
            self._meter = provider.get_meter(self._service_name)
        return self._meter

    def _get_histogram(self, metric_name: str, unit: str) -> Any:
        key = (metric_name, unit)
        if key not in self._histograms:
            self._histograms[key] = self._get_meter().create_histogram(
                name=metric_name,
                unit=unit,
                description=f"Contexta metric: {metric_name}",
            )
        return self._histograms[key]

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def _export_span(self, record: "TraceSpanRecord") -> None:
        otel_trace = _load_otel_trace()
        payload = record.payload
        envelope = record.envelope

        attrs: dict[str, Any] = {
            "contexta.run_ref": str(envelope.run_ref),
            "contexta.record_ref": str(envelope.record_ref),
            "contexta.span_kind": payload.span_kind,
            "contexta.span_id": payload.span_id,
            "contexta.trace_id": payload.trace_id,
        }
        if envelope.stage_execution_ref is not None:
            attrs["contexta.stage_ref"] = str(envelope.stage_execution_ref)
        if payload.parent_span_id is not None:
            attrs["contexta.parent_span_id"] = payload.parent_span_id
        if payload.attributes:
            for k, v in payload.attributes.items():
                attrs[f"contexta.span.{k}"] = str(v)

        span_kind = _map_span_kind(payload.span_kind)
        status_code = _map_status_code(payload.status)

        span = self._get_tracer().start_span(
            payload.span_name,
            kind=span_kind,
            attributes=attrs,
        )
        try:
            span.set_status(status_code)
        finally:
            span.end()

    def _export_metric(self, record: "MetricRecord") -> None:
        payload = record.payload
        envelope = record.envelope

        metric_name = f"contexta.{payload.metric_key}"
        unit = payload.unit or "1"

        attrs: dict[str, Any] = {
            "contexta.run_ref": str(envelope.run_ref),
            "contexta.aggregation_scope": payload.aggregation_scope,
            "contexta.value_type": payload.value_type,
        }
        if envelope.stage_execution_ref is not None:
            attrs["contexta.stage_ref"] = str(envelope.stage_execution_ref)
        if payload.tags:
            for k, v in payload.tags.items():
                attrs[f"contexta.tag.{k}"] = v

        histogram = self._get_histogram(metric_name, unit)
        histogram.record(float(payload.value), attributes=attrs)

    def _export_event(self, record: "StructuredEventRecord") -> None:
        otel_trace = _load_otel_trace()
        payload = record.payload
        envelope = record.envelope

        attrs: dict[str, Any] = {
            "contexta.run_ref": str(envelope.run_ref),
            "contexta.event_level": payload.level,
            "contexta.event_message": payload.message,
        }
        if envelope.stage_execution_ref is not None:
            attrs["contexta.stage_ref"] = str(envelope.stage_execution_ref)
        if payload.attributes:
            for k, v in payload.attributes.items():
                attrs[f"contexta.event.{k}"] = str(v)

        current_span = otel_trace.get_current_span()
        current_span.add_event(payload.event_key, attributes=attrs)

    def _export_degraded(self, record: "DegradedRecord") -> None:
        otel_trace = _load_otel_trace()
        payload = record.payload
        envelope = record.envelope

        attrs: dict[str, Any] = {
            "contexta.run_ref": str(envelope.run_ref),
            "contexta.issue_key": payload.issue_key,
            "contexta.degradation_category": payload.category,
            "contexta.severity": payload.severity,
        }
        if envelope.stage_execution_ref is not None:
            attrs["contexta.stage_ref"] = str(envelope.stage_execution_ref)

        current_span = otel_trace.get_current_span()
        current_span.add_event("contexta.degraded", attributes=attrs)


__all__ = ["OTelSink"]
