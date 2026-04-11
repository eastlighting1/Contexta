"""Dispatch engine for capture payload fan-out."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import time
from typing import TYPE_CHECKING, Any, Sequence

from ..common.errors import DispatchError
from ..common.results import FailureInfo
from ..common.time import iso_utc_now
from .results import BatchCaptureResult, CaptureResult, Delivery, DeliveryStatus, PayloadFamily
from .sinks import LocalJsonlSink, Sink
from .sinks.protocol import SinkCaptureRequest

if TYPE_CHECKING:
    from ..config import UnifiedConfig


def _normalize_payload_family(value: PayloadFamily | str) -> PayloadFamily:
    if isinstance(value, PayloadFamily):
        return value
    return PayloadFamily(str(value).upper())


def _failure_delivery(sink_name: str, family: PayloadFamily, error: BaseException, *, attempts: int) -> Delivery:
    failure = FailureInfo.from_exception(error)
    return Delivery(
        sink_name=sink_name,
        family=family,
        status=DeliveryStatus.FAILURE,
        detail=failure.message,
        metadata={
            "error_code": failure.code,
            "error_type": failure.error_type,
            "retryable": failure.retryable,
            "attempts": attempts,
        },
    )


@dataclass(slots=True)
class CaptureDispatcher:
    """Canonical dispatch engine for capture fan-out."""

    config: "UnifiedConfig"
    sinks: tuple[Sink, ...] = ()

    def __post_init__(self) -> None:
        self.sinks = tuple(self.sinks)

    @classmethod
    def with_default_local_sink(
        cls,
        *,
        config: "UnifiedConfig",
        sinks: Sequence[Sink] | None = None,
    ) -> "CaptureDispatcher":
        if sinks is None:
            sinks = (LocalJsonlSink(config.workspace.cache_path / "capture"),)
        return cls(config=config, sinks=tuple(sinks))

    def dispatch_capture(self, result: CaptureResult) -> CaptureResult:
        family = _normalize_payload_family(result.family)
        if result.failed:
            return result

        deliveries: list[Delivery] = list(result.deliveries)
        warnings = list(result.warnings)
        degradation_reasons = list(result.degradation_reasons)
        request = SinkCaptureRequest(family=family, payload=result.payload, metadata=result.metadata)

        if not self.sinks:
            warnings.append("no configured sinks; capture payload was not persisted")
            degradation_reasons.append("no_configured_sink")
            return self._result_from_delivery_state(
                base=result,
                deliveries=deliveries,
                warnings=warnings,
                degradation_reasons=degradation_reasons,
                recovered_to_outbox=False,
                replay_refs=(),
            )

        eligible_failures: list[tuple[Sink, BaseException, int]] = []
        eligible_count = 0
        for sink in self.sinks:
            if not sink.supports(family):
                deliveries.append(
                    Delivery(
                        sink_name=sink.name,
                        family=family,
                        status=DeliveryStatus.SKIPPED,
                        detail="family not supported by sink",
                    )
                )
                continue

            eligible_count += 1
            try:
                receipt = self._capture_with_retry(sink, family=family, payload=result.payload)
            except BaseException as exc:
                attempts = self.config.capture.retry_attempts + 1
                deliveries.append(_failure_delivery(sink.name, family, exc, attempts=attempts))
                eligible_failures.append((sink, exc, attempts))
                continue

            deliveries.append(
                Delivery(
                    sink_name=sink.name,
                    family=family,
                    status=receipt.status,
                    detail=receipt.detail,
                    metadata=receipt.metadata,
                )
            )
            if receipt.status is DeliveryStatus.DEGRADED:
                degradation_reasons.append(f"sink_degraded:{sink.name}")

        if eligible_count == 0:
            warnings.append(f"no eligible sink for family {family.value}")
            degradation_reasons.append("no_eligible_sink")

        replay_refs: tuple[str, ...] = ()
        recovered_to_outbox = False
        if eligible_failures and self.config.capture.dispatch_failure_mode == "outbox":
            replay_refs = self._write_outbox_entries(request=request, failures=eligible_failures)
            recovered_to_outbox = bool(replay_refs)
            if recovered_to_outbox:
                warnings.append("failed deliveries were queued to the recovery outbox")
                degradation_reasons.append("recovered_to_outbox")

        return self._result_from_delivery_state(
            base=result,
            deliveries=deliveries,
            warnings=warnings,
            degradation_reasons=degradation_reasons,
            recovered_to_outbox=recovered_to_outbox,
            replay_refs=replay_refs,
        )

    def dispatch_batch(self, batch: BatchCaptureResult) -> BatchCaptureResult:
        results = tuple(self.dispatch_capture(item) for item in batch.results)
        return BatchCaptureResult.from_results(
            batch.family,
            results,
            metadata=dict(batch.metadata),
            applied=any(result.applied for result in results) if results else True,
            planned_only=bool(results) and all(result.planned_only for result in results),
        )

    def _capture_with_retry(
        self,
        sink: Sink,
        *,
        family: PayloadFamily,
        payload: object,
    ) -> Any:
        attempts = self.config.capture.retry_attempts + 1
        last_error: BaseException | None = None
        for attempt in range(1, attempts + 1):
            try:
                return sink.capture(family=family, payload=payload)
            except BaseException as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                backoff = self.config.capture.retry_backoff_seconds * (2 ** (attempt - 1))
                if backoff > 0:
                    time.sleep(backoff)
        assert last_error is not None
        raise last_error

    def _result_from_delivery_state(
        self,
        *,
        base: CaptureResult,
        deliveries: Sequence[Delivery],
        warnings: Sequence[str],
        degradation_reasons: Sequence[str],
        recovered_to_outbox: bool,
        replay_refs: Sequence[str],
    ) -> CaptureResult:
        deliveries = tuple(deliveries)
        warnings = tuple(dict.fromkeys(warnings))
        degradation_reasons = tuple(dict.fromkeys(degradation_reasons))
        success_count = sum(delivery.status is DeliveryStatus.SUCCESS for delivery in deliveries)
        degraded_count = sum(delivery.status is DeliveryStatus.DEGRADED for delivery in deliveries)
        failure_count = sum(delivery.status is DeliveryStatus.FAILURE for delivery in deliveries)
        eligible_count = success_count + degraded_count + failure_count

        metadata = dict(base.metadata)
        metadata.update(
            {
                "dispatch_pending": False,
                "delivery_count": len(deliveries),
                "eligible_delivery_count": eligible_count,
                "success_delivery_count": success_count,
                "degraded_delivery_count": degraded_count,
                "failure_delivery_count": failure_count,
            }
        )

        should_fail = (
            eligible_count > 0
            and success_count == 0
            and degraded_count == 0
            and failure_count > 0
            and not recovered_to_outbox
            and self.config.capture.dispatch_failure_mode == "raise"
        )
        if should_fail:
            return CaptureResult.failure_result(
                base.family,
                DispatchError(
                    "All eligible sinks failed to capture the payload.",
                    code="dispatch_all_eligible_sinks_failed",
                    details={"family": family.value if (family := _normalize_payload_family(base.family)) else None},
                ),
                deliveries=deliveries,
                warnings=warnings,
                replay_refs=replay_refs,
                metadata=metadata,
            )

        should_degrade = (
            base.degraded
            or not self.sinks
            or eligible_count == 0
            or degraded_count > 0
            or failure_count > 0
            or bool(degradation_reasons)
        )
        if should_degrade:
            return CaptureResult.with_degradation(
                base.family,
                payload=base.payload,
                deliveries=deliveries,
                warnings=warnings,
                degradation_reasons=degradation_reasons or ("capture_degraded",),
                degradation_emitted=base.degradation_emitted,
                degradation_payload=base.degradation_payload,
                recovered_to_outbox=recovered_to_outbox or base.recovered_to_outbox,
                replay_refs=replay_refs or base.replay_refs,
                metadata=metadata,
                applied=base.applied,
                planned_only=base.planned_only,
            )

        return CaptureResult.success(
            base.family,
            payload=base.payload,
            deliveries=deliveries,
            warnings=warnings,
            metadata=metadata,
            applied=base.applied,
        )

    def _write_outbox_entries(
        self,
        *,
        request: SinkCaptureRequest,
        failures: Sequence[tuple[Sink, BaseException, int]],
    ) -> tuple[str, ...]:
        outbox_root = self.config.recovery.outbox_root
        if outbox_root is None:
            return ()

        outbox_root.mkdir(parents=True, exist_ok=True)
        failed_deliveries_path = Path(outbox_root) / "failed_deliveries.jsonl"
        replay_refs: list[str] = []
        with failed_deliveries_path.open("a", encoding="utf-8", newline="\n") as handle:
            for index, (sink, error, attempts) in enumerate(failures, start=1):
                replay_ref = f"replay:{request.family.value.lower()}.{int(time.time() * 1000)}.{index}"
                replay_refs.append(replay_ref)
                failure = FailureInfo.from_exception(error)
                entry = {
                    "replay_ref": replay_ref,
                    "failed_at": iso_utc_now(),
                    "sink_name": sink.name,
                    "family": request.family.value,
                    "payload_type": request.payload_type,
                    "payload_ref": request.payload_ref,
                    "error": failure.message,
                    "error_code": failure.code,
                    "attempts": attempts,
                    "payload": request.serialized_payload,
                }
                handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str))
                handle.write("\n")
        return tuple(replay_refs)


def dispatch_capture_result(
    config: "UnifiedConfig",
    result: CaptureResult,
    *,
    sinks: Sequence[Sink] | None = None,
) -> CaptureResult:
    dispatcher = CaptureDispatcher.with_default_local_sink(config=config, sinks=sinks)
    return dispatcher.dispatch_capture(result)


def dispatch_batch_capture_result(
    config: "UnifiedConfig",
    batch: BatchCaptureResult,
    *,
    sinks: Sequence[Sink] | None = None,
) -> BatchCaptureResult:
    dispatcher = CaptureDispatcher.with_default_local_sink(config=config, sinks=sinks)
    return dispatcher.dispatch_batch(batch)


__all__ = ["CaptureDispatcher", "dispatch_batch_capture_result", "dispatch_capture_result"]
