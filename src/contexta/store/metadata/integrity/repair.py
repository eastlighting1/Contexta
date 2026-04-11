"""Repair planning helpers for metadata integrity findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .report import IntegrityReport


ISSUE_ACTION_MAP = {
    "missing_run_project": "review_or_remove_run",
    "missing_stage_run": "review_or_remove_stage",
    "missing_environment_run": "review_or_remove_environment",
    "missing_relation_source": "review_or_remove_relation",
    "missing_relation_target": "review_or_remove_relation",
    "missing_provenance_relation": "review_or_remove_provenance",
    "duplicate_stage_name_for_run": "review_stage_ambiguity",
    "malformed_registered_ref": "quarantine_registered_ref",
    "run_time_window_inverted": "review_temporal_inconsistency",
    "stage_time_window_inverted": "review_temporal_inconsistency",
    "registry_owner_mismatch": "rebuild_registry_entry",
}


@dataclass(frozen=True, slots=True)
class RepairCandidate:
    issue_code: str
    ref: str | None
    action: str
    rationale: str


@dataclass(frozen=True, slots=True)
class RepairPlan:
    ok: bool
    candidates: tuple[RepairCandidate, ...] = ()
    actions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RepairPreview:
    plan: RepairPlan
    summary_lines: tuple[str, ...] = ()


def plan_repairs(report: IntegrityReport | None = None) -> RepairPlan:
    """Convert an integrity report into operator-facing repair candidates."""

    if report is None or report.ok:
        return RepairPlan(ok=True, candidates=(), actions=())

    candidates = []
    actions: list[str] = []
    for issue in report.issues:
        action = ISSUE_ACTION_MAP.get(issue.code, issue.suggested_action or "review")
        rationale = issue.message
        candidates.append(
            RepairCandidate(
                issue_code=issue.code,
                ref=issue.ref,
                action=action,
                rationale=rationale,
            )
        )
        if action not in actions:
            actions.append(action)
    return RepairPlan(ok=False, candidates=tuple(candidates), actions=tuple(actions))


def preview_repairs(plan: RepairPlan | None = None) -> RepairPreview:
    """Build a short operator summary for a repair plan."""

    if plan is None or plan.ok:
        return RepairPreview(plan=plan or RepairPlan(ok=True), summary_lines=("No repair actions are required.",))

    lines = [f"{len(plan.candidates)} repair candidate(s) identified."]
    for candidate in plan.candidates:
        target = candidate.ref or "<store>"
        lines.append(f"{candidate.action}: {target} ({candidate.issue_code})")
    return RepairPreview(plan=plan, summary_lines=tuple(lines))


__all__ = [
    "RepairCandidate",
    "RepairPlan",
    "RepairPreview",
    "plan_repairs",
    "preview_repairs",
]
