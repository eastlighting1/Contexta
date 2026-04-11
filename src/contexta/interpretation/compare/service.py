"""Comparison services over interpretation query results."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

from ...common.errors import InterpretationError, ValidationError
from ..query import EvidenceLink, QueryService, RunSnapshot
from ..repositories import ArtifactRecord, ObservationRecord, StageRecord
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


@dataclass(frozen=True, slots=True)
class ComparisonPolicy:
    metric_selection: str = "latest"
    include_unchanged_metrics: bool = False
    missing_stage_severity: str = "warning"

    def __post_init__(self) -> None:
        if self.metric_selection not in {"latest", "max", "min", "mean"}:
            raise ValidationError(
                "Unsupported comparison metric selection.",
                code="compare_invalid_metric_selection",
                details={"metric_selection": self.metric_selection},
            )
        if self.missing_stage_severity not in {"info", "warning", "error"}:
            raise ValidationError(
                "Unsupported missing-stage severity.",
                code="compare_invalid_missing_stage_severity",
                details={"missing_stage_severity": self.missing_stage_severity},
            )


class ComparisonError(InterpretationError):
    """Raised for compare-specific failures."""


class CompareService:
    """Read-only comparison service layered on top of QueryService."""

    def __init__(
        self,
        query_service: QueryService,
        *,
        config: ComparisonPolicy | None = None,
    ) -> None:
        self.query_service = query_service
        self.config = config or ComparisonPolicy()

    def compare_runs(self, left_run_id: str, right_run_id: str) -> RunComparison:
        left = self.query_service.get_run_snapshot(left_run_id)
        right = self.query_service.get_run_snapshot(right_run_id)

        left_stages = {stage.name: stage for stage in left.stages}
        right_stages = {stage.name: stage for stage in right.stages}
        stage_names = tuple(sorted(set(left_stages) | set(right_stages)))

        stage_comparisons = tuple(
            self._compare_stage(
                stage_name,
                left_stage=left_stages.get(stage_name),
                right_stage=right_stages.get(stage_name),
                left_snapshot=left,
                right_snapshot=right,
            )
            for stage_name in stage_names
        )
        artifact_changes = self._compare_artifacts(left.artifacts, right.artifacts)
        completeness_notes = self._combine_notes(
            self._snapshot_notes(left, side="left"),
            self._snapshot_notes(right, side="right"),
            *(stage.completeness_notes for stage in stage_comparisons),
        )
        evidence_links = tuple(
            dict.fromkeys(
                left.evidence_links
                + right.evidence_links
                + tuple(link for stage in stage_comparisons for link in stage.evidence_links)
                + tuple(link for change in artifact_changes for link in change.evidence_links)
            )
        )
        provenance_comparison = self._compare_provenance(left, right)
        summary = (
            f"Compared {left.run.name} and {right.run.name}: "
            f"{len(stage_comparisons)} stage rows, "
            f"{sum(len(stage.metric_deltas) for stage in stage_comparisons)} metric deltas, "
            f"{len(artifact_changes)} artifact changes."
        )
        return RunComparison(
            left_run_id=left.run.run_id,
            right_run_id=right.run.run_id,
            summary=summary,
            stage_comparisons=stage_comparisons,
            artifact_changes=artifact_changes,
            completeness_notes=completeness_notes,
            evidence_links=evidence_links,
            provenance_comparison=provenance_comparison,
        )

    def compare_multiple_runs(self, run_ids: Sequence[str]) -> MultiRunComparison:
        unique_run_ids = tuple(dict.fromkeys(run_ids))
        if len(unique_run_ids) < 2:
            raise ComparisonError(
                "compare_multiple_runs requires at least two runs.",
                code="compare_requires_multiple_runs",
                details={"run_ids": tuple(run_ids)},
            )
        snapshots = tuple(self.query_service.get_run_snapshot(run_id) for run_id in unique_run_ids)
        run_names = tuple(snapshot.run.name for snapshot in snapshots)

        metric_values: dict[tuple[str | None, str], list[float | None]] = {}
        for index, snapshot in enumerate(snapshots):
            stage_rows = self._metric_values_by_stage(snapshot)
            for key in set(metric_values) | set(stage_rows):
                metric_values.setdefault(key, [None] * len(snapshots))
            for key, value in stage_rows.items():
                metric_values[key][index] = value

        metric_table = []
        for stage_name, metric_key in sorted(metric_values):
            values = tuple(metric_values[(stage_name, metric_key)])
            best_run_id = self._select_best_run_from_values(unique_run_ids, values)
            metric_table.append(
                MultiRunMetricRow(
                    metric_key=metric_key,
                    stage_name=stage_name,
                    values=values,
                    best_run_id=best_run_id,
                )
            )

        artifact_counts: dict[str, list[int]] = {}
        for index, snapshot in enumerate(snapshots):
            per_kind: dict[str, int] = {}
            for artifact in snapshot.artifacts:
                per_kind[artifact.kind] = per_kind.get(artifact.kind, 0) + 1
            for kind in set(artifact_counts) | set(per_kind):
                artifact_counts.setdefault(kind, [0] * len(snapshots))
            for kind, count in per_kind.items():
                artifact_counts[kind][index] = count

        artifact_kind_counts = tuple(
            ArtifactKindCountRow(artifact_kind=kind, counts=tuple(counts))
            for kind, counts in sorted(artifact_counts.items())
        )
        completeness_notes = self._combine_notes(*(self._snapshot_notes(snapshot) for snapshot in snapshots))
        evidence_links = tuple(dict.fromkeys(link for snapshot in snapshots for link in snapshot.evidence_links))
        summary = (
            f"Compared {len(unique_run_ids)} runs: "
            f"{len(metric_table)} metric rows and {len(artifact_kind_counts)} artifact kind summaries."
        )
        return MultiRunComparison(
            run_ids=unique_run_ids,
            run_names=run_names,
            metric_table=tuple(metric_table),
            artifact_kind_counts=artifact_kind_counts,
            completeness_notes=completeness_notes,
            evidence_links=evidence_links,
            summary=summary,
        )

    def select_best_run(
        self,
        run_ids: Sequence[str],
        metric_key: str,
        *,
        stage_name: str | None = None,
        higher_is_better: bool = True,
    ) -> str | None:
        comparison = self.compare_multiple_runs(run_ids)
        candidates = [
            row
            for row in comparison.metric_table
            if row.metric_key == metric_key and row.stage_name == stage_name
        ]
        if not candidates:
            return None
        values = candidates[0].values
        selected_index = None
        selected_value = None
        for index, value in enumerate(values):
            if value is None:
                continue
            if selected_value is None:
                selected_index = index
                selected_value = value
                continue
            if higher_is_better and value > selected_value:
                selected_index = index
                selected_value = value
            if not higher_is_better and value < selected_value:
                selected_index = index
                selected_value = value
        return None if selected_index is None else comparison.run_ids[selected_index]

    def compare_report_documents(self, left: object, right: object) -> ReportComparison:
        left_title, left_sections = _extract_report(left)
        right_title, right_sections = _extract_report(right)
        section_titles = tuple(sorted(set(left_sections) | set(right_sections)))
        section_diffs = tuple(
            SectionDiff(
                section_title=title,
                left_body=left_sections.get(title),
                right_body=right_sections.get(title),
                changed=left_sections.get(title) != right_sections.get(title),
            )
            for title in section_titles
        )
        completeness_notes = []
        for title in section_titles:
            if title not in left_sections or title not in right_sections:
                completeness_notes.append(
                    CompletenessNote(
                        severity="warning",
                        summary=f"section_presence_changed:{title}",
                        details={
                            "left_present": title in left_sections,
                            "right_present": title in right_sections,
                        },
                    )
                )
        return ReportComparison(
            left_title=left_title,
            right_title=right_title,
            section_diffs=section_diffs,
            completeness_notes=tuple(completeness_notes),
        )

    def _compare_stage(
        self,
        stage_name: str,
        *,
        left_stage: StageRecord | None,
        right_stage: StageRecord | None,
        left_snapshot: RunSnapshot,
        right_snapshot: RunSnapshot,
    ) -> StageComparison:
        left_records = self._records_for_stage(left_snapshot.records, left_stage.stage_id if left_stage else None)
        right_records = self._records_for_stage(right_snapshot.records, right_stage.stage_id if right_stage else None)
        metric_deltas = self._build_metric_deltas(stage_name, left_records, right_records)

        completeness_notes: list[CompletenessNote] = []
        if left_stage is None or right_stage is None:
            completeness_notes.append(
                CompletenessNote(
                    severity=self.config.missing_stage_severity,
                    summary=f"missing_stage:{stage_name}",
                    details={
                        "left_present": left_stage is not None,
                        "right_present": right_stage is not None,
                    },
                )
            )
        evidence_links = []
        if left_stage is not None:
            evidence_links.append(EvidenceLink(kind="stage", ref=left_stage.stage_id, label=left_stage.name))
        if right_stage is not None:
            evidence_links.append(EvidenceLink(kind="stage", ref=right_stage.stage_id, label=right_stage.name))

        return StageComparison(
            stage_name=stage_name,
            left_stage_id=None if left_stage is None else left_stage.stage_id,
            right_stage_id=None if right_stage is None else right_stage.stage_id,
            left_status=None if left_stage is None else left_stage.status,
            right_status=None if right_stage is None else right_stage.status,
            metric_deltas=metric_deltas,
            completeness_notes=tuple(completeness_notes),
            evidence_links=tuple(evidence_links),
        )

    def _build_metric_deltas(
        self,
        stage_name: str,
        left_records: tuple[ObservationRecord, ...],
        right_records: tuple[ObservationRecord, ...],
    ) -> tuple[MetricDelta, ...]:
        left_values = self._metric_values(left_records)
        right_values = self._metric_values(right_records)
        metric_keys = tuple(sorted(set(left_values) | set(right_values)))
        deltas = []
        for metric_key in metric_keys:
            left_value = left_values.get(metric_key)
            right_value = right_values.get(metric_key)
            delta = None if left_value is None or right_value is None else right_value - left_value
            if left_value in {None, 0} or right_value is None:
                change_ratio = None
            else:
                change_ratio = right_value / left_value
            unchanged = left_value == right_value and left_value is not None
            if unchanged and not self.config.include_unchanged_metrics:
                continue
            completeness_notes = []
            if left_value is None or right_value is None:
                completeness_notes.append(
                    CompletenessNote(
                        severity="warning",
                        summary=f"sparse_metric_capture:{stage_name}:{metric_key}",
                        details={"left_value": left_value, "right_value": right_value},
                    )
                )
            deltas.append(
                MetricDelta(
                    metric_key=metric_key,
                    left_value=left_value,
                    right_value=right_value,
                    delta=delta,
                    change_ratio=change_ratio,
                    stage_name=stage_name,
                    completeness_notes=tuple(completeness_notes),
                )
            )
        return tuple(deltas)

    def _metric_values(self, records: tuple[ObservationRecord, ...]) -> dict[str, float]:
        by_key: dict[str, list[float]] = {}
        latest: dict[str, tuple[str, float]] = {}
        for record in records:
            if record.record_type != "metric" or record.value is None:
                continue
            value = float(record.value)
            by_key.setdefault(record.key, []).append(value)
            current = latest.get(record.key)
            if current is None or record.observed_at >= current[0]:
                latest[record.key] = (record.observed_at, value)

        if self.config.metric_selection == "latest":
            return {key: value for key, (_, value) in latest.items()}
        if self.config.metric_selection == "max":
            return {key: max(values) for key, values in by_key.items()}
        if self.config.metric_selection == "min":
            return {key: min(values) for key, values in by_key.items()}
        return {key: mean(values) for key, values in by_key.items()}

    def _metric_values_by_stage(self, snapshot: RunSnapshot) -> dict[tuple[str | None, str], float]:
        values: dict[tuple[str | None, str], float] = {}
        for stage in snapshot.stages:
            stage_records = self._records_for_stage(snapshot.records, stage.stage_id)
            for metric_key, value in self._metric_values(stage_records).items():
                values[(stage.name, metric_key)] = value
        run_level_records = tuple(
            record for record in snapshot.records if record.record_type == "metric" and record.stage_id is None
        )
        for metric_key, value in self._metric_values(run_level_records).items():
            values[(None, metric_key)] = value
        return values

    def _records_for_stage(
        self,
        records: tuple[ObservationRecord, ...],
        stage_id: str | None,
    ) -> tuple[ObservationRecord, ...]:
        return tuple(record for record in records if record.stage_id == stage_id)

    def _compare_artifacts(
        self,
        left_artifacts: tuple[ArtifactRecord, ...],
        right_artifacts: tuple[ArtifactRecord, ...],
    ) -> tuple[ArtifactChange, ...]:
        left_by_kind = _group_artifacts_by_kind(left_artifacts)
        right_by_kind = _group_artifacts_by_kind(right_artifacts)
        changes = []
        for artifact_kind in sorted(set(left_by_kind) | set(right_by_kind)):
            left_group = left_by_kind.get(artifact_kind, ())
            right_group = right_by_kind.get(artifact_kind, ())
            if not left_group and right_group:
                changes.append(
                    ArtifactChange(
                        artifact_kind=artifact_kind,
                        left_ref=None,
                        right_ref=right_group[0].artifact_ref,
                        change="added",
                        evidence_links=tuple(
                            EvidenceLink(kind="artifact", ref=item.artifact_ref, label=item.kind)
                            for item in right_group
                        ),
                    )
                )
                continue
            if left_group and not right_group:
                changes.append(
                    ArtifactChange(
                        artifact_kind=artifact_kind,
                        left_ref=left_group[0].artifact_ref,
                        right_ref=None,
                        change="removed",
                        evidence_links=tuple(
                            EvidenceLink(kind="artifact", ref=item.artifact_ref, label=item.kind)
                            for item in left_group
                        ),
                    )
                )
                continue
            if len(left_group) != 1 or len(right_group) != 1:
                changes.append(
                    ArtifactChange(
                        artifact_kind=artifact_kind,
                        left_ref=None if not left_group else left_group[0].artifact_ref,
                        right_ref=None if not right_group else right_group[0].artifact_ref,
                        change="ambiguous",
                        change_detail=f"left={len(left_group)}, right={len(right_group)}",
                    )
                )
                continue
            left_item = left_group[0]
            right_item = right_group[0]
            if (
                left_item.hash_value == right_item.hash_value
                and left_item.location == right_item.location
            ):
                continue
            detail = None
            if left_item.hash_value != right_item.hash_value and left_item.location != right_item.location:
                detail = "both_changed"
            elif left_item.hash_value != right_item.hash_value:
                detail = "hash_changed"
            elif left_item.location != right_item.location:
                detail = "location_changed"
            changes.append(
                ArtifactChange(
                    artifact_kind=artifact_kind,
                    left_ref=left_item.artifact_ref,
                    right_ref=right_item.artifact_ref,
                    change="changed",
                    change_detail=detail,
                    evidence_links=(
                        EvidenceLink(kind="artifact", ref=left_item.artifact_ref, label=left_item.kind),
                        EvidenceLink(kind="artifact", ref=right_item.artifact_ref, label=right_item.kind),
                    ),
                )
            )
        return tuple(changes)

    def _compare_provenance(
        self,
        left: RunSnapshot,
        right: RunSnapshot,
    ) -> ProvenanceComparison | None:
        if left.provenance is None and right.provenance is None:
            return None
        left_provenance = left.provenance
        right_provenance = right.provenance
        return ProvenanceComparison(
            code_revision_changed=_provenance_value(left_provenance, "formation_context_ref")
            != _provenance_value(right_provenance, "formation_context_ref"),
            config_hash_changed=_provenance_value(left_provenance, "policy_ref")
            != _provenance_value(right_provenance, "policy_ref"),
            environment_changed=tuple(sorted(left.run.metadata.items()))
            != tuple(sorted(right.run.metadata.items())),
            dataset_refs_changed=_provenance_value(left_provenance, "evidence_bundle_ref")
            != _provenance_value(right_provenance, "evidence_bundle_ref"),
            left_provenance=left_provenance,
            right_provenance=right_provenance,
        )

    def _snapshot_notes(self, snapshot: RunSnapshot, *, side: str | None = None) -> tuple[CompletenessNote, ...]:
        prefix = "" if side is None else f"{side}:"
        return tuple(
            CompletenessNote(
                severity="warning",
                summary=f"{prefix}{note}",
                details={"run_id": snapshot.run.run_id},
            )
            for note in snapshot.completeness_notes
        )

    def _combine_notes(self, *groups: Iterable[CompletenessNote]) -> tuple[CompletenessNote, ...]:
        seen: set[tuple[str, str]] = set()
        merged: list[CompletenessNote] = []
        for group in groups:
            for note in group:
                key = (note.severity, note.summary)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(note)
        return tuple(merged)

    def _select_best_run_from_values(
        self,
        run_ids: tuple[str, ...],
        values: tuple[float | None, ...],
    ) -> str | None:
        best_index = None
        best_value = None
        for index, value in enumerate(values):
            if value is None:
                continue
            if best_value is None or value > best_value:
                best_index = index
                best_value = value
        return None if best_index is None else run_ids[best_index]


def _group_artifacts_by_kind(
    artifacts: tuple[ArtifactRecord, ...],
) -> dict[str, tuple[ArtifactRecord, ...]]:
    grouped: dict[str, list[ArtifactRecord]] = {}
    for artifact in artifacts:
        grouped.setdefault(artifact.kind, []).append(artifact)
    return {key: tuple(grouped[key]) for key in sorted(grouped)}


def _provenance_value(provenance: Any, field_name: str) -> Any:
    if provenance is None:
        return None
    return getattr(provenance, field_name, None)


def _extract_report(report: object) -> tuple[str, dict[str, str | None]]:
    payload = _coerce_report_payload(report)
    title = str(payload.get("title") or "Untitled Report")
    sections_payload = payload.get("sections") or ()
    sections: dict[str, str | None] = {}
    for section in sections_payload:
        if isinstance(section, Mapping):
            section_title = str(section.get("title") or section.get("section_title") or "Untitled Section")
            section_body = section.get("body")
        else:
            section_title = str(getattr(section, "title", getattr(section, "section_title", "Untitled Section")))
            section_body = getattr(section, "body", None)
        sections[section_title] = None if section_body is None else str(section_body)
    return title, sections


def _coerce_report_payload(report: object) -> Mapping[str, Any]:
    if isinstance(report, Mapping):
        return report
    if hasattr(report, "to_dict"):
        payload = report.to_dict()
        if isinstance(payload, Mapping):
            return payload
    if hasattr(report, "__dict__"):
        return report.__dict__
    raise ComparisonError(
        "Report document could not be normalized for comparison.",
        code="compare_invalid_report_document",
        details={"type": type(report).__name__},
    )


__all__ = ["CompareService", "ComparisonError", "ComparisonPolicy"]
