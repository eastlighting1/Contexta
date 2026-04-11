"""Core interpretation query service."""

from __future__ import annotations

from collections import defaultdict

from ...common.errors import InterpretationError
from ..protocols import CompositeRepository
from ..repositories import ArtifactRecord, BatchRecord, DeploymentRecord, ObservationRecord, RunRecord, SampleRecord
from .filters import MetricCondition, RunListQuery
from .models import EvidenceLink, RunSnapshot


class QueryService:
    """Interpretation-owned read orchestrator over a composite repository."""

    def __init__(self, repository: CompositeRepository) -> None:
        self.repository = repository

    def list_projects(self) -> tuple[str, ...]:
        return tuple(self.repository.list_projects())

    def list_runs(
        self,
        project_name: str | None = None,
        *,
        query: RunListQuery | None = None,
    ) -> tuple[RunRecord, ...]:
        active_project = project_name
        if query is not None and query.project_name is not None:
            active_project = query.project_name
        runs = list(self.repository.list_runs(active_project))
        if query is None:
            return tuple(runs)
        runs = self._apply_metadata_filters(runs, query)
        runs = self._apply_sort(runs, query)
        if query.metric_conditions:
            runs = [run for run in runs if self._matches_metric_conditions(run, query.metric_conditions)]
        start = query.offset
        end = None if query.limit is None else start + query.limit
        return tuple(runs[start:end])

    def get_run_snapshot(self, run_id: str) -> RunSnapshot:
        run = self.repository.get_run(run_id)
        if run is None:
            raise InterpretationError(
                "Run anchor was not found.",
                code="query_run_not_found",
                details={"run_id": run_id},
            )
        deployments = tuple(self.repository.list_deployments(run_id=run.run_id))
        stages = tuple(self.repository.list_stages(run.run_id))
        batches = tuple(self.repository.list_batches(run.run_id))
        samples = tuple(self.repository.list_samples(run.run_id))
        artifacts = tuple(self.repository.list_artifacts(run_id=run.run_id))
        relations_map: dict[str, object] = {}
        for relation in self.repository.list_relations(run.run_id):
            relations_map[relation.relation_ref] = relation
        for stage in stages:
            for relation in self.repository.list_relations(stage.stage_id):
                relations_map[relation.relation_ref] = relation
        for batch in batches:
            for relation in self.repository.list_relations(batch.batch_id):
                relations_map[relation.relation_ref] = relation
        for artifact in artifacts:
            for relation in self.repository.list_relations(artifact.artifact_ref):
                relations_map[relation.relation_ref] = relation
        records = tuple(self.repository.list_records(run_id=run.run_id))
        provenance = self.repository.get_provenance(run.run_id)
        evidence_links = self._build_evidence_links(
            run=run,
            deployments=deployments,
            stages=stages,
            batches=batches,
            samples=samples,
            artifacts=artifacts,
            records=records,
        )
        completeness_notes = self._build_completeness_notes(
            deployments=deployments,
            stages=stages,
            batches=batches,
            samples=samples,
            artifacts=artifacts,
            relations=tuple(relations_map.values()),
            records=records,
            provenance=provenance,
        )
        return RunSnapshot(
            run=run,
            deployments=deployments,
            stages=stages,
            batches=batches,
            samples=samples,
            artifacts=artifacts,
            relations=tuple(relations_map[key] for key in sorted(relations_map)),
            records=records,
            evidence_links=evidence_links,
            completeness_notes=completeness_notes,
            provenance=provenance,
        )

    def list_deployments(
        self,
        project_name: str | None = None,
        run_id: str | None = None,
    ) -> tuple[DeploymentRecord, ...]:
        return tuple(self.repository.list_deployments(project_name, run_id))

    def list_batches(
        self,
        run_id: str,
        stage_id: str | None = None,
    ) -> tuple[BatchRecord, ...]:
        return tuple(self.repository.list_batches(run_id, stage_id))

    def list_samples(
        self,
        run_id: str,
        stage_id: str | None = None,
        batch_id: str | None = None,
    ) -> tuple[SampleRecord, ...]:
        return tuple(self.repository.list_samples(run_id, stage_id, batch_id))

    def get_artifact_origin(self, artifact_ref: str) -> RunSnapshot | None:
        artifact = self.repository.get_artifact(artifact_ref)
        if artifact is None:
            return None
        try:
            return self.get_run_snapshot(artifact.run_id)
        except InterpretationError as exc:
            raise InterpretationError(
                "Artifact exists but the owning run snapshot could not be assembled.",
                code="query_artifact_origin_incomplete",
                details={"artifact_ref": artifact.artifact_ref, "run_id": artifact.run_id},
                cause=exc,
            ) from exc

    def _apply_metadata_filters(self, runs: list[RunRecord], query: RunListQuery) -> list[RunRecord]:
        filtered = runs
        explicit_run_ids = None
        if query.tags and "__run_ids__" in query.tags:
            explicit_run_ids = {item for item in query.tags["__run_ids__"].split(",") if item}
        if query.status is not None:
            filtered = [run for run in filtered if run.status == query.status]
        if query.tags:
            filtered = [
                run
                for run in filtered
                if all(
                    key == "__run_ids__" or run.tags.get(key) == value
                    for key, value in query.tags.items()
                )
            ]
        if explicit_run_ids is not None:
            filtered = [run for run in filtered if run.run_id in explicit_run_ids]
        if query.time_range is not None:
            if query.time_range.started_after is not None:
                filtered = [
                    run
                    for run in filtered
                    if run.started_at is not None and run.started_at >= query.time_range.started_after
                ]
            if query.time_range.started_before is not None:
                filtered = [
                    run
                    for run in filtered
                    if run.started_at is not None and run.started_at <= query.time_range.started_before
                ]
        return filtered

    def _apply_sort(self, runs: list[RunRecord], query: RunListQuery) -> list[RunRecord]:
        return sorted(
            runs,
            key=lambda run: getattr(run, query.sort_by) or "",
            reverse=query.sort_desc,
        )

    def _matches_metric_conditions(
        self,
        run: RunRecord,
        conditions: tuple[MetricCondition, ...],
    ) -> bool:
        records = tuple(self.repository.list_records(run_id=run.run_id, record_type="metric"))
        latest_by_key: dict[tuple[str | None, str], ObservationRecord] = {}
        for record in records:
            stage_name = None if record.stage_id is None else record.stage_id.split(".")[-1]
            key = (stage_name, record.key)
            current = latest_by_key.get(key)
            if current is None or record.observed_at >= current.observed_at:
                latest_by_key[key] = record
        for condition in conditions:
            key = (condition.stage_name, condition.metric_key)
            record = latest_by_key.get(key)
            if record is None and condition.stage_name is None:
                candidates = [item for item_key, item in latest_by_key.items() if item_key[1] == condition.metric_key]
                if candidates:
                    record = max(candidates, key=lambda item: item.observed_at)
            if record is None or record.value is None:
                return False
            if not _compare_metric_value(float(record.value), condition.operator, float(condition.threshold)):
                return False
        return True

    def _build_evidence_links(
        self,
        *,
        run: RunRecord,
        deployments: tuple[object, ...],
        stages: tuple[object, ...],
        batches: tuple[object, ...],
        samples: tuple[object, ...],
        artifacts: tuple[ArtifactRecord, ...],
        records: tuple[ObservationRecord, ...],
    ) -> tuple[EvidenceLink, ...]:
        links: list[EvidenceLink] = [EvidenceLink(kind="run", ref=run.run_id, label=run.name)]
        links.extend(
            EvidenceLink(kind="deployment", ref=deployment.deployment_id, label=deployment.name)
            for deployment in deployments
        )
        links.extend(EvidenceLink(kind="stage", ref=stage.stage_id, label=stage.name) for stage in stages)
        links.extend(EvidenceLink(kind="batch", ref=batch.batch_id, label=batch.name) for batch in batches)
        links.extend(EvidenceLink(kind="sample", ref=sample.sample_id, label=sample.name) for sample in samples[:10])
        links.extend(EvidenceLink(kind="artifact", ref=artifact.artifact_ref, label=artifact.kind) for artifact in artifacts)
        links.extend(EvidenceLink(kind="record", ref=record.record_id, label=record.key) for record in records[:10])
        return tuple(links)

    def _build_completeness_notes(
        self,
        *,
        deployments: tuple[object, ...],
        stages: tuple[object, ...],
        batches: tuple[object, ...],
        samples: tuple[object, ...],
        artifacts: tuple[ArtifactRecord, ...],
        relations: tuple[object, ...],
        records: tuple[ObservationRecord, ...],
        provenance: object | None,
    ) -> tuple[str, ...]:
        notes: list[str] = []
        if not stages:
            notes.append("stage_list_empty")
        if not deployments:
            notes.append("deployment_list_empty")
        if stages and not batches:
            notes.append("batch_list_empty")
        if batches and not samples:
            notes.append("sample_list_empty")
        if not artifacts:
            notes.append("artifact_list_empty")
        if not relations:
            notes.append("relation_scope_empty")
        if not records:
            notes.append("record_scope_empty")
        if provenance is None:
            notes.append("provenance_missing")
        by_stage = defaultdict(list)
        for record in records:
            by_stage[record.stage_id].append(record)
        for stage in stages:
            if not by_stage.get(stage.stage_id):
                notes.append(f"missing_stage_records:{stage.name}")
        return tuple(dict.fromkeys(notes))


def _compare_metric_value(value: float, operator: str, threshold: float) -> bool:
    if operator == "gt":
        return value > threshold
    if operator == "lt":
        return value < threshold
    if operator == "gte":
        return value >= threshold
    if operator == "lte":
        return value <= threshold
    if operator == "eq":
        return value == threshold
    if operator == "ne":
        return value != threshold
    raise InterpretationError(
        "Unsupported metric operator.",
        code="query_invalid_metric_operator",
        details={"operator": operator},
    )


__all__ = ["QueryService"]
