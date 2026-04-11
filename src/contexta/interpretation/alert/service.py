"""Alert evaluation service over interpretation query snapshots."""

from __future__ import annotations

from ...common.errors import InterpretationError, ValidationError
from ..compare import CompletenessNote
from ..query import EvidenceLink, QueryService, RunListQuery
from ..repositories import ObservationRecord
from ..trend.service import TrendPolicy
from .models import AlertReport, AlertResult, AlertRule


class AlertError(InterpretationError):
    """Raised for alert-specific failures."""


class AlertService:
    """Read-only alert evaluation service layered on top of QueryService."""

    def __init__(
        self,
        query_service: QueryService,
        *,
        metric_aggregation: str = "latest",
    ) -> None:
        self.query_service = query_service
        self.metric_aggregation = TrendPolicy(metric_aggregation=metric_aggregation).metric_aggregation

    def evaluate_alerts(self, run_id: str, rules: tuple[AlertRule, ...] | list[AlertRule]) -> tuple[AlertResult, ...]:
        snapshot = self.query_service.get_run_snapshot(run_id)
        results = []
        for rule in rules:
            _validate_rule(rule)
            records = _filter_metric_records(snapshot.records, metric_key=rule.metric_key, stage_name=rule.stage_name)
            actual_value = _representative_metric_value(records, self.metric_aggregation)
            notes = []
            if actual_value is None:
                notes.append(
                    CompletenessNote(
                        severity="warning",
                        summary=f"alert_metric_missing:{rule.metric_key}",
                        details={"run_id": snapshot.run.run_id, "stage_name": rule.stage_name},
                    )
                )
            triggered = False if actual_value is None else _compare(actual_value, rule.operator, rule.threshold)
            results.append(
                AlertResult(
                    rule_name=rule.name or _default_rule_name(rule),
                    metric_key=rule.metric_key,
                    run_id=snapshot.run.run_id,
                    actual_value=actual_value,
                    threshold=rule.threshold,
                    operator=rule.operator,
                    triggered=triggered,
                    severity=rule.severity,
                    stage_name=rule.stage_name,
                    evidence_links=(EvidenceLink(kind="run", ref=snapshot.run.run_id, label=snapshot.run.name),),
                    completeness_notes=tuple(notes),
                )
            )
        return tuple(results)

    def evaluate_alerts_fleet(
        self,
        rules: tuple[AlertRule, ...] | list[AlertRule],
        *,
        query: RunListQuery | None = None,
        project_name: str | None = None,
    ) -> AlertReport:
        runs = self.query_service.list_runs(project_name, query=query)
        results = []
        for run in runs:
            results.extend(self.evaluate_alerts(run.run_id, rules))
        notes = []
        if not runs:
            notes.append(
                CompletenessNote(
                    severity="info",
                    summary="alert_population_empty",
                    details={"project_name": project_name},
                )
            )
        return AlertReport(
            run_ids=tuple(run.run_id for run in runs),
            results=tuple(results),
            completeness_notes=tuple(notes),
        )


def _validate_rule(rule: AlertRule) -> None:
    if rule.operator not in {"gt", "lt", "gte", "lte", "eq", "ne"}:
        raise ValidationError(
            "Unsupported alert operator.",
            code="alert_invalid_operator",
            details={"operator": rule.operator},
        )
    if rule.severity not in {"info", "warning", "error"}:
        raise ValidationError(
            "Unsupported alert severity.",
            code="alert_invalid_severity",
            details={"severity": rule.severity},
        )


def _default_rule_name(rule: AlertRule) -> str:
    stage_suffix = "" if rule.stage_name is None else f"@{rule.stage_name}"
    return f"{rule.metric_key}{stage_suffix}:{rule.operator}:{rule.threshold}"


def _filter_metric_records(
    records: tuple[ObservationRecord, ...],
    *,
    metric_key: str,
    stage_name: str | None = None,
) -> tuple[ObservationRecord, ...]:
    filtered = []
    for record in records:
        if record.record_type != "metric" or record.key != metric_key:
            continue
        if stage_name is not None:
            if record.stage_id is None or not record.stage_id.endswith(f".{stage_name}"):
                continue
        filtered.append(record)
    return tuple(sorted(filtered, key=lambda item: item.observed_at))


def _representative_metric_value(records: tuple[ObservationRecord, ...], aggregation: str) -> float | None:
    values = [float(record.value) for record in records if record.value is not None]
    if not values:
        return None
    if aggregation == "latest":
        return values[-1]
    if aggregation == "max":
        return max(values)
    if aggregation == "min":
        return min(values)
    from statistics import mean

    return mean(values)


def _compare(value: float, operator: str, threshold: float) -> bool:
    if operator == "gt":
        return value > threshold
    if operator == "lt":
        return value < threshold
    if operator == "gte":
        return value >= threshold
    if operator == "lte":
        return value <= threshold
    if operator == "eq":
        return value == threshold
    if operator == "ne":
        return value != threshold
    raise AlertError(
        "Unsupported alert operator.",
        code="alert_invalid_operator",
        details={"operator": operator},
    )


__all__ = ["AlertError", "AlertService"]
