"""Public compare surface for interpretation workflows."""

from .models import (
    ArtifactChange,
    ArtifactKindCountRow,
    CompletenessNote,
    MetricDelta,
    MultiRunComparison,
    MultiRunMetricRow,
    ProvenanceComparison,
    ReportComparison,
    RunComparison,
    SectionDiff,
    StageComparison,
)
from .service import CompareService, ComparisonError, ComparisonPolicy

__all__ = [
    "ArtifactChange",
    "ArtifactKindCountRow",
    "CompareService",
    "CompletenessNote",
    "ComparisonError",
    "ComparisonPolicy",
    "MetricDelta",
    "MultiRunComparison",
    "MultiRunMetricRow",
    "ProvenanceComparison",
    "ReportComparison",
    "RunComparison",
    "SectionDiff",
    "StageComparison",
]
