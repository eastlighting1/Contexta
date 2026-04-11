"""Composite read-only repository over metadata, records, and artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ...contract import DegradedRecord, MetricRecord, StructuredEventRecord, TraceSpanRecord
from ...store.artifacts import ArtifactStore
from ...store.metadata import MetadataStore
from ...store.records import RecordStore, ScanFilter
from ..protocols import CompositeRepository


def _freeze_mapping(value: dict[str, Any] | None) -> MappingProxyType:
    if not value:
        return MappingProxyType({})
    return MappingProxyType(dict(sorted(value.items())))


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    project_name: str
    name: str
    status: str
    started_at: str | None = None
    ended_at: str | None = None
    tags: MappingProxyType = MappingProxyType({})
    metadata: MappingProxyType = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class StageRecord:
    stage_id: str
    run_id: str
    name: str
    status: str
    order: int = 0
    started_at: str | None = None
    ended_at: str | None = None
    tags: MappingProxyType = MappingProxyType({})
    metadata: MappingProxyType = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class DeploymentRecord:
    deployment_id: str
    project_name: str
    name: str
    status: str
    run_id: str | None = None
    artifact_ref: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    order: int = 0
    metadata: MappingProxyType = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class BatchRecord:
    batch_id: str
    run_id: str
    stage_id: str
    name: str
    status: str
    order: int = 0
    started_at: str | None = None
    ended_at: str | None = None
    metadata: MappingProxyType = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class SampleRecord:
    sample_id: str
    run_id: str
    stage_id: str
    batch_id: str | None
    name: str
    observed_at: str
    retention_class: str | None = None
    redaction_profile: str | None = None
    metadata: MappingProxyType = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_ref: str
    run_id: str
    stage_id: str | None
    kind: str
    created_at: str | None = None
    location: str | None = None
    hash_value: str | None = None
    size_bytes: int | None = None
    attributes: MappingProxyType = MappingProxyType({})
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class ObservationRecord:
    record_id: str
    run_id: str
    stage_id: str | None
    record_type: str
    key: str
    observed_at: str
    value: Any = None
    message: str | None = None
    completeness_marker: str = "complete"
    degradation_marker: str = "none"
    payload: MappingProxyType = MappingProxyType({})
    tags: MappingProxyType = MappingProxyType({})
    schema_version: str = "1"
    producer_ref: str | None = None
    correlation_id: str | None = None
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class RelationRecord:
    relation_ref: str
    relation_type: str
    source_ref: str
    target_ref: str
    recorded_at: str
    origin_marker: str
    confidence_marker: str


@dataclass(frozen=True, slots=True)
class ProvenanceView:
    run_id: str
    provenance_ref: str
    relation_ref: str
    assertion_mode: str
    asserted_at: str
    formation_context_ref: str | None = None
    policy_ref: str | None = None
    evidence_bundle_ref: str | None = None


class CompositeStoreRepository(CompositeRepository):
    """Read-only composition over the three truth-owning planes."""

    def __init__(
        self,
        metadata_store: MetadataStore,
        record_store: RecordStore,
        artifact_store: ArtifactStore,
    ) -> None:
        self.metadata_store = metadata_store
        self.record_store = record_store
        self.artifact_store = artifact_store

    def list_projects(self) -> tuple[str, ...]:
        return tuple(project.name for project in self.metadata_store.projects.list_projects())

    def list_runs(self, project_name: str | None = None) -> tuple[RunRecord, ...]:
        project_ref = None
        if project_name is not None:
            project_ref = self._resolve_project_ref(project_name)
            if project_ref is None:
                return ()
        runs = self.metadata_store.runs.list_runs(project_ref=project_ref)
        return tuple(self._project_run(run) for run in runs)

    def get_run(self, run_id: str) -> RunRecord | None:
        run_ref = self._resolve_run_ref(run_id)
        if run_ref is None:
            return None
        run = self.metadata_store.runs.find_run(run_ref)
        if run is None:
            return None
        return self._project_run(run)

    def list_deployments(
        self,
        project_name: str | None = None,
        run_id: str | None = None,
    ) -> tuple[DeploymentRecord, ...]:
        project_ref = None
        if project_name is not None:
            project_ref = self._resolve_project_ref(project_name)
            if project_ref is None:
                return ()
        run_ref = None if run_id is None else self._require_run_ref(run_id)
        deployments = self.metadata_store.deployments.list_deployment_executions(
            project_ref=project_ref,
            run_ref=run_ref,
        )
        return tuple(self._project_deployment(deployment) for deployment in deployments)

    def list_stages(self, run_id: str) -> tuple[StageRecord, ...]:
        run_ref = self._require_run_ref(run_id)
        stages = self.metadata_store.stages.list_stage_executions(run_ref)
        return tuple(self._project_stage(stage) for stage in stages)

    def list_batches(self, run_id: str, stage_id: str | None = None) -> tuple[BatchRecord, ...]:
        run_ref = self._require_run_ref(run_id)
        stage_ref = None if stage_id is None else self._require_stage_ref(stage_id, run_ref=run_ref)
        batches = self.metadata_store.batches.list_batch_executions(run_ref=run_ref, stage_ref=stage_ref)
        return tuple(self._project_batch(batch) for batch in batches)

    def list_samples(
        self,
        run_id: str,
        stage_id: str | None = None,
        batch_id: str | None = None,
    ) -> tuple[SampleRecord, ...]:
        run_ref = self._require_run_ref(run_id)
        stage_ref = None if stage_id is None else self._require_stage_ref(stage_id, run_ref=run_ref)
        batch_ref = None
        if batch_id is not None:
            batch_ref = batch_id.strip()
            if not batch_ref.startswith("batch:"):
                batch_ref = next(
                    (
                        item.batch_id
                        for item in self.list_batches(run_id, stage_id=stage_id)
                        if item.batch_id == batch_id or item.name == batch_id or item.batch_id.endswith(f".{batch_id}")
                    ),
                    None,
                )
                if batch_ref is None:
                    raise LookupError(f"Batch not found: {batch_id}")
        samples = self.metadata_store.samples.list_sample_observations(
            run_ref=run_ref,
            stage_ref=stage_ref,
            batch_ref=batch_ref,
        )
        return tuple(self._project_sample(sample) for sample in samples)

    def list_records(
        self,
        *,
        run_id: str,
        stage_id: str | None = None,
        record_type: str | None = None,
    ) -> tuple[ObservationRecord, ...]:
        run_ref = self._require_run_ref(run_id)
        stage_ref = None if stage_id is None else self._require_stage_ref(stage_id, run_ref=run_ref)
        scan_filter = ScanFilter(run_ref=run_ref, stage_execution_ref=stage_ref, record_type=record_type)
        return tuple(self._project_record(stored) for stored in self.record_store.scan(scan_filter))

    def get_artifact(self, artifact_ref: str) -> ArtifactRecord | None:
        ref = self._resolve_artifact_ref(artifact_ref)
        if ref is None:
            return None
        try:
            handle = self.artifact_store.get_artifact(ref)
        except Exception:
            return None
        return self._project_artifact(handle.binding)

    def list_artifacts(
        self,
        *,
        run_id: str | None = None,
        stage_id: str | None = None,
    ) -> tuple[ArtifactRecord, ...]:
        run_ref = None if run_id is None else self._require_run_ref(run_id)
        stage_ref = None if stage_id is None else self._require_stage_ref(stage_id, run_ref=run_ref)
        results: list[ArtifactRecord] = []
        for artifact_ref in self.artifact_store.list_refs():
            handle = self.artifact_store.get_artifact(artifact_ref)
            manifest = handle.binding.manifest_snapshot
            if run_ref is not None and str(manifest.run_ref) != run_ref:
                continue
            if stage_ref is not None and str(manifest.stage_execution_ref) != stage_ref:
                continue
            results.append(self._project_artifact(handle.binding))
        return tuple(results)

    def list_relations(self, subject_ref: str | None = None) -> tuple[RelationRecord, ...]:
        if subject_ref is not None:
            relations = self._collect_relations_for_subject(subject_ref)
            return tuple(self._project_relation(relation) for relation in relations)
        relations: dict[str, RelationRecord] = {}
        for run in self.metadata_store.runs.list_runs():
            for relation in self._collect_relations_for_subject(str(run.run_ref)):
                record = self._project_relation(relation)
                relations[record.relation_ref] = record
        return tuple(relations[key] for key in sorted(relations))

    def get_provenance(self, run_id: str) -> ProvenanceView | None:
        run_ref = self._require_run_ref(run_id)
        provenance_records: dict[str, Any] = {}
        for relation in self._collect_relations_for_subject(run_ref):
            for provenance in self.metadata_store.provenance.list_provenance_for_relation(str(relation.relation_ref)):
                provenance_records[str(provenance.provenance_ref)] = provenance
        if not provenance_records:
            return None
        ordered = sorted(provenance_records.values(), key=lambda item: item.asserted_at)
        selected = ordered[-1]
        return ProvenanceView(
            run_id=run_ref,
            provenance_ref=str(selected.provenance_ref),
            relation_ref=str(selected.relation_ref),
            assertion_mode=selected.assertion_mode,
            asserted_at=selected.asserted_at,
            formation_context_ref=None if selected.formation_context_ref is None else str(selected.formation_context_ref),
            policy_ref=None if selected.policy_ref is None else str(selected.policy_ref),
            evidence_bundle_ref=None if selected.evidence_bundle_ref is None else str(selected.evidence_bundle_ref),
        )

    def _collect_relations_for_subject(self, subject_ref: str) -> tuple[Any, ...]:
        refs: set[str] = {subject_ref}
        if subject_ref.startswith("run:"):
            for stage in self.metadata_store.stages.list_stage_executions(subject_ref):
                refs.add(str(stage.stage_execution_ref))
            for artifact in self.list_artifacts(run_id=subject_ref):
                refs.add(artifact.artifact_ref)
            for deployment in self.metadata_store.deployments.list_deployment_executions(run_ref=subject_ref):
                refs.add(str(deployment.deployment_execution_ref))
        elif subject_ref.startswith("stage:"):
            refs.add(subject_ref)
            for artifact in self.list_artifacts(stage_id=subject_ref):
                refs.add(artifact.artifact_ref)
        relations: dict[str, Any] = {}
        for ref in sorted(refs):
            for relation in self.metadata_store.relations.list_relations_for_ref(ref):
                relations[str(relation.relation_ref)] = relation
        return tuple(relations[key] for key in sorted(relations))

    def _project_run(self, run: Any) -> RunRecord:
        project = self.metadata_store.projects.get_project(str(run.project_ref))
        return RunRecord(
            run_id=str(run.run_ref),
            project_name=project.name,
            name=run.name,
            status=run.status,
            started_at=run.started_at,
            ended_at=run.ended_at,
            tags=_freeze_mapping(dict(getattr(run, "tags", {}) or {})),
            metadata=MappingProxyType({}),
        )

    def _project_stage(self, stage: Any) -> StageRecord:
        return StageRecord(
            stage_id=str(stage.stage_execution_ref),
            run_id=str(stage.run_ref),
            name=stage.stage_name,
            status=stage.status,
            order=0 if stage.order_index is None else stage.order_index,
            started_at=stage.started_at,
            ended_at=stage.ended_at,
            tags=MappingProxyType({}),
            metadata=MappingProxyType({}),
        )

    def _project_deployment(self, deployment: Any) -> DeploymentRecord:
        project = self.metadata_store.projects.get_project(str(deployment.project_ref))
        return DeploymentRecord(
            deployment_id=str(deployment.deployment_execution_ref),
            project_name=project.name,
            name=deployment.deployment_name,
            status=deployment.status,
            run_id=None if deployment.run_ref is None else str(deployment.run_ref),
            artifact_ref=None if deployment.artifact_ref is None else str(deployment.artifact_ref),
            started_at=deployment.started_at,
            ended_at=deployment.ended_at,
            order=0 if deployment.order_index is None else deployment.order_index,
            metadata=MappingProxyType({}),
        )

    def _project_batch(self, batch: Any) -> BatchRecord:
        return BatchRecord(
            batch_id=str(batch.batch_execution_ref),
            run_id=str(batch.run_ref),
            stage_id=str(batch.stage_execution_ref),
            name=batch.batch_name,
            status=batch.status,
            order=0 if batch.order_index is None else batch.order_index,
            started_at=batch.started_at,
            ended_at=batch.ended_at,
            metadata=MappingProxyType({}),
        )

    def _project_sample(self, sample: Any) -> SampleRecord:
        return SampleRecord(
            sample_id=str(sample.sample_observation_ref),
            run_id=str(sample.run_ref),
            stage_id=str(sample.stage_execution_ref),
            batch_id=None if sample.batch_execution_ref is None else str(sample.batch_execution_ref),
            name=sample.sample_name,
            observed_at=sample.observed_at,
            retention_class=sample.retention_class,
            redaction_profile=sample.redaction_profile,
            metadata=MappingProxyType({}),
        )

    def _project_artifact(self, binding: Any) -> ArtifactRecord:
        manifest = binding.manifest_snapshot
        return ArtifactRecord(
            artifact_ref=binding.artifact_ref,
            run_id=str(manifest.run_ref),
            stage_id=None if manifest.stage_execution_ref is None else str(manifest.stage_execution_ref),
            kind=binding.artifact_kind,
            created_at=binding.created_at,
            location=manifest.location_ref,
            hash_value=binding.hash_value,
            size_bytes=binding.size_bytes,
            attributes=_freeze_mapping(dict(getattr(manifest, "attributes", {}) or {})),
            content_type=None,
        )

    def _project_record(self, stored: Any) -> ObservationRecord:
        envelope = stored.record.envelope
        payload = stored.record.payload
        if isinstance(stored.record, StructuredEventRecord):
            key = payload.event_key
            value = None
            message = payload.message
            unit = None
        elif isinstance(stored.record, MetricRecord):
            key = payload.metric_key
            value = payload.value
            message = None
            unit = payload.unit
        elif isinstance(stored.record, TraceSpanRecord):
            key = payload.span_name
            value = payload.duration_ms
            message = None
            unit = "ms"
        elif isinstance(stored.record, DegradedRecord):
            key = payload.issue_key
            value = None
            message = payload.summary
            unit = None
        else:
            key = stored.record.record_type
            value = None
            message = None
            unit = None
        correlation_refs = getattr(envelope, "correlation_refs", None)
        correlation = None
        if correlation_refs is not None:
            correlation = correlation_refs.trace_id or correlation_refs.session_id
        return ObservationRecord(
            record_id=str(envelope.record_ref),
            run_id=str(envelope.run_ref),
            stage_id=None if envelope.stage_execution_ref is None else str(envelope.stage_execution_ref),
            record_type=envelope.record_type,
            key=key,
            observed_at=envelope.observed_at,
            value=value,
            message=message,
            completeness_marker=envelope.completeness_marker,
            degradation_marker=envelope.degradation_marker,
            payload=_freeze_mapping(payload.to_dict()),
            tags=_freeze_mapping(dict(getattr(envelope, "tags", {}) or {})),
            schema_version=envelope.schema_version,
            producer_ref=envelope.producer_ref,
            correlation_id=correlation,
            unit=unit,
        )

    def _project_relation(self, relation: Any) -> RelationRecord:
        return RelationRecord(
            relation_ref=str(relation.relation_ref),
            relation_type=relation.relation_type,
            source_ref=str(relation.source_ref),
            target_ref=str(relation.target_ref),
            recorded_at=relation.recorded_at,
            origin_marker=relation.origin_marker,
            confidence_marker=relation.confidence_marker,
        )

    def _resolve_project_ref(self, project_name: str) -> str | None:
        project_name = project_name.strip()
        for project in self.metadata_store.projects.list_projects():
            if project.name == project_name or str(project.project_ref) == project_name:
                return str(project.project_ref)
        return None

    def _resolve_run_ref(self, run_id: str) -> str | None:
        run_id = run_id.strip()
        if run_id.startswith("run:"):
            return run_id
        matches = [str(run.run_ref) for run in self.metadata_store.runs.list_runs() if str(run.run_ref) == run_id or str(run.run_ref).endswith(f".{run_id}")]
        if len(matches) == 1:
            return matches[0]
        return None

    def _require_run_ref(self, run_id: str) -> str:
        run_ref = self._resolve_run_ref(run_id)
        if run_ref is None:
            raise LookupError(f"Run not found: {run_id}")
        return run_ref

    def _resolve_stage_ref(self, stage_id: str, *, run_ref: str | None = None) -> str | None:
        stage_id = stage_id.strip()
        if stage_id.startswith("stage:"):
            return stage_id
        if run_ref is not None:
            matches = [
                str(stage.stage_execution_ref)
                for stage in self.metadata_store.stages.list_stage_executions(run_ref)
                if str(stage.stage_execution_ref) == stage_id or stage.stage_name == stage_id or str(stage.stage_execution_ref).endswith(f".{stage_id}")
            ]
            if len(matches) == 1:
                return matches[0]
        matches = []
        for run in self.metadata_store.runs.list_runs():
            for stage in self.metadata_store.stages.list_stage_executions(str(run.run_ref)):
                if str(stage.stage_execution_ref) == stage_id or stage.stage_name == stage_id or str(stage.stage_execution_ref).endswith(f".{stage_id}"):
                    matches.append(str(stage.stage_execution_ref))
        if len(matches) == 1:
            return matches[0]
        return None

    def _require_stage_ref(self, stage_id: str, *, run_ref: str | None = None) -> str:
        stage_ref = self._resolve_stage_ref(stage_id, run_ref=run_ref)
        if stage_ref is None:
            raise LookupError(f"Stage not found: {stage_id}")
        return stage_ref

    def _resolve_artifact_ref(self, artifact_ref: str) -> str | None:
        artifact_ref = artifact_ref.strip()
        if artifact_ref.startswith("artifact:"):
            return artifact_ref
        matches = [ref for ref in self.artifact_store.list_refs() if ref == artifact_ref or ref.endswith(f".{artifact_ref}")]
        if len(matches) == 1:
            return matches[0]
        return None


__all__ = [
    "ArtifactRecord",
    "BatchRecord",
    "CompositeStoreRepository",
    "DeploymentRecord",
    "ObservationRecord",
    "ProvenanceView",
    "RelationRecord",
    "RunRecord",
    "SampleRecord",
    "StageRecord",
]
