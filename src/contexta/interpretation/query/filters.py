"""Filter models for interpretation query workflows."""

from __future__ import annotations

from dataclasses import dataclass

from ...common.errors import ValidationError


VALID_SORT_KEYS = ("started_at", "ended_at", "name")
VALID_OPERATORS = ("gt", "lt", "gte", "lte", "eq", "ne")


@dataclass(frozen=True, slots=True)
class TimeRange:
    started_after: str | None = None
    started_before: str | None = None

    def __post_init__(self) -> None:
        if self.started_after is not None and (not isinstance(self.started_after, str) or not self.started_after.strip()):
            raise ValidationError("started_after must be a non-blank string.", code="query_invalid_time_range")
        if self.started_before is not None and (not isinstance(self.started_before, str) or not self.started_before.strip()):
            raise ValidationError("started_before must be a non-blank string.", code="query_invalid_time_range")
        if self.started_after and self.started_before and self.started_after > self.started_before:
            raise ValidationError(
                "started_after must be less than or equal to started_before.",
                code="query_invalid_time_range",
            )


@dataclass(frozen=True, slots=True)
class MetricCondition:
    metric_key: str
    operator: str
    threshold: int | float
    stage_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.metric_key, str) or not self.metric_key.strip():
            raise ValidationError("metric_key must be a non-blank string.", code="query_invalid_metric_condition")
        normalized_operator = self.operator.strip().lower() if isinstance(self.operator, str) else ""
        if normalized_operator not in VALID_OPERATORS:
            raise ValidationError(
                "unsupported metric condition operator.",
                code="query_invalid_metric_condition",
                details={"operator": self.operator, "allowed": VALID_OPERATORS},
            )
        if not isinstance(self.threshold, (int, float)) or isinstance(self.threshold, bool):
            raise ValidationError("threshold must be numeric.", code="query_invalid_metric_condition")
        if self.stage_name is not None and (not isinstance(self.stage_name, str) or not self.stage_name.strip()):
            raise ValidationError("stage_name must be a non-blank string when provided.", code="query_invalid_metric_condition")
        object.__setattr__(self, "operator", normalized_operator)


@dataclass(frozen=True, slots=True)
class RunListQuery:
    project_name: str | None = None
    status: str | None = None
    tags: dict[str, str] | None = None
    time_range: TimeRange | None = None
    metric_conditions: tuple[MetricCondition, ...] = ()
    limit: int | None = None
    offset: int = 0
    sort_by: str = "started_at"
    sort_desc: bool = False

    def __post_init__(self) -> None:
        if self.project_name is not None and (not isinstance(self.project_name, str) or not self.project_name.strip()):
            raise ValidationError("project_name must be a non-blank string when provided.", code="query_invalid_run_list_query")
        if self.status is not None and (not isinstance(self.status, str) or not self.status.strip()):
            raise ValidationError("status must be a non-blank string when provided.", code="query_invalid_run_list_query")
        if self.tags is not None:
            if not isinstance(self.tags, dict):
                raise ValidationError("tags must be a mapping.", code="query_invalid_run_list_query")
            for key, value in self.tags.items():
                if not isinstance(key, str) or not key.strip() or not isinstance(value, str):
                    raise ValidationError("tags must use non-blank string keys and string values.", code="query_invalid_run_list_query")
        if self.time_range is not None and not isinstance(self.time_range, TimeRange):
            raise ValidationError("time_range must be a TimeRange.", code="query_invalid_run_list_query")
        object.__setattr__(self, "metric_conditions", tuple(self.metric_conditions))
        if self.limit is not None:
            if not isinstance(self.limit, int) or isinstance(self.limit, bool) or self.limit <= 0:
                raise ValidationError("limit must be a positive integer when provided.", code="query_invalid_run_list_query")
        if not isinstance(self.offset, int) or isinstance(self.offset, bool) or self.offset < 0:
            raise ValidationError("offset must be a non-negative integer.", code="query_invalid_run_list_query")
        if self.sort_by not in VALID_SORT_KEYS:
            raise ValidationError(
                "unsupported sort key.",
                code="query_invalid_run_list_query",
                details={"sort_by": self.sort_by, "allowed": VALID_SORT_KEYS},
            )
        if not isinstance(self.sort_desc, bool):
            raise ValidationError("sort_desc must be a bool.", code="query_invalid_run_list_query")


__all__ = ["MetricCondition", "RunListQuery", "TimeRange"]
