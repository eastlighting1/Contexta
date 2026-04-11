"""MLflow bridge sink — exports Contexta capture payloads to MLflow Tracking."""

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
    )

_MLFLOW_TAG_MAX_LEN = 5000


def _load_mlflow():
    """Lazy import of mlflow — raises DependencyError if absent."""
    try:
        import mlflow
        return mlflow
    except ImportError as exc:
        raise DependencyError(
            "mlflow is required for MLflowSink. "
            "Install it with: pip install 'contexta[mlflow]'",
            code="mlflow_not_ready",
            cause=exc,
        ) from exc


class MLflowSink(BaseSink):
    """Export Contexta capture payloads to the MLflow Tracking API.

    Implements the ``Sink`` protocol so it can be passed directly to
    ``Contexta(sinks=[MLflowSink(...)])``.

    Raises ``DependencyError`` on construction when ``mlflow``
    is not installed.

    Thread safety: tag-write cache is not thread-safe.
    Use one instance per thread or protect externally.
    """

    def __init__(
        self,
        *,
        run_id: str | None = None,
        name: str = "mlflow",
    ) -> None:
        super().__init__(
            name=name,
            supported_families=(PayloadFamily.RECORD,),
        )
        # Eager import check — fail loudly on construction, not on first capture.
        _load_mlflow()

        self._run_id = run_id
        # Track which tags have already been written to avoid write amplification.
        # Keyed by the full tag key string.
        self._written_tags: set[str] = set()
        # Track whether the global run_ref tag has been set.
        self._run_ref_written: bool = False

    # ------------------------------------------------------------------
    # Sink protocol
    # ------------------------------------------------------------------

    def capture(self, *, family: PayloadFamily | str, payload: object) -> SinkCaptureReceipt:
        from ...contract import (
            DegradedRecord,
            MetricRecord,
            StructuredEventRecord,
        )

        if not self.supports(family):
            return SinkCaptureReceipt.success(detail="family not handled by MLflowSink")

        if isinstance(payload, MetricRecord):
            self._export_metric(payload)
            return SinkCaptureReceipt.success(
                detail=f"logged metric {payload.payload.metric_key}",
                metadata={"metric_key": payload.payload.metric_key},
            )

        if isinstance(payload, StructuredEventRecord):
            self._export_event(payload)
            return SinkCaptureReceipt.success(
                detail=f"tagged event {payload.payload.event_key}",
                metadata={"event_key": payload.payload.event_key},
            )

        if isinstance(payload, DegradedRecord):
            self._export_degraded(payload)
            return SinkCaptureReceipt.success(
                detail=f"tagged degraded {payload.payload.issue_key}",
                metadata={"issue_key": payload.payload.issue_key},
            )

        return SinkCaptureReceipt.success(detail="unrecognised record type; skipped")

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def _log_metric(self, key: str, value: float) -> None:
        mlflow = _load_mlflow()
        if self._run_id is not None:
            mlflow.log_metric(key, value, run_id=self._run_id)
        else:
            mlflow.log_metric(key, value)

    def _set_tag(self, key: str, value: str) -> None:
        mlflow = _load_mlflow()
        if self._run_id is not None:
            mlflow.set_tag(key, value, run_id=self._run_id)
        else:
            mlflow.set_tag(key, value)

    def _set_tag_once(self, key: str, value: str) -> None:
        """Write a tag only on the first call for this key."""
        if key not in self._written_tags:
            self._written_tags.add(key)
            self._set_tag(key, value)

    def _ensure_run_ref_tag(self, run_ref: Any) -> None:
        if not self._run_ref_written:
            self._run_ref_written = True
            self._set_tag_once("contexta.run_ref", str(run_ref))

    def _export_metric(self, record: "MetricRecord") -> None:
        payload = record.payload
        envelope = record.envelope

        self._ensure_run_ref_tag(envelope.run_ref)
        if envelope.stage_execution_ref is not None:
            self._set_tag_once("contexta.stage_ref", str(envelope.stage_execution_ref))

        # Write unit tag once per metric key (not per observation)
        if payload.unit:
            unit_tag = f"contexta.metric_unit.{payload.metric_key}"
            self._set_tag_once(unit_tag, payload.unit)

        # Write metric tags once per metric key
        if payload.tags:
            for k, v in payload.tags.items():
                tag_key = f"contexta.tag.{k}"
                self._set_tag_once(tag_key, str(v))

        self._log_metric(payload.metric_key, float(payload.value))

    def _export_event(self, record: "StructuredEventRecord") -> None:
        payload = record.payload
        envelope = record.envelope

        self._ensure_run_ref_tag(envelope.run_ref)

        message = str(payload.message)[:_MLFLOW_TAG_MAX_LEN]
        self._set_tag(f"contexta.event.{payload.event_key}", message)
        self._set_tag_once(
            f"contexta.event_level.{payload.event_key}",
            payload.level,
        )

    def _export_degraded(self, record: "DegradedRecord") -> None:
        payload = record.payload
        envelope = record.envelope

        self._set_tag(
            f"contexta.degraded.{payload.issue_key}",
            f"{payload.category}:{payload.severity}",
        )
        self._set_tag_once("contexta.degraded_run_ref", str(envelope.run_ref))


__all__ = ["MLflowSink"]
