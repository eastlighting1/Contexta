"""Run snapshot builder for the metadata truth plane."""

from __future__ import annotations

from dataclasses import dataclass

from ...contract import (
    BatchExecution,
    DeploymentExecution,
    EnvironmentSnapshot,
    LineageEdge,
    Project,
    ProvenanceRecord,
    Run,
    SampleObservation,
    StageExecution,
)


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    """Metadata-only projection of a run and its lineage-adjacent context."""

    project: Project
    run: Run
    deployments: tuple[DeploymentExecution, ...] = ()
    stages: tuple[StageExecution, ...] = ()
    batches: tuple[BatchExecution, ...] = ()
    samples: tuple[SampleObservation, ...] = ()
    environments: tuple[EnvironmentSnapshot, ...] = ()
    relations: tuple[LineageEdge, ...] = ()
    provenance: tuple[ProvenanceRecord, ...] = ()
    scoped_refs: tuple[str, ...] = ()
    completeness_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "deployments", tuple(self.deployments))
        object.__setattr__(self, "stages", tuple(self.stages))
        object.__setattr__(self, "batches", tuple(self.batches))
        object.__setattr__(self, "samples", tuple(self.samples))
        object.__setattr__(self, "environments", tuple(self.environments))
        object.__setattr__(self, "relations", tuple(self.relations))
        object.__setattr__(self, "provenance", tuple(self.provenance))
        object.__setattr__(self, "scoped_refs", tuple(self.scoped_refs))
        object.__setattr__(self, "completeness_notes", tuple(self.completeness_notes))

    def to_dict(self) -> dict[str, object]:
        return {
            "project": self.project.to_dict(),
            "run": self.run.to_dict(),
            "deployments": [deployment.to_dict() for deployment in self.deployments],
            "stages": [stage.to_dict() for stage in self.stages],
            "batches": [batch.to_dict() for batch in self.batches],
            "samples": [sample.to_dict() for sample in self.samples],
            "environments": [environment.to_dict() for environment in self.environments],
            "relations": [relation.to_dict() for relation in self.relations],
            "provenance": [item.to_dict() for item in self.provenance],
            "scoped_refs": list(self.scoped_refs),
            "completeness_notes": list(self.completeness_notes),
        }


def build_run_snapshot(store: object, run_ref: str) -> RunSnapshot:
    """Build a metadata-scoped snapshot for one run."""

    run = store.runs.get_run(run_ref)
    project = store.projects.get_project(str(run.project_ref))
    deployments = store.deployments.list_deployment_executions(run_ref=str(run.run_ref))
    stages = store.stages.list_stage_executions(str(run.run_ref))
    batches = store.batches.list_batch_executions(run_ref=str(run.run_ref))
    samples = store.samples.list_sample_observations(run_ref=str(run.run_ref))
    environments = store.environments.list_environment_snapshots(str(run.run_ref))

    scoped_anchor_refs = {str(run.run_ref)}
    scoped_anchor_refs.update(str(deployment.deployment_execution_ref) for deployment in deployments)
    scoped_anchor_refs.update(str(stage.stage_execution_ref) for stage in stages)
    scoped_anchor_refs.update(str(batch.batch_execution_ref) for batch in batches)
    scoped_anchor_refs.update(str(sample.sample_observation_ref) for sample in samples)
    scoped_anchor_refs.update(str(environment.environment_snapshot_ref) for environment in environments)

    relations_by_ref: dict[str, LineageEdge] = {}
    for anchor_ref in sorted(scoped_anchor_refs):
        for relation in store.relations.list_relations_for_ref(anchor_ref):
            relations_by_ref[str(relation.relation_ref)] = relation

    provenance_by_ref: dict[str, ProvenanceRecord] = {}
    for relation_ref in sorted(relations_by_ref):
        for provenance in store.provenance.list_provenance_for_relation(relation_ref):
            provenance_by_ref[str(provenance.provenance_ref)] = provenance

    notes: list[str] = []
    if not environments:
        notes.append("environment_snapshot_missing")
    if not relations_by_ref:
        notes.append("relation_graph_empty")
    if relations_by_ref and not provenance_by_ref:
        notes.append("provenance_missing")
    notes.extend(("record_plane_not_projected", "artifact_plane_not_projected"))

    scoped_refs = set(scoped_anchor_refs)
    scoped_refs.update(relations_by_ref)
    scoped_refs.update(str(provenance.provenance_ref) for provenance in provenance_by_ref.values())

    return RunSnapshot(
        project=project,
        run=run,
        deployments=deployments,
        stages=stages,
        batches=batches,
        samples=samples,
        environments=environments,
        relations=tuple(relations_by_ref[ref] for ref in sorted(relations_by_ref)),
        provenance=tuple(provenance_by_ref[ref] for ref in sorted(provenance_by_ref)),
        scoped_refs=tuple(sorted(scoped_refs)),
        completeness_notes=tuple(dict.fromkeys(notes)),
    )


__all__ = ["RunSnapshot", "build_run_snapshot"]
