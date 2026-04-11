"""Core contract validators for Contexta canonical models."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any, Sequence

from ...common.errors import ValidationError
from ..extensions import ExtensionFieldSet
from ..models import (
    DEFAULT_CONTRACT_SCHEMA_VERSION,
    ArtifactManifest,
    BatchExecution,
    DeploymentExecution,
    DegradedRecord,
    EnvironmentSnapshot,
    LineageEdge,
    MetricRecord,
    OperationContext,
    Project,
    ProvenanceRecord,
    RecordEnvelope,
    Run,
    SampleObservation,
    StageExecution,
    StructuredEventRecord,
    TraceSpanRecord,
)
from ..registry import EXTENSION_TARGET_MODELS, ExtensionRegistry
from .report import ValidationIssue, ValidationReport


def _error(path: str, code: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, path=path, message=message, severity="error")


def _warning(path: str, code: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, path=path, message=message, severity="warning")


def _revalidate_dataclass_model(obj: Any) -> ValidationReport:
    if not is_dataclass(obj):
        return ValidationReport.from_issues(
            (_error("$", "validation.invalid_model", "Validator target must be a dataclass model."),),
        )
    try:
        payload = {field.name: getattr(obj, field.name) for field in fields(obj)}
        type(obj)(**payload)
    except ValidationError as exc:
        path = "$"
        field_name = None if exc.details is None else exc.details.get("field_name")
        if isinstance(field_name, str) and field_name.strip():
            path = f"$.{field_name.strip()}"
        return ValidationReport.from_issues((_error(path, exc.code, exc.message),))
    except TypeError as exc:
        return ValidationReport.from_issues((_error("$", "validation.invalid_model", str(exc)),))
    return ValidationReport.ok()


def _validate_schema_version(schema_version: str) -> ValidationReport:
    if schema_version != DEFAULT_CONTRACT_SCHEMA_VERSION:
        return ValidationReport.from_issues(
            (
                _error(
                    "$.schema_version",
                    "schema.version_mismatch",
                    f"schema_version must equal {DEFAULT_CONTRACT_SCHEMA_VERSION!r}.",
                ),
            ),
        )
    return ValidationReport.ok()


def validate_extension_field_set(
    ext: Any,
    *,
    target_model: str,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    """Validate one extension field set against the registry."""

    issues: list[ValidationIssue] = []
    active_registry = ExtensionRegistry() if registry is None else registry

    if target_model not in EXTENSION_TARGET_MODELS:
        issues.append(
            _error(
                "$",
                "extension.invalid_target_model",
                f"Unknown extension target model: {target_model!r}.",
            ),
        )
        return ValidationReport.from_issues(issues)

    if not isinstance(active_registry, ExtensionRegistry):
        issues.append(_error("$", "extension.invalid_registry", "registry must be ExtensionRegistry."))
        return ValidationReport.from_issues(issues)

    if not isinstance(ext, ExtensionFieldSet):
        issues.append(_error("$", "extension.invalid_type", "ext must be ExtensionFieldSet."))
        return ValidationReport.from_issues(issues)

    issues.extend(_revalidate_dataclass_model(ext).issues)
    entry = active_registry.get_entry(ext.namespace)
    if entry is None:
        issues.append(
            _error(
                "$.namespace",
                "extension.namespace_unregistered",
                f"Extension namespace is not registered: {ext.namespace}",
            ),
        )
    elif not entry.allows_target_model(target_model):
        issues.append(
            _error(
                "$.namespace",
                "extension.target_model_mismatch",
                f"Extension namespace {ext.namespace!r} is not allowed on {target_model!r}.",
            ),
        )
    return ValidationReport.from_issues(issues)


def _validate_extensions(
    extensions: Sequence[ExtensionFieldSet],
    *,
    target_model: str,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    reports = [
        validate_extension_field_set(ext, target_model=target_model, registry=registry).prefixed(
            f"$.extensions[{index}]",
        )
        for index, ext in enumerate(extensions)
    ]
    return ValidationReport.merge(*reports)


def _validate_model_base(
    obj: Any,
    *,
    expected_type: type[Any],
    target_model: str,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    if not isinstance(obj, expected_type):
        return ValidationReport.from_issues(
            (
                _error(
                    "$",
                    "validation.invalid_type",
                    f"Expected {expected_type.__name__}, got {type(obj).__name__}.",
                ),
            ),
        )

    reports = [
        _revalidate_dataclass_model(obj),
        _validate_schema_version(obj.schema_version),
    ]
    if hasattr(obj, "extensions"):
        reports.append(_validate_extensions(obj.extensions, target_model=target_model, registry=registry))
    return ValidationReport.merge(*reports)


def validate_project(project: Any, *, registry: ExtensionRegistry | None = None) -> ValidationReport:
    return _validate_model_base(project, expected_type=Project, target_model="project", registry=registry)


def validate_run(run: Any, *, registry: ExtensionRegistry | None = None) -> ValidationReport:
    return _validate_model_base(run, expected_type=Run, target_model="run", registry=registry)


def validate_deployment_execution(
    deployment: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    return _validate_model_base(
        deployment,
        expected_type=DeploymentExecution,
        target_model="deployment_execution",
        registry=registry,
    )


def validate_stage_execution(
    stage: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    return _validate_model_base(
        stage,
        expected_type=StageExecution,
        target_model="stage_execution",
        registry=registry,
    )


def validate_batch_execution(
    batch: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    return _validate_model_base(
        batch,
        expected_type=BatchExecution,
        target_model="batch_execution",
        registry=registry,
    )


def validate_sample_observation(
    sample: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    return _validate_model_base(
        sample,
        expected_type=SampleObservation,
        target_model="sample_observation",
        registry=registry,
    )


def validate_operation_context(
    operation: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    return _validate_model_base(
        operation,
        expected_type=OperationContext,
        target_model="operation_context",
        registry=registry,
    )


def validate_environment_snapshot(
    snapshot: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    return _validate_model_base(
        snapshot,
        expected_type=EnvironmentSnapshot,
        target_model="environment_snapshot",
        registry=registry,
    )


def validate_record_envelope(
    envelope: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    return _validate_model_base(
        envelope,
        expected_type=RecordEnvelope,
        target_model="record_envelope",
        registry=registry,
    )


def validate_structured_event_record(
    record: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    if not isinstance(record, StructuredEventRecord):
        return ValidationReport.from_issues(
            (_error("$", "validation.invalid_type", f"Expected StructuredEventRecord, got {type(record).__name__}."),),
        )
    return ValidationReport.merge(
        _revalidate_dataclass_model(record),
        validate_record_envelope(record.envelope, registry=registry).prefixed("$.envelope"),
        _revalidate_dataclass_model(record.payload).prefixed("$.payload"),
    )


def validate_metric_record(
    record: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    if not isinstance(record, MetricRecord):
        return ValidationReport.from_issues(
            (_error("$", "validation.invalid_type", f"Expected MetricRecord, got {type(record).__name__}."),),
        )

    reports = [
        _revalidate_dataclass_model(record),
        validate_record_envelope(record.envelope, registry=registry).prefixed("$.envelope"),
        _revalidate_dataclass_model(record.payload).prefixed("$.payload"),
    ]
    if record.payload.unit is None:
        reports.append(
            ValidationReport.from_issues(
                (_warning("$.payload.unit", "metric.unit_missing", "Metric unit is missing."),),
            ),
        )
    return ValidationReport.merge(*reports)


def validate_trace_span_record(
    record: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    if not isinstance(record, TraceSpanRecord):
        return ValidationReport.from_issues(
            (_error("$", "validation.invalid_type", f"Expected TraceSpanRecord, got {type(record).__name__}."),),
        )
    return ValidationReport.merge(
        _revalidate_dataclass_model(record),
        validate_record_envelope(record.envelope, registry=registry).prefixed("$.envelope"),
        _revalidate_dataclass_model(record.payload).prefixed("$.payload"),
    )


def validate_degraded_record(
    record: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    if not isinstance(record, DegradedRecord):
        return ValidationReport.from_issues(
            (_error("$", "validation.invalid_type", f"Expected DegradedRecord, got {type(record).__name__}."),),
        )
    return ValidationReport.merge(
        _revalidate_dataclass_model(record),
        validate_record_envelope(record.envelope, registry=registry).prefixed("$.envelope"),
        _revalidate_dataclass_model(record.payload).prefixed("$.payload"),
    )


def validate_artifact_manifest(
    manifest: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    reports = [
        _validate_model_base(
            manifest,
            expected_type=ArtifactManifest,
            target_model="artifact_manifest",
            registry=registry,
        ),
    ]
    if isinstance(manifest, ArtifactManifest):
        if manifest.hash_value is None:
            reports.append(
                ValidationReport.from_issues(
                    (_warning("$.hash_value", "artifact.hash_value_missing", "Artifact hash_value is missing."),),
                ),
            )
        if manifest.size_bytes is None:
            reports.append(
                ValidationReport.from_issues(
                    (_warning("$.size_bytes", "artifact.size_bytes_missing", "Artifact size_bytes is missing."),),
                ),
            )
    return ValidationReport.merge(*reports)


def validate_lineage_edge(
    edge: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    reports = [
        _validate_model_base(edge, expected_type=LineageEdge, target_model="lineage_edge", registry=registry),
    ]
    if isinstance(edge, LineageEdge):
        if not edge.evidence_refs:
            reports.append(
                ValidationReport.from_issues(
                    (_warning("$.evidence_refs", "lineage.evidence_refs_missing", "Lineage edge has no evidence_refs."),),
                ),
            )
        if edge.confidence_marker == "low" and not edge.evidence_refs:
            reports.append(
                ValidationReport.from_issues(
                    (
                        _warning(
                            "$.confidence_marker",
                            "lineage.low_confidence_without_provenance",
                            "Low-confidence lineage should carry provenance or evidence.",
                        ),
                    ),
                ),
            )
    return ValidationReport.merge(*reports)


def validate_provenance_record(
    record: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport:
    reports = [
        _validate_model_base(
            record,
            expected_type=ProvenanceRecord,
            target_model="provenance_record",
            registry=registry,
        ),
    ]
    if isinstance(record, ProvenanceRecord):
        if record.policy_ref is None:
            reports.append(
                ValidationReport.from_issues(
                    (_warning("$.policy_ref", "provenance.policy_ref_missing", "Provenance policy_ref is missing."),),
                ),
            )
        if record.evidence_bundle_ref is None:
            reports.append(
                ValidationReport.from_issues(
                    (
                        _warning(
                            "$.evidence_bundle_ref",
                            "provenance.evidence_bundle_ref_missing",
                            "Provenance evidence_bundle_ref is missing.",
                        ),
                    ),
                ),
            )
    return ValidationReport.merge(*reports)


__all__ = [
    "validate_artifact_manifest",
    "validate_batch_execution",
    "validate_degraded_record",
    "validate_deployment_execution",
    "validate_environment_snapshot",
    "validate_extension_field_set",
    "validate_lineage_edge",
    "validate_metric_record",
    "validate_operation_context",
    "validate_project",
    "validate_provenance_record",
    "validate_record_envelope",
    "validate_run",
    "validate_sample_observation",
    "validate_stage_execution",
    "validate_structured_event_record",
    "validate_trace_span_record",
]
