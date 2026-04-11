"""Public aggregation surface for interpretation workflows."""

from .models import MetricAggregate, RunStatusDistribution, RunSummaryTable, StageAggregate, StatusCount
from .service import AggregationError, AggregationService

__all__ = [
    "AggregationError",
    "AggregationService",
    "MetricAggregate",
    "RunStatusDistribution",
    "RunSummaryTable",
    "StageAggregate",
    "StatusCount",
]
