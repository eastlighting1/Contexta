"""Composite sink fan-out implementation."""

from __future__ import annotations

from ...common.errors import ContextaError, DispatchError
from .protocol import BaseSink, Sink, SinkCaptureReceipt
from ..results import DeliveryStatus, PayloadFamily


class CompositeSink(BaseSink):
    """Fan out one payload to multiple child sinks."""

    def __init__(
        self,
        sinks: tuple[Sink, ...] | list[Sink],
        *,
        name: str = "composite",
    ) -> None:
        self.sinks = tuple(sinks)
        supported = self._collect_supported_families(self.sinks)
        super().__init__(name=name, supported_families=supported)

    @staticmethod
    def _collect_supported_families(sinks: tuple[Sink, ...]) -> tuple[PayloadFamily, ...]:
        ordered: list[PayloadFamily] = []
        seen: set[PayloadFamily] = set()
        for sink in sinks:
            for family in getattr(sink, "supported_families", ()):
                normalized = family if isinstance(family, PayloadFamily) else PayloadFamily(str(family).upper())
                if normalized not in seen:
                    seen.add(normalized)
                    ordered.append(normalized)
        return tuple(ordered or tuple(PayloadFamily))

    def supports(self, family: PayloadFamily | str) -> bool:
        normalized = PayloadFamily(family) if isinstance(family, str) else family
        return any(sink.supports(normalized) for sink in self.sinks)

    def capture(self, *, family: PayloadFamily | str, payload: object) -> SinkCaptureReceipt:
        request = self.make_request(family=family, payload=payload)
        eligible = tuple(sink for sink in self.sinks if sink.supports(request.family))
        if not eligible:
            raise DispatchError(
                f"Composite sink '{self.name}' has no eligible child sinks for '{request.family.value}'.",
                code="composite_sink_no_eligible_children",
                details={"sink_name": self.name, "family": request.family.value},
            )

        successes: list[str] = []
        degradations: list[str] = []
        failures: list[dict[str, str]] = []
        for sink in eligible:
            try:
                receipt = sink.capture(family=request.family, payload=request.payload)
            except ContextaError as exc:
                failures.append(
                    {
                        "sink_name": sink.name,
                        "code": exc.code,
                        "message": str(exc),
                    }
                )
                continue
            except Exception as exc:  # pragma: no cover - defensive boundary
                failures.append(
                    {
                        "sink_name": sink.name,
                        "code": "unexpected_sink_error",
                        "message": str(exc),
                    }
                )
                continue

            detail = receipt.detail or sink.name
            if receipt.status is DeliveryStatus.DEGRADED:
                degradations.append(f"{sink.name}: {detail}")
            else:
                successes.append(f"{sink.name}: {detail}")

        if failures and not successes and not degradations:
            raise DispatchError(
                f"Composite sink '{self.name}' failed in all eligible child sinks.",
                code="composite_sink_all_children_failed",
                details={
                    "sink_name": self.name,
                    "family": request.family.value,
                    "failures": failures,
                },
            )

        summary_parts: list[str] = []
        if successes:
            summary_parts.append(f"{len(successes)} child sink(s) succeeded")
        if degradations:
            summary_parts.append(f"{len(degradations)} child sink(s) degraded")
        if failures:
            summary_parts.append(f"{len(failures)} child sink(s) failed")

        metadata = {
            "family": request.family.value,
            "success_count": len(successes),
            "degraded_count": len(degradations),
            "failure_count": len(failures),
            "successes": tuple(successes),
            "degradations": tuple(degradations),
            "failures": tuple(failures),
        }
        detail = "; ".join(summary_parts) or "no-op composite capture"
        if failures or degradations:
            return SinkCaptureReceipt.degraded(detail=detail, metadata=metadata)
        return SinkCaptureReceipt.success(detail=detail, metadata=metadata)


__all__ = ["CompositeSink"]
