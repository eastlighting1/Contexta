"""Report builder helpers over typed interpretation results."""

from __future__ import annotations

from ..alert import AlertResult
from ..compare import CompletenessNote, MultiRunComparison, RunComparison
from ..diagnostics import DiagnosticsResult
from ..query import RunSnapshot
from ..repositories import RunRecord
from ..trend import MetricTrend
from .models import ReportDocument, ReportSection


class ReportBuilder:
    """Build report documents from already-computed interpretation results."""

    def build_snapshot_report(
        self,
        snapshot: RunSnapshot,
        diagnostics: DiagnosticsResult,
    ) -> ReportDocument:
        sections = [
            ReportSection(
                title="Run Summary",
                body="\n".join(
                    (
                        f"run_id: {snapshot.run.run_id}",
                        f"name: {snapshot.run.name}",
                        f"status: {snapshot.run.status}",
                        f"project: {snapshot.run.project_name}",
                    )
                ),
                evidence_links=tuple(link for link in snapshot.evidence_links if link.kind == "run"),
            ),
            ReportSection(
                title="Stages",
                body="\n".join(
                    f"{stage.name}: status={stage.status}, stage_id={stage.stage_id}"
                    for stage in snapshot.stages
                )
                or "No stages.",
                evidence_links=tuple(link for link in snapshot.evidence_links if link.kind == "stage"),
            ),
            ReportSection(
                title="Artifacts",
                body="\n".join(
                    f"{artifact.kind}: ref={artifact.artifact_ref}, location={artifact.location}"
                    for artifact in snapshot.artifacts
                )
                or "No artifacts.",
                evidence_links=tuple(link for link in snapshot.evidence_links if link.kind == "artifact"),
            ),
            ReportSection(
                title="Batches",
                body="\n".join(
                    f"{batch.name}: stage={batch.stage_id.split('.')[-1] if batch.stage_id else '?'}"
                    f", status={batch.status}"
                    f", order={batch.order}"
                    for batch in snapshot.batches
                )
                or "No batches.",
                evidence_links=tuple(link for link in snapshot.evidence_links if link.kind == "batch"),
            ),
            ReportSection(
                title="Deployments",
                body="\n".join(
                    f"{deployment.name}: status={deployment.status}"
                    + (f", run_id={deployment.run_id}" if deployment.run_id else "")
                    + (f", artifact_ref={deployment.artifact_ref}" if deployment.artifact_ref else "")
                    for deployment in snapshot.deployments
                )
                or "No deployments.",
                evidence_links=tuple(link for link in snapshot.evidence_links if link.kind == "deployment"),
            ),
            ReportSection(
                title="Samples",
                body="\n".join(
                    f"{sample.name}: observed_at={sample.observed_at}"
                    + (f", retention={sample.retention_class}" if sample.retention_class else "")
                    + (f", redaction={sample.redaction_profile}" if sample.redaction_profile else "")
                    for sample in snapshot.samples[:20]
                )
                + (f"\n... and {len(snapshot.samples) - 20} more." if len(snapshot.samples) > 20 else "")
                or "No samples.",
                evidence_links=tuple(link for link in snapshot.evidence_links if link.kind == "sample"),
            ),
            ReportSection(
                title="Diagnostics",
                body="\n".join(
                    f"{issue.severity}:{issue.code}: {issue.summary}"
                    for issue in diagnostics.issues
                )
                or "No diagnostics issues.",
                evidence_links=diagnostics.evidence_links,
            ),
            ReportSection(
                title="Completeness Notes",
                body=_render_completeness_lines(
                    tuple(
                        list(_notes_from_strings(snapshot.completeness_notes))
                        + list(diagnostics.completeness_notes)
                    )
                ),
            ),
        ]
        if snapshot.provenance is not None:
            sections.append(
                ReportSection(
                    title="Provenance",
                    body="\n".join(
                        (
                            f"provenance_ref: {snapshot.provenance.provenance_ref}",
                            f"relation_ref: {snapshot.provenance.relation_ref}",
                            f"assertion_mode: {snapshot.provenance.assertion_mode}",
                            f"asserted_at: {snapshot.provenance.asserted_at}",
                        )
                    ),
                    evidence_links=tuple(
                        link for link in snapshot.evidence_links if link.kind in {"run", "artifact"}
                    ),
                )
            )
        return ReportDocument(
            title=f"Run Snapshot Report: {snapshot.run.run_id}",
            sections=tuple(sections),
        )

    def build_run_report(
        self,
        comparison: RunComparison,
        diagnostics: DiagnosticsResult,
    ) -> ReportDocument:
        sections = (
            ReportSection(
                title="Summary",
                body=comparison.summary,
                evidence_links=comparison.evidence_links,
            ),
            ReportSection(
                title="Metric Deltas",
                body="\n".join(
                    f"{stage.stage_name}/{delta.metric_key}: left={delta.left_value}, right={delta.right_value}, delta={delta.delta}"
                    for stage in comparison.stage_comparisons
                    for delta in stage.metric_deltas
                )
                or "No metric deltas.",
            ),
            ReportSection(
                title="Artifact Changes",
                body="\n".join(
                    f"{change.artifact_kind}: {change.change} ({change.left_ref} -> {change.right_ref})"
                    for change in comparison.artifact_changes
                )
                or "No artifact changes.",
            ),
            ReportSection(
                title="Diagnostics",
                body="\n".join(
                    f"{issue.severity}:{issue.code}: {issue.summary}"
                    for issue in diagnostics.issues
                )
                or "No diagnostics issues.",
                evidence_links=diagnostics.evidence_links,
            ),
            ReportSection(
                title="Completeness Notes",
                body=_render_completeness_lines(
                    tuple(list(comparison.completeness_notes) + list(diagnostics.completeness_notes))
                ),
            ),
        )
        section_list = list(sections)
        if comparison.provenance_comparison is not None:
            section_list.append(
                ReportSection(
                    title="Provenance",
                    body="\n".join(
                        (
                            f"code_revision_changed: {comparison.provenance_comparison.code_revision_changed}",
                            f"config_hash_changed: {comparison.provenance_comparison.config_hash_changed}",
                            f"environment_changed: {comparison.provenance_comparison.environment_changed}",
                            f"dataset_refs_changed: {comparison.provenance_comparison.dataset_refs_changed}",
                        )
                    ),
                )
            )
        return ReportDocument(
            title=f"Run Comparison Report: {comparison.left_run_id} vs {comparison.right_run_id}",
            sections=tuple(section_list),
        )

    def build_project_summary_report(
        self,
        project_name: str,
        *,
        runs: tuple[RunRecord, ...] = (),
        notes: tuple[CompletenessNote, ...] = (),
    ) -> ReportDocument:
        return ReportDocument(
            title=f"Project Summary Report: {project_name}",
            sections=(
                ReportSection(
                    title="Runs",
                    body="\n".join(
                        f"{run.run_id}: name={run.name}, status={run.status}, started_at={run.started_at}"
                        for run in runs
                    )
                    or "No runs.",
                ),
                ReportSection(
                    title="Completeness Notes",
                    body=_render_completeness_lines(notes),
                ),
            ),
        )

    def build_trend_report(self, trend: MetricTrend) -> ReportDocument:
        return ReportDocument(
            title=f"Trend Report: {trend.metric_key}",
            sections=(
                ReportSection(
                    title="Series",
                    body="\n".join(
                        f"{point.run_id}: value={point.value}, captured_at={point.captured_at}"
                        for point in trend.points
                    )
                    or "No series points.",
                ),
                ReportSection(
                    title="Completeness Notes",
                    body=_render_completeness_lines(trend.completeness_notes),
                ),
            ),
        )

    def build_alert_report(self, results: list[AlertResult] | tuple[AlertResult, ...]) -> ReportDocument:
        triggered = [result for result in results if result.triggered]
        passed = [result for result in results if not result.triggered]
        return ReportDocument(
            title="Alert Report",
            sections=(
                ReportSection(
                    title="Triggered",
                    body="\n".join(
                        f"{result.run_id}: {result.rule_name} actual={result.actual_value} threshold={result.threshold}"
                        for result in triggered
                    )
                    or "No triggered alerts.",
                ),
                ReportSection(
                    title="Passed",
                    body="\n".join(
                        f"{result.run_id}: {result.rule_name} actual={result.actual_value} threshold={result.threshold}"
                        for result in passed
                    )
                    or "No passing alerts.",
                ),
            ),
        )

    def build_multi_run_report(self, comparison: MultiRunComparison) -> ReportDocument:
        return ReportDocument(
            title=f"Multi Run Report: {len(comparison.run_ids)} runs",
            sections=(
                ReportSection(
                    title="Summary",
                    body=comparison.summary,
                    evidence_links=comparison.evidence_links,
                ),
                ReportSection(
                    title="Run IDs",
                    body="\n".join(comparison.run_ids),
                ),
                ReportSection(
                    title="Metric Table",
                    body="\n".join(
                        f"{row.stage_name or 'run'}/{row.metric_key}: {row.values}"
                        for row in comparison.metric_table
                    )
                    or "No metric rows.",
                ),
                ReportSection(
                    title="Completeness Notes",
                    body=_render_completeness_lines(comparison.completeness_notes),
                ),
            ),
        )


def _notes_from_strings(values: tuple[str, ...]) -> tuple[CompletenessNote, ...]:
    return tuple(
        CompletenessNote(severity="warning", summary=value, details={})
        for value in values
    )


def _render_completeness_lines(notes: tuple[CompletenessNote, ...]) -> str:
    if not notes:
        return "No completeness notes."
    return "\n".join(f"{note.severity}: {note.summary}" for note in notes)


__all__ = ["ReportBuilder"]
