"""Diagnostics service over interpretation query snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from ...common.errors import InterpretationError, ValidationError
from ..compare import CompletenessNote
from ..query import EvidenceLink, QueryService, RunSnapshot
from ..repositories import BatchRecord, DeploymentRecord, ObservationRecord, SampleRecord, StageRecord
from .models import DiagnosticsIssue, DiagnosticsResult


@dataclass(frozen=True, slots=True)
class DiagnosticsPolicy:
    require_metrics_for_completed_stages: bool = True
    detect_degraded_records: bool = True
    expected_terminal_stage_names: tuple[str, ...] = ("evaluate", "package")

    def __post_init__(self) -> None:
        object.__setattr__(self, "expected_terminal_stage_names", tuple(self.expected_terminal_stage_names))
        for stage_name in self.expected_terminal_stage_names:
            if not isinstance(stage_name, str) or not stage_name.strip():
                raise ValidationError(
                    "expected_terminal_stage_names must contain non-blank strings.",
                    code="diagnostics_invalid_expected_stage_name",
                    details={"stage_name": stage_name},
                )


class DiagnosticsError(InterpretationError):
    """Raised for diagnostics-specific failures."""


class DiagnosticsService:
    """Read-only diagnostics service layered on top of QueryService."""

    def __init__(
        self,
        query_service: QueryService,
        *,
        config: DiagnosticsPolicy | None = None,
    ) -> None:
        self.query_service = query_service
        self.config = config or DiagnosticsPolicy()

    def diagnose_run(self, run_id: str) -> DiagnosticsResult:
        snapshot = self.query_service.get_run_snapshot(run_id)
        issues: list[DiagnosticsIssue] = []

        if self.config.detect_degraded_records:
            for record in snapshot.records:
                if record.degradation_marker == "none":
                    continue
                issues.append(
                    DiagnosticsIssue(
                        severity="warning",
                        code="degraded_record",
                        summary=f"degraded record detected for {record.key}",
                        details={
                            "record_type": record.record_type,
                            "degradation_marker": record.degradation_marker,
                            "stage_id": record.stage_id,
                        },
                        subject_ref=record.record_id,
                        evidence_links=(
                            EvidenceLink(kind="record", ref=record.record_id, label=record.key),
                        ),
                    )
                )

        stage_metrics = self._stage_metric_presence(snapshot.records)
        for stage in snapshot.stages:
            if stage.status != "completed":
                issues.append(
                    DiagnosticsIssue(
                        severity="warning",
                        code="incomplete_stage",
                        summary=f"stage {stage.name} is not completed",
                        details={"status": stage.status, "run_id": snapshot.run.run_id},
                        subject_ref=stage.stage_id,
                        evidence_links=(EvidenceLink(kind="stage", ref=stage.stage_id, label=stage.name),),
                    )
                )
            if self.config.require_metrics_for_completed_stages and stage.status == "completed":
                if not stage_metrics.get(stage.stage_id, False):
                    issues.append(
                        DiagnosticsIssue(
                            severity="info",
                            code="missing_stage_metrics",
                            summary=f"completed stage {stage.name} has no metric records",
                            details={"stage_name": stage.name, "run_id": snapshot.run.run_id},
                            subject_ref=stage.stage_id,
                            evidence_links=(EvidenceLink(kind="stage", ref=stage.stage_id, label=stage.name),),
                        )
                    )

        for batch in snapshot.batches:
            if batch.status == "failed":
                issues.append(
                    DiagnosticsIssue(
                        severity="error",
                        code="failed_batch",
                        summary=f"batch {batch.name} failed",
                        details={"batch_id": batch.batch_id, "stage_id": batch.stage_id, "run_id": snapshot.run.run_id},
                        subject_ref=batch.batch_id,
                        evidence_links=(EvidenceLink(kind="batch", ref=batch.batch_id, label=batch.name),),
                    )
                )
            elif batch.status not in ("completed", "open"):
                issues.append(
                    DiagnosticsIssue(
                        severity="warning",
                        code="incomplete_batch",
                        summary=f"batch {batch.name} ended with status {batch.status}",
                        details={"batch_id": batch.batch_id, "status": batch.status, "run_id": snapshot.run.run_id},
                        subject_ref=batch.batch_id,
                        evidence_links=(EvidenceLink(kind="batch", ref=batch.batch_id, label=batch.name),),
                    )
                )

        for deployment in snapshot.deployments:
            if deployment.status == "failed":
                issues.append(
                    DiagnosticsIssue(
                        severity="error",
                        code="failed_deployment",
                        summary=f"deployment {deployment.name} failed",
                        details={"deployment_id": deployment.deployment_id, "run_id": snapshot.run.run_id},
                        subject_ref=deployment.deployment_id,
                        evidence_links=(EvidenceLink(kind="deployment", ref=deployment.deployment_id, label=deployment.name),),
                    )
                )
        present_stage_names = {stage.name for stage in snapshot.stages}
        for expected_stage_name in self.config.expected_terminal_stage_names:
            if expected_stage_name in present_stage_names:
                continue
            issues.append(
                DiagnosticsIssue(
                    severity="info",
                    code="missing_expected_stage",
                    summary=f"expected terminal stage {expected_stage_name} is missing",
                    details={"expected_stage_name": expected_stage_name, "run_id": snapshot.run.run_id},
                    subject_ref=snapshot.run.run_id,
                    evidence_links=(EvidenceLink(kind="run", ref=snapshot.run.run_id, label=snapshot.run.name),),
                )
            )

        completeness_notes = tuple(
            CompletenessNote(
                severity="warning",
                summary=note,
                details={"run_id": snapshot.run.run_id},
            )
            for note in snapshot.completeness_notes
        )
        evidence_links = tuple(
            dict.fromkeys(
                snapshot.evidence_links + tuple(link for issue in issues for link in issue.evidence_links)
            )
        )
        return DiagnosticsResult(
            run_id=snapshot.run.run_id,
            issues=tuple(issues),
            completeness_notes=completeness_notes,
            evidence_links=evidence_links,
        )

    def _stage_metric_presence(self, records: tuple[ObservationRecord, ...]) -> dict[str, bool]:
        stage_metrics: dict[str, bool] = {}
        for record in records:
            if record.stage_id is None:
                continue
            if record.record_type != "metric":
                stage_metrics.setdefault(record.stage_id, False)
                continue
            stage_metrics[record.stage_id] = True
        return stage_metrics


__all__ = ["DiagnosticsError", "DiagnosticsPolicy", "DiagnosticsService"]
