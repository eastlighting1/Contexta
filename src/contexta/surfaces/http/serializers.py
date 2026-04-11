"""HTTP JSON serializers for Contexta embedded surfaces."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from types import MappingProxyType
from typing import Any


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, MappingProxyType):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(item) for item in value]
    if is_dataclass(value):
        return {
            field.name: to_jsonable(getattr(value, field.name))
            for field in fields(value)
        }
    if hasattr(value, "to_json") and callable(value.to_json):
        return to_jsonable(value.to_json())
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return to_jsonable(value.to_dict())
    if hasattr(value, "__dict__"):
        return {
            key: to_jsonable(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return str(value)


def run_summary_payload(snapshot: Any) -> dict[str, Any]:
    return {
        "run_id": snapshot.run.run_id,
        "project_name": snapshot.run.project_name,
        "name": snapshot.run.name,
        "status": snapshot.run.status,
        "started_at": snapshot.run.started_at,
        "ended_at": snapshot.run.ended_at,
        "stages": [to_jsonable(stage) for stage in snapshot.stages],
        "artifact_count": len(snapshot.artifacts),
        "record_count": len(snapshot.records),
        "completeness_notes": list(snapshot.completeness_notes),
        "provenance": to_jsonable(snapshot.provenance),
    }


def reproducibility_payload(audit: Any) -> dict[str, Any]:
    missing_fields: list[str] = []
    if audit.provenance is None:
        missing_fields.append("provenance")
    if audit.environment_ref is None:
        missing_fields.append("environment_ref")
    return {
        "run_id": audit.run_id,
        "code_revision": None if audit.provenance is None else audit.provenance.formation_context_ref,
        "config_hash": None if audit.provenance is None else audit.provenance.policy_ref,
        "environment_ref": audit.environment_ref,
        "dataset_version_refs": []
        if audit.provenance is None or audit.provenance.evidence_bundle_ref is None
        else [audit.provenance.evidence_bundle_ref],
        "missing_fields": missing_fields,
        "reproducibility_score": _reproducibility_score(audit.reproducibility_status),
        "is_fully_reproducible": audit.reproducibility_status == "complete",
        "completeness_notes": [note.summary for note in audit.completeness_notes],
    }


def environment_diff_payload(diff: Any) -> dict[str, Any]:
    changed_fields: list[str] = []
    if diff.python_version_changed:
        changed_fields.append("python_version")
    if diff.platform_changed:
        changed_fields.append("platform")
    if diff.added_packages or diff.removed_packages or diff.changed_packages:
        changed_fields.append("packages")
    if diff.added_variables or diff.removed_variables or diff.changed_variables:
        changed_fields.append("environment_variables")
    missing_fields: list[str] = []
    if diff.left_environment_ref is None:
        missing_fields.append("left_environment_ref")
    if diff.right_environment_ref is None:
        missing_fields.append("right_environment_ref")
    return {
        "left_run_id": diff.left_run_id,
        "right_run_id": diff.right_run_id,
        "changed_fields": changed_fields,
        "missing_fields": missing_fields,
        "has_differences": bool(changed_fields),
        "left_environment_ref": diff.left_environment_ref,
        "right_environment_ref": diff.right_environment_ref,
        "left_code_revision": None,
        "right_code_revision": None,
        "left_config_hash": None,
        "right_config_hash": None,
        "completeness_notes": [note.summary for note in diff.completeness_notes],
        "package_changes": {
            "added": to_jsonable(diff.added_packages),
            "removed": to_jsonable(diff.removed_packages),
            "changed": to_jsonable(diff.changed_packages),
        },
        "environment_variable_changes": {
            "added": to_jsonable(diff.added_variables),
            "removed": to_jsonable(diff.removed_variables),
            "changed": to_jsonable(diff.changed_variables),
        },
    }


def error_envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": to_jsonable(details),
        }
    }


def _reproducibility_score(status: str) -> float:
    if status == "complete":
        return 1.0
    if status == "partial":
        return 0.5
    return 0.0


__all__ = [
    "environment_diff_payload",
    "error_envelope",
    "reproducibility_payload",
    "run_summary_payload",
    "to_jsonable",
]
