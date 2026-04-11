"""Reproducibility and environment diff service over interpretation queries."""

from __future__ import annotations

from ...common.errors import InterpretationError
from ..compare import CompletenessNote
from ..query import EvidenceLink, QueryService
from .models import EnvironmentDiff, EnvironmentValueChange, ReproducibilityAudit


class ProvenanceError(InterpretationError):
    """Raised for provenance-specific failures."""


class ProvenanceService:
    """Read-only provenance service layered on top of QueryService."""

    def __init__(self, query_service: QueryService) -> None:
        self.query_service = query_service

    def audit_reproducibility(self, run_id: str) -> ReproducibilityAudit:
        snapshot = self.query_service.get_run_snapshot(run_id)
        environment = self._get_latest_environment_snapshot(snapshot.run.run_id)
        notes: list[CompletenessNote] = []
        if snapshot.provenance is None:
            notes.append(
                CompletenessNote(
                    severity="warning",
                    summary="provenance_missing",
                    details={"run_id": snapshot.run.run_id},
                )
            )
        if environment is None:
            notes.append(
                CompletenessNote(
                    severity="warning",
                    summary="environment_snapshot_missing",
                    details={"run_id": snapshot.run.run_id},
                )
            )
        elif not environment.packages:
            notes.append(
                CompletenessNote(
                    severity="info",
                    summary="environment_packages_empty",
                    details={"run_id": snapshot.run.run_id, "environment_ref": str(environment.environment_snapshot_ref)},
                )
            )
        if snapshot.provenance is not None and snapshot.provenance.evidence_bundle_ref is None:
            notes.append(
                CompletenessNote(
                    severity="info",
                    summary="provenance_evidence_bundle_missing",
                    details={"run_id": snapshot.run.run_id, "provenance_ref": snapshot.provenance.provenance_ref},
                )
            )

        evidence_links = [EvidenceLink(kind="run", ref=snapshot.run.run_id, label=snapshot.run.name)]
        if snapshot.provenance is not None:
            evidence_links.append(
                EvidenceLink(
                    kind="provenance",
                    ref=snapshot.provenance.provenance_ref,
                    label=snapshot.provenance.assertion_mode,
                )
            )
        if environment is not None:
            evidence_links.append(
                EvidenceLink(
                    kind="environment",
                    ref=str(environment.environment_snapshot_ref),
                    label=environment.platform,
                )
            )

        return ReproducibilityAudit(
            run_id=snapshot.run.run_id,
            provenance=snapshot.provenance,
            environment_ref=None if environment is None else str(environment.environment_snapshot_ref),
            python_version=None if environment is None else environment.python_version,
            platform=None if environment is None else environment.platform,
            package_count=0 if environment is None else len(environment.packages),
            environment_variable_count=0 if environment is None else len(environment.environment_variables),
            reproducibility_status=_derive_reproducibility_status(
                has_provenance=snapshot.provenance is not None,
                has_environment=environment is not None,
            ),
            completeness_notes=tuple(notes),
            evidence_links=tuple(evidence_links),
        )

    def compare_environments(self, left_run_id: str, right_run_id: str) -> EnvironmentDiff:
        left_snapshot = self.query_service.get_run_snapshot(left_run_id)
        right_snapshot = self.query_service.get_run_snapshot(right_run_id)
        left_environment = self._get_latest_environment_snapshot(left_snapshot.run.run_id)
        right_environment = self._get_latest_environment_snapshot(right_snapshot.run.run_id)

        notes: list[CompletenessNote] = []
        if left_environment is None:
            notes.append(
                CompletenessNote(
                    severity="warning",
                    summary="left_environment_snapshot_missing",
                    details={"run_id": left_snapshot.run.run_id},
                )
            )
        if right_environment is None:
            notes.append(
                CompletenessNote(
                    severity="warning",
                    summary="right_environment_snapshot_missing",
                    details={"run_id": right_snapshot.run.run_id},
                )
            )

        left_packages = {} if left_environment is None else dict(left_environment.packages)
        right_packages = {} if right_environment is None else dict(right_environment.packages)
        left_variables = {} if left_environment is None else dict(left_environment.environment_variables)
        right_variables = {} if right_environment is None else dict(right_environment.environment_variables)

        evidence_links = [
            EvidenceLink(kind="run", ref=left_snapshot.run.run_id, label=left_snapshot.run.name),
            EvidenceLink(kind="run", ref=right_snapshot.run.run_id, label=right_snapshot.run.name),
        ]
        if left_environment is not None:
            evidence_links.append(
                EvidenceLink(
                    kind="environment",
                    ref=str(left_environment.environment_snapshot_ref),
                    label=left_environment.platform,
                )
            )
        if right_environment is not None:
            evidence_links.append(
                EvidenceLink(
                    kind="environment",
                    ref=str(right_environment.environment_snapshot_ref),
                    label=right_environment.platform,
                )
            )

        return EnvironmentDiff(
            left_run_id=left_snapshot.run.run_id,
            right_run_id=right_snapshot.run.run_id,
            left_environment_ref=None if left_environment is None else str(left_environment.environment_snapshot_ref),
            right_environment_ref=None if right_environment is None else str(right_environment.environment_snapshot_ref),
            python_version_changed=_normalize_env_value(left_environment, "python_version")
            != _normalize_env_value(right_environment, "python_version"),
            platform_changed=_normalize_env_value(left_environment, "platform")
            != _normalize_env_value(right_environment, "platform"),
            added_packages=_added_entries(left_packages, right_packages),
            removed_packages=_removed_entries(left_packages, right_packages),
            changed_packages=_changed_entries(left_packages, right_packages),
            added_variables=_added_entries(left_variables, right_variables),
            removed_variables=_removed_entries(left_variables, right_variables),
            changed_variables=_changed_entries(left_variables, right_variables),
            completeness_notes=tuple(notes),
            evidence_links=tuple(evidence_links),
        )

    def _get_latest_environment_snapshot(self, run_id: str):
        metadata_store = getattr(self.query_service.repository, "metadata_store", None)
        if metadata_store is None:
            raise ProvenanceError(
                "Composite repository does not expose metadata_store.",
                code="provenance_metadata_store_unavailable",
                details={"repository_type": type(self.query_service.repository).__name__},
            )
        snapshots = metadata_store.environments.list_environment_snapshots(run_id)
        if not snapshots:
            return None
        return sorted(snapshots, key=lambda item: item.captured_at)[-1]


def _derive_reproducibility_status(*, has_provenance: bool, has_environment: bool) -> str:
    if has_provenance and has_environment:
        return "complete"
    if has_provenance or has_environment:
        return "partial"
    return "missing"


def _normalize_env_value(snapshot, field_name: str) -> str | None:
    if snapshot is None:
        return None
    return getattr(snapshot, field_name)


def _added_entries(left: dict[str, str], right: dict[str, str]) -> tuple[EnvironmentValueChange, ...]:
    return tuple(
        EnvironmentValueChange(key=key, left_value=None, right_value=right[key])
        for key in sorted(set(right) - set(left))
    )


def _removed_entries(left: dict[str, str], right: dict[str, str]) -> tuple[EnvironmentValueChange, ...]:
    return tuple(
        EnvironmentValueChange(key=key, left_value=left[key], right_value=None)
        for key in sorted(set(left) - set(right))
    )


def _changed_entries(left: dict[str, str], right: dict[str, str]) -> tuple[EnvironmentValueChange, ...]:
    return tuple(
        EnvironmentValueChange(key=key, left_value=left[key], right_value=right[key])
        for key in sorted(set(left) & set(right))
        if left[key] != right[key]
    )


__all__ = ["ProvenanceError", "ProvenanceService"]
