"""Integrity report model and scan logic for the metadata store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ....common.errors import IntegrityError
from ....common.time import iso_utc_now
from ....contract import StableRef


def _freeze_counts(values: Mapping[str, int] | None) -> dict[str, int]:
    if not values:
        return {}
    return {key: int(values[key]) for key in sorted(values)}


@dataclass(frozen=True, slots=True)
class IntegrityIssue:
    code: str
    message: str
    rule_id: str | None = None
    category: str = "integrity"
    severity: str = "error"
    ref: str | None = None
    suggested_action: str | None = None
    details: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.code or not self.message:
            raise ValueError("IntegrityIssue requires non-empty code and message.")
        if self.severity not in {"error", "warning"}:
            raise ValueError("IntegrityIssue.severity must be 'error' or 'warning'.")


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    ok: bool
    store_schema_version: str
    checked_at: str
    issues: tuple[IntegrityIssue, ...] = ()
    issue_counts: Mapping[str, int] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))
        if self.issue_counts is None:
            counts: dict[str, int] = {"error": 0, "warning": 0}
            for issue in self.issues:
                counts[issue.severity] = counts.get(issue.severity, 0) + 1
            object.__setattr__(self, "issue_counts", _freeze_counts(counts))
        else:
            object.__setattr__(self, "issue_counts", _freeze_counts(self.issue_counts))


def check_integrity(store: Any, *, full: bool = True) -> IntegrityReport:
    """Scan the persisted metadata store for integrity findings."""

    issues: list[IntegrityIssue] = []
    backend = store._backend

    project_refs = {str(row[0]) for row in backend.fetchall("SELECT ref FROM projects")}
    run_rows = backend.fetchall("SELECT ref, project_ref, started_at, payload_json FROM runs")
    stage_rows = backend.fetchall("SELECT ref, run_ref, stage_name, started_at, payload_json FROM stage_executions")
    environment_rows = backend.fetchall("SELECT ref, run_ref, payload_json FROM environment_snapshots")
    relation_rows = backend.fetchall("SELECT ref, source_ref, target_ref, payload_json FROM relations")
    provenance_rows = backend.fetchall("SELECT ref, relation_ref, payload_json FROM provenance_records")
    registered_rows = backend.fetchall("SELECT ref, ref_kind, owner_kind FROM structural_ref_registry")

    run_refs = {str(row[0]) for row in run_rows}
    stage_refs = {str(row[0]) for row in stage_rows}
    environment_refs = {str(row[0]) for row in environment_rows}
    relation_refs = {str(row[0]) for row in relation_rows}
    provenance_refs = {str(row[0]) for row in provenance_rows}
    registered_refs = {str(row[0]) for row in registered_rows}

    known_refs = project_refs | run_refs | stage_refs | environment_refs | relation_refs | provenance_refs | registered_refs

    for ref, project_ref, _started_at, _payload in run_rows:
        if str(project_ref) not in project_refs:
            issues.append(
                IntegrityIssue(
                    code="missing_run_project",
                    message="Run references a missing owning project.",
                    ref=str(ref),
                    suggested_action="review_or_remove_run",
                    details={"project_ref": str(project_ref)},
                )
            )

    stage_name_counts: dict[tuple[str, str], int] = {}
    for ref, run_ref, stage_name, _started_at, _payload in stage_rows:
        if str(run_ref) not in run_refs:
            issues.append(
                IntegrityIssue(
                    code="missing_stage_run",
                    message="Stage execution references a missing owning run.",
                    ref=str(ref),
                    suggested_action="review_or_remove_stage",
                    details={"run_ref": str(run_ref)},
                )
            )
        key = (str(run_ref), str(stage_name))
        stage_name_counts[key] = stage_name_counts.get(key, 0) + 1

    for (run_ref, stage_name), count in stage_name_counts.items():
        if count > 1:
            issues.append(
                IntegrityIssue(
                    code="duplicate_stage_name_for_run",
                    message="Multiple stage rows share the same run_ref and stage_name.",
                    severity="warning",
                    ref=run_ref,
                    suggested_action="review_stage_ambiguity",
                    details={"run_ref": run_ref, "stage_name": stage_name, "count": count},
                )
            )

    for ref, run_ref, _payload in environment_rows:
        if str(run_ref) not in run_refs:
            issues.append(
                IntegrityIssue(
                    code="missing_environment_run",
                    message="Environment snapshot references a missing owning run.",
                    ref=str(ref),
                    suggested_action="review_or_remove_environment",
                    details={"run_ref": str(run_ref)},
                )
            )

    for ref, source_ref, target_ref, _payload in relation_rows:
        if str(source_ref) not in known_refs:
            issues.append(
                IntegrityIssue(
                    code="missing_relation_source",
                    message="Relation source ref cannot be resolved.",
                    ref=str(ref),
                    suggested_action="review_or_remove_relation",
                    details={"source_ref": str(source_ref)},
                )
            )
        if str(target_ref) not in known_refs:
            issues.append(
                IntegrityIssue(
                    code="missing_relation_target",
                    message="Relation target ref cannot be resolved.",
                    ref=str(ref),
                    suggested_action="review_or_remove_relation",
                    details={"target_ref": str(target_ref)},
                )
            )

    for ref, relation_ref, _payload in provenance_rows:
        if str(relation_ref) not in relation_refs:
            issues.append(
                IntegrityIssue(
                    code="missing_provenance_relation",
                    message="Provenance row references a missing relation.",
                    ref=str(ref),
                    suggested_action="review_or_remove_provenance",
                    details={"relation_ref": str(relation_ref)},
                )
            )

    if full:
        for ref, ref_kind, owner_kind in registered_rows:
            try:
                parsed = StableRef.parse(str(ref))
            except Exception:
                issues.append(
                    IntegrityIssue(
                        code="malformed_registered_ref",
                        message="Registered ref is not valid canonical StableRef text.",
                        severity="warning",
                        ref=str(ref),
                        suggested_action="quarantine_registered_ref",
                        details={"ref_kind": str(ref_kind), "owner_kind": str(owner_kind)},
                    )
                )
                continue
            expected_owner = {
                "project": "project",
                "run": "run",
                "stage": "stage_execution",
                "environment": "environment_snapshot",
                "relation": "relation",
                "provenance": "provenance",
            }.get(parsed.kind)
            if expected_owner is not None and expected_owner != str(owner_kind):
                issues.append(
                    IntegrityIssue(
                        code="registry_owner_mismatch",
                        message="Registered ref owner kind does not match the canonical row family.",
                        severity="warning",
                        ref=str(ref),
                        suggested_action="rebuild_registry_entry",
                        details={"expected_owner_kind": expected_owner, "actual_owner_kind": str(owner_kind)},
                    )
                )

    report = IntegrityReport(
        ok=not issues,
        store_schema_version=store.get_store_schema_version(),
        checked_at=iso_utc_now(),
        issues=tuple(issues),
    )
    return report


__all__ = ["IntegrityIssue", "IntegrityReport", "check_integrity"]
