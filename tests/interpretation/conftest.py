"""Shared mock repository fixture for interpretation tests."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from contexta.interpretation.repositories import (
    ArtifactRecord,
    BatchRecord,
    DeploymentRecord,
    ObservationRecord,
    ProvenanceView,
    RelationRecord,
    RunRecord,
    SampleRecord,
    StageRecord,
)


TS = "2024-01-01T00:00:00Z"
TS2 = "2024-01-02T00:00:00Z"
TS3 = "2024-01-03T00:00:00Z"


def _make_run(run_id, project_name="my-proj", status="completed", started=TS, ended=TS2):
    return RunRecord(
        run_id=run_id,
        project_name=project_name,
        name=run_id,
        status=status,
        started_at=started,
        ended_at=ended if status != "open" else None,
    )


def _make_stage(stage_id, run_id, name="train", status="completed"):
    return StageRecord(
        stage_id=stage_id,
        run_id=run_id,
        name=name,
        status=status,
        started_at=TS,
        ended_at=TS2,
    )


def _make_observation(record_id, run_id, record_type="metric", key="loss", value=0.5):
    return ObservationRecord(
        record_id=record_id,
        run_id=run_id,
        stage_id=None,
        record_type=record_type,
        key=key,
        observed_at=TS,
        value=value,
    )


def _make_batch(batch_id, run_id, stage_id, name="mini-batch-0", status="completed"):
    return BatchRecord(
        batch_id=batch_id,
        run_id=run_id,
        stage_id=stage_id,
        name=name,
        status=status,
        order=0,
        started_at=TS,
        ended_at=TS2,
    )


def _make_sample(
    sample_id,
    run_id,
    stage_id,
    batch_id=None,
    name="item-0001",
    retention_class="debug",
    redaction_profile="metadata-only",
):
    return SampleRecord(
        sample_id=sample_id,
        run_id=run_id,
        stage_id=stage_id,
        batch_id=batch_id,
        name=name,
        observed_at=TS,
        retention_class=retention_class,
        redaction_profile=redaction_profile,
    )


def _make_deployment(
    deployment_id,
    project_name="my-proj",
    run_id=None,
    artifact_ref=None,
    name="recommendation-api",
    status="completed",
):
    return DeploymentRecord(
        deployment_id=deployment_id,
        project_name=project_name,
        name=name,
        status=status,
        run_id=run_id,
        artifact_ref=artifact_ref,
        started_at=TS,
        ended_at=TS2,
        order=0,
    )


def _make_artifact(artifact_ref, run_id, kind="checkpoint"):
    return ArtifactRecord(
        artifact_ref=artifact_ref,
        run_id=run_id,
        stage_id=None,
        kind=kind,
        created_at=TS,
    )


class MockRepository:
    """Simple in-memory implementation of CompositeRepository for tests."""

    def __init__(self):
        self._runs: dict[str, RunRecord] = {}
        self._deployments: dict[str, list[DeploymentRecord]] = {}
        self._stages: dict[str, list[StageRecord]] = {}
        self._batches: dict[str, list[BatchRecord]] = {}
        self._samples: dict[str, list[SampleRecord]] = {}
        self._records: dict[str, list[ObservationRecord]] = {}
        self._artifacts: dict[str, list[ArtifactRecord]] = {}
        self._relations: list[RelationRecord] = []

    def add_run(self, run: RunRecord) -> None:
        self._runs[run.run_id] = run

    def add_stage(self, stage: StageRecord) -> None:
        self._stages.setdefault(stage.run_id, []).append(stage)

    def add_deployment(self, deployment: DeploymentRecord) -> None:
        self._deployments.setdefault(deployment.project_name, []).append(deployment)

    def add_batch(self, batch: BatchRecord) -> None:
        self._batches.setdefault(batch.run_id, []).append(batch)

    def add_sample(self, sample: SampleRecord) -> None:
        self._samples.setdefault(sample.run_id, []).append(sample)

    def add_record(self, record: ObservationRecord) -> None:
        self._records.setdefault(record.run_id, []).append(record)

    def add_artifact(self, artifact: ArtifactRecord) -> None:
        self._artifacts.setdefault(artifact.run_id, []).append(artifact)

    # Protocol implementation
    def list_projects(self):
        return list({r.project_name for r in self._runs.values()})

    def list_runs(self, project_name=None):
        if project_name is None:
            return list(self._runs.values())
        return [r for r in self._runs.values() if r.project_name == project_name]

    def get_run(self, run_id):
        return self._runs.get(run_id)

    def list_deployments(self, project_name=None, run_id=None):
        deployments = []
        if project_name is None:
            for items in self._deployments.values():
                deployments.extend(items)
        else:
            deployments = list(self._deployments.get(project_name, []))
        if run_id:
            deployments = [d for d in deployments if d.run_id == run_id]
        return deployments

    def list_stages(self, run_id):
        return self._stages.get(run_id, [])

    def list_batches(self, run_id, stage_id=None):
        batches = self._batches.get(run_id, [])
        if stage_id:
            batches = [b for b in batches if b.stage_id == stage_id]
        return batches

    def list_samples(self, run_id, stage_id=None, batch_id=None):
        samples = self._samples.get(run_id, [])
        if stage_id:
            samples = [s for s in samples if s.stage_id == stage_id]
        if batch_id:
            samples = [s for s in samples if s.batch_id == batch_id]
        return samples

    def list_records(self, *, run_id, stage_id=None, record_type=None):
        records = self._records.get(run_id, [])
        if stage_id:
            records = [r for r in records if r.stage_id == stage_id]
        if record_type:
            records = [r for r in records if r.record_type == record_type]
        return records

    def list_relations(self, subject_ref=None):
        if subject_ref is None:
            return self._relations
        return [r for r in self._relations if r.source_ref == subject_ref or r.target_ref == subject_ref]

    def get_provenance(self, run_id):
        return None

    def get_artifact(self, artifact_ref):
        for arts in self._artifacts.values():
            for a in arts:
                if a.artifact_ref == artifact_ref:
                    return a
        return None

    def list_artifacts(self, *, run_id=None, stage_id=None):
        if run_id is None:
            result = []
            for arts in self._artifacts.values():
                result.extend(arts)
            return result
        arts = self._artifacts.get(run_id, [])
        if stage_id:
            arts = [a for a in arts if a.stage_id == stage_id]
        return arts


@pytest.fixture()
def mock_repo():
    repo = MockRepository()
    # Two runs in the same project
    repo.add_run(_make_run("my-proj.run-01"))
    repo.add_run(_make_run("my-proj.run-02"))
    repo.add_deployment(
        _make_deployment(
            "deployment:my-proj.recommendation-api",
            run_id="my-proj.run-01",
            artifact_ref="artifact:my-proj.run-01.model",
        )
    )
    repo.add_stage(_make_stage("my-proj.run-01.train", "my-proj.run-01"))
    repo.add_stage(_make_stage("my-proj.run-02.train", "my-proj.run-02"))
    repo.add_batch(_make_batch("batch:my-proj.run-01.train.mini-batch-0", "my-proj.run-01", "my-proj.run-01.train"))
    repo.add_batch(_make_batch("batch:my-proj.run-02.train.mini-batch-0", "my-proj.run-02", "my-proj.run-02.train"))
    repo.add_sample(
        _make_sample(
            "sample:my-proj.run-01.train.mini-batch-0.item-0001",
            "my-proj.run-01",
            "my-proj.run-01.train",
            batch_id="batch:my-proj.run-01.train.mini-batch-0",
        )
    )
    repo.add_sample(
        _make_sample(
            "sample:my-proj.run-02.train.mini-batch-0.item-0001",
            "my-proj.run-02",
            "my-proj.run-02.train",
            batch_id="batch:my-proj.run-02.train.mini-batch-0",
        )
    )
    repo.add_record(_make_observation("r01-m1", "my-proj.run-01", key="loss", value=0.5))
    repo.add_record(_make_observation("r01-m2", "my-proj.run-01", key="accuracy", value=0.8))
    repo.add_record(_make_observation("r02-m1", "my-proj.run-02", key="loss", value=0.3))
    repo.add_record(_make_observation("r02-m2", "my-proj.run-02", key="accuracy", value=0.9))
    repo.add_artifact(_make_artifact("artifact:my-proj.run-01.model", "my-proj.run-01"))
    repo.add_artifact(_make_artifact("artifact:my-proj.run-02.model", "my-proj.run-02"))
    return repo
