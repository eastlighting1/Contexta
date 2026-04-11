"""TST-010: project/run/stage/env/relation/provenance repository tests."""

from __future__ import annotations

import pytest

from contexta.common.errors import NotFoundError
from contexta.common.time import iso_utc_now
from contexta.contract.models.context import (
    BatchExecution,
    DeploymentExecution,
    EnvironmentSnapshot,
    Project,
    Run,
    SampleObservation,
    StageExecution,
)
from contexta.contract.models.lineage import LineageEdge, ProvenanceRecord
from contexta.store.metadata import MetadataStore, MetadataStoreConfig


TS = "2024-01-01T00:00:00Z"
TS2 = "2024-01-01T01:00:00Z"


@pytest.fixture()
def store():
    s = MetadataStore(MetadataStoreConfig(database_path=":memory:"))
    yield s
    s._backend.close()


def _make_project(ref="project:my-proj", name="My Project"):
    return Project(project_ref=ref, name=name, created_at=TS)


def _make_run(project_ref="project:my-proj", run_ref="run:my-proj.run-01"):
    return Run(
        run_ref=run_ref,
        project_ref=project_ref,
        name="Run 1",
        status="open",
        started_at=TS,
    )


def _make_stage(run_ref="run:my-proj.run-01", stage_ref="stage:my-proj.run-01.train"):
    return StageExecution(
        stage_execution_ref=stage_ref,
        run_ref=run_ref,
        stage_name="train",
        status="open",
        started_at=TS,
    )


def _make_batch(
    run_ref="run:my-proj.run-01",
    stage_ref="stage:my-proj.run-01.train",
    batch_ref="batch:my-proj.run-01.train.batch-0",
):
    return BatchExecution(
        batch_execution_ref=batch_ref,
        run_ref=run_ref,
        stage_execution_ref=stage_ref,
        batch_name="batch-0",
        status="open",
        started_at=TS,
    )


def _make_deployment(
    project_ref="project:my-proj",
    deployment_ref="deployment:my-proj.recommendation-api",
    run_ref="run:my-proj.run-01",
):
    return DeploymentExecution(
        deployment_execution_ref=deployment_ref,
        project_ref=project_ref,
        deployment_name="recommendation-api",
        status="open",
        started_at=TS,
        run_ref=run_ref,
        artifact_ref="artifact:my-proj.run-01.model",
    )


def _make_sample(
    run_ref="run:my-proj.run-01",
    stage_ref="stage:my-proj.run-01.train",
    sample_ref="sample:my-proj.run-01.train.item-0001",
    batch_ref=None,
):
    return SampleObservation(
        sample_observation_ref=sample_ref,
        run_ref=run_ref,
        stage_execution_ref=stage_ref,
        batch_execution_ref=batch_ref,
        sample_name="item-0001",
        observed_at=TS,
        retention_class="debug",
        redaction_profile="metadata-only",
    )


# ---------------------------------------------------------------------------
# ProjectRepository
# ---------------------------------------------------------------------------

class TestProjectRepository:
    def test_put_and_get(self, store):
        p = _make_project()
        store.projects.put_project(p)
        fetched = store.projects.get_project("project:my-proj")
        assert fetched.name == "My Project"

    def test_exists_true(self, store):
        store.projects.put_project(_make_project())
        assert store.projects.exists_project("project:my-proj")

    def test_exists_false(self, store):
        assert not store.projects.exists_project("project:missing")

    def test_list_projects(self, store):
        store.projects.put_project(_make_project("project:proj-a", "A"))
        store.projects.put_project(_make_project("project:proj-b", "B"))
        projects = store.projects.list_projects()
        refs = [str(p.project_ref) for p in projects]
        assert "project:proj-a" in refs
        assert "project:proj-b" in refs

    def test_get_missing_raises(self, store):
        with pytest.raises(NotFoundError):
            store.projects.get_project("project:missing")

    def test_upsert_replaces_existing(self, store):
        store.projects.put_project(_make_project())
        p2 = Project(project_ref="project:my-proj", name="Updated", created_at=TS)
        store.projects.put_project(p2)
        fetched = store.projects.get_project("project:my-proj")
        assert fetched.name == "Updated"


# ---------------------------------------------------------------------------
# RunRepository
# ---------------------------------------------------------------------------

class TestRunRepository:
    def test_put_and_get(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        fetched = store.runs.get_run("run:my-proj.run-01")
        assert fetched.status == "open"

    def test_run_requires_existing_project(self, store):
        with pytest.raises(NotFoundError):
            store.runs.put_run(_make_run())

    def test_list_runs_by_project(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run(run_ref="run:my-proj.run-01"))
        store.runs.put_run(_make_run(run_ref="run:my-proj.run-02"))
        runs = store.runs.list_runs("project:my-proj")
        assert len(runs) == 2

    def test_find_run_returns_none_if_missing(self, store):
        result = store.runs.find_run("run:ghost")
        assert result is None

    def test_exists_run(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        assert store.runs.exists_run("run:my-proj.run-01")
        assert not store.runs.exists_run("run:missing")


# ---------------------------------------------------------------------------
# DeploymentRepository
# ---------------------------------------------------------------------------

class TestDeploymentRepository:
    def test_put_and_get(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        store.deployments.put_deployment_execution(_make_deployment())
        fetched = store.deployments.get_deployment_execution("deployment:my-proj.recommendation-api")
        assert fetched.deployment_name == "recommendation-api"

    def test_list_deployments_by_run(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        store.deployments.put_deployment_execution(_make_deployment())
        deployments = store.deployments.list_deployment_executions(run_ref="run:my-proj.run-01")
        assert len(deployments) == 1

    def test_deployment_requires_existing_project(self, store):
        with pytest.raises(NotFoundError):
            store.deployments.put_deployment_execution(_make_deployment())

    def test_run_snapshot_includes_deployments(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        store.deployments.put_deployment_execution(_make_deployment())
        snapshot = store.build_run_snapshot("run:my-proj.run-01")
        assert len(snapshot.deployments) == 1
        assert str(snapshot.deployments[0].deployment_execution_ref) == "deployment:my-proj.recommendation-api"


# ---------------------------------------------------------------------------
# StageRepository
# ---------------------------------------------------------------------------

class TestStageRepository:
    def test_put_and_get(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        store.stages.put_stage_execution(_make_stage())
        fetched = store.stages.get_stage_execution("stage:my-proj.run-01.train")
        assert fetched.stage_name == "train"

    def test_list_stages_by_run(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        store.stages.put_stage_execution(_make_stage())
        stages = store.stages.list_stage_executions("run:my-proj.run-01")
        assert len(stages) == 1

    def test_stage_requires_existing_run(self, store):
        with pytest.raises(NotFoundError):
            store.stages.put_stage_execution(_make_stage())


# ---------------------------------------------------------------------------
# BatchRepository
# ---------------------------------------------------------------------------

class TestBatchRepository:
    def test_put_and_get(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        store.stages.put_stage_execution(_make_stage())
        store.batches.put_batch_execution(_make_batch())
        fetched = store.batches.get_batch_execution("batch:my-proj.run-01.train.batch-0")
        assert fetched.batch_name == "batch-0"

    def test_list_batches_by_run(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        store.stages.put_stage_execution(_make_stage())
        store.batches.put_batch_execution(_make_batch())
        batches = store.batches.list_batch_executions(run_ref="run:my-proj.run-01")
        assert len(batches) == 1

    def test_batch_requires_existing_stage(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        with pytest.raises(NotFoundError):
            store.batches.put_batch_execution(_make_batch())


class TestSampleRepository:
    def test_put_and_get_stage_owned_sample(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        store.stages.put_stage_execution(_make_stage())
        store.samples.put_sample_observation(_make_sample())
        fetched = store.samples.get_sample_observation("sample:my-proj.run-01.train.item-0001")
        assert fetched.sample_name == "item-0001"

    def test_put_and_get_batch_owned_sample(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        store.stages.put_stage_execution(_make_stage())
        store.batches.put_batch_execution(_make_batch())
        store.samples.put_sample_observation(
            _make_sample(
                sample_ref="sample:my-proj.run-01.train.batch-0.item-0001",
                batch_ref="batch:my-proj.run-01.train.batch-0",
            )
        )
        fetched = store.samples.get_sample_observation("sample:my-proj.run-01.train.batch-0.item-0001")
        assert str(fetched.batch_execution_ref) == "batch:my-proj.run-01.train.batch-0"

    def test_run_snapshot_includes_samples(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        store.stages.put_stage_execution(_make_stage())
        store.samples.put_sample_observation(_make_sample())
        snapshot = store.build_run_snapshot("run:my-proj.run-01")
        assert len(snapshot.samples) == 1

    def test_sample_requires_existing_stage(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        with pytest.raises(NotFoundError):
            store.samples.put_sample_observation(_make_sample())


# ---------------------------------------------------------------------------
# EnvironmentRepository
# ---------------------------------------------------------------------------

class TestEnvironmentRepository:
    def test_put_and_get(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        env = EnvironmentSnapshot(
            environment_snapshot_ref="environment:my-proj.run-01.snap",
            run_ref="run:my-proj.run-01",
            captured_at=TS,
            python_version="3.11.0",
            platform="Linux",
        )
        store.environments.put_environment_snapshot(env)
        fetched = store.environments.get_environment_snapshot("environment:my-proj.run-01.snap")
        assert fetched.python_version == "3.11.0"

    def test_list_environments_by_run(self, store):
        store.projects.put_project(_make_project())
        store.runs.put_run(_make_run())
        env = EnvironmentSnapshot(
            environment_snapshot_ref="environment:my-proj.run-01.snap",
            run_ref="run:my-proj.run-01",
            captured_at=TS,
            python_version="3.11.0",
            platform="Linux",
        )
        store.environments.put_environment_snapshot(env)
        envs = store.environments.list_environment_snapshots("run:my-proj.run-01")
        assert len(envs) == 1


# ---------------------------------------------------------------------------
# RelationRepository
# ---------------------------------------------------------------------------

class TestRelationRepository:
    def test_put_and_get(self, store):
        edge = LineageEdge(
            relation_ref="relation:edge-01",
            relation_type="generated_from",
            source_ref="artifact:my-proj.run-01.dataset",
            target_ref="artifact:my-proj.run-01.model",
            recorded_at=TS,
            origin_marker="explicit",
            confidence_marker="high",
        )
        store.relations.put_relation(edge)
        fetched = store.relations.get_relation("relation:edge-01")
        assert fetched.relation_type == "generated_from"

    def test_list_relations_by_ref(self, store):
        edge = LineageEdge(
            relation_ref="relation:edge-02",
            relation_type="produced_by",
            source_ref="artifact:my-proj.run-01.dataset",
            target_ref="artifact:my-proj.run-01.model",
            recorded_at=TS,
            origin_marker="explicit",
            confidence_marker="medium",
        )
        store.relations.put_relation(edge)
        rels = store.relations.list_relations_for_ref("artifact:my-proj.run-01.dataset")
        assert len(rels) >= 1


# ---------------------------------------------------------------------------
# ProvenanceRepository
# ---------------------------------------------------------------------------

class TestProvenanceRepository:
    def test_put_and_get(self, store):
        edge = LineageEdge(
            relation_ref="relation:edge-p1",
            relation_type="generated_from",
            source_ref="artifact:my-proj.run-01.src",
            target_ref="artifact:my-proj.run-01.dst",
            recorded_at=TS,
            origin_marker="explicit",
            confidence_marker="high",
        )
        store.relations.put_relation(edge)
        prov = ProvenanceRecord(
            provenance_ref="provenance:prov-01",
            relation_ref="relation:edge-p1",
            assertion_mode="explicit",
            asserted_at=TS,
        )
        store.provenance.put_provenance(prov)
        fetched = store.provenance.get_provenance("provenance:prov-01")
        assert fetched.assertion_mode == "explicit"
