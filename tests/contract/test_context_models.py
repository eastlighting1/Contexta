"""TST-002: Project, Run, Stage, Operation model tests."""

import pytest

from contexta.common.errors import ValidationError
from contexta.contract.models.context import (
    BatchExecution,
    DeploymentExecution,
    EnvironmentSnapshot,
    OperationContext,
    Project,
    RUN_STAGE_STATUSES,
    Run,
    SampleObservation,
    StageExecution,
)
from contexta.contract.refs import StableRef


TS = "2024-01-01T00:00:00Z"
TS2 = "2024-01-01T01:00:00Z"


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class TestProject:
    def test_minimal_valid(self):
        p = Project(project_ref="project:my-proj", name="My Project", created_at=TS)
        assert p.name == "My Project"
        assert str(p.project_ref) == "project:my-proj"

    def test_ref_coerced_from_string(self):
        p = Project(project_ref="project:my-proj", name="X", created_at=TS)
        assert isinstance(p.project_ref, StableRef)

    def test_tags_normalized(self):
        p = Project(project_ref="project:my-proj", name="X", created_at=TS, tags={"env": "prod"})
        assert p.tags["env"] == "prod"

    def test_description_stripped(self):
        p = Project(project_ref="project:my-proj", name="X", created_at=TS, description="  hi  ")
        assert p.description == "hi"

    def test_blank_name_raises(self):
        with pytest.raises(ValidationError):
            Project(project_ref="project:my-proj", name="   ", created_at=TS)

    def test_wrong_ref_kind_raises(self):
        with pytest.raises(ValidationError):
            Project(project_ref="run:my-proj.run-01", name="X", created_at=TS)

    def test_timestamp_must_end_with_z(self):
        with pytest.raises(ValidationError):
            Project(project_ref="project:my-proj", name="X", created_at="2024-01-01T00:00:00")

    def test_to_dict_has_required_keys(self):
        p = Project(project_ref="project:my-proj", name="X", created_at=TS)
        d = p.to_dict()
        assert "project_ref" in d
        assert "name" in d
        assert "created_at" in d


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

class TestRun:
    def _make_run(self, **overrides):
        defaults = dict(
            run_ref="run:my-proj.run-01",
            project_ref="project:my-proj",
            name="Run 1",
            status="open",
            started_at=TS,
        )
        defaults.update(overrides)
        return Run(**defaults)

    def test_minimal_valid_open(self):
        r = self._make_run()
        assert r.status == "open"
        assert r.ended_at is None

    def test_completed_run(self):
        r = self._make_run(status="completed", ended_at=TS2)
        assert r.status == "completed"
        assert r.ended_at is not None

    def test_open_with_ended_at_raises(self):
        with pytest.raises(ValidationError):
            self._make_run(status="open", ended_at=TS2)

    def test_completed_without_ended_at_raises(self):
        with pytest.raises(ValidationError):
            self._make_run(status="completed")

    def test_ended_before_started_raises(self):
        with pytest.raises(ValidationError):
            self._make_run(status="completed", started_at=TS2, ended_at=TS)

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            self._make_run(status="running")

    def test_run_ref_must_share_project_prefix(self):
        with pytest.raises(ValidationError):
            self._make_run(run_ref="run:other-proj.run-01", project_ref="project:my-proj")

    def test_all_statuses_accepted(self):
        for status in RUN_STAGE_STATUSES:
            ended = TS2 if status != "open" else None
            r = self._make_run(status=status, ended_at=ended)
            assert r.status == status

    def test_to_dict_keys(self):
        r = self._make_run()
        d = r.to_dict()
        for key in ("run_ref", "project_ref", "name", "status", "started_at"):
            assert key in d


# ---------------------------------------------------------------------------
# StageExecution
# ---------------------------------------------------------------------------

class TestStageExecution:
    def _make_stage(self, **overrides):
        defaults = dict(
            stage_execution_ref="stage:my-proj.run-01.train",
            run_ref="run:my-proj.run-01",
            stage_name="train",
            status="open",
            started_at=TS,
        )
        defaults.update(overrides)
        return StageExecution(**defaults)

    def test_minimal_valid(self):
        s = self._make_stage()
        assert s.stage_name == "train"
        assert s.status == "open"

    def test_stage_ref_must_equal_run_ref_plus_stage_name(self):
        with pytest.raises(ValidationError):
            self._make_stage(stage_execution_ref="stage:my-proj.run-01.other")

    def test_order_index_zero_allowed(self):
        s = self._make_stage(order_index=0)
        assert s.order_index == 0

    def test_order_index_negative_raises(self):
        with pytest.raises(ValidationError):
            self._make_stage(order_index=-1)

    def test_stage_name_must_be_kebab(self):
        with pytest.raises(ValidationError):
            self._make_stage(
                stage_name="Train_Step",
                stage_execution_ref="stage:my-proj.run-01.Train_Step",
            )

    def test_to_dict_contains_order_index(self):
        s = self._make_stage(order_index=2)
        assert s.to_dict()["order_index"] == 2


# ---------------------------------------------------------------------------
# OperationContext
# ---------------------------------------------------------------------------

class TestOperationContext:
    def test_minimal_valid(self):
        op = OperationContext(
            operation_context_ref="op:my-proj.run-01.train.fit",
            run_ref="run:my-proj.run-01",
            stage_execution_ref="stage:my-proj.run-01.train",
            operation_name="fit",
            observed_at=TS,
        )
        assert op.operation_name == "fit"

    def test_op_ref_must_equal_stage_plus_op_name(self):
        with pytest.raises(ValidationError):
            OperationContext(
                operation_context_ref="op:my-proj.run-01.train.wrong",
                run_ref="run:my-proj.run-01",
                stage_execution_ref="stage:my-proj.run-01.train",
                operation_name="fit",
                observed_at=TS,
            )

    def test_stage_must_share_run_prefix(self):
        with pytest.raises(ValidationError):
            OperationContext(
                operation_context_ref="op:my-proj.run-01.train.fit",
                run_ref="run:other-proj.run-01",
                stage_execution_ref="stage:my-proj.run-01.train",
                operation_name="fit",
                observed_at=TS,
            )

    def test_batch_owned_operation_is_valid(self):
        op = OperationContext(
            operation_context_ref="op:my-proj.run-01.train.batch-0.fit",
            run_ref="run:my-proj.run-01",
            stage_execution_ref="stage:my-proj.run-01.train",
            batch_execution_ref="batch:my-proj.run-01.train.batch-0",
            operation_name="fit",
            observed_at=TS,
        )
        assert str(op.batch_execution_ref) == "batch:my-proj.run-01.train.batch-0"


# ---------------------------------------------------------------------------
# BatchExecution
# ---------------------------------------------------------------------------

class TestBatchExecution:
    def _make_batch(self, **overrides):
        defaults = dict(
            batch_execution_ref="batch:my-proj.run-01.train.batch-0",
            run_ref="run:my-proj.run-01",
            stage_execution_ref="stage:my-proj.run-01.train",
            batch_name="batch-0",
            status="open",
            started_at=TS,
        )
        defaults.update(overrides)
        return BatchExecution(**defaults)

    def test_minimal_valid(self):
        batch = self._make_batch()
        assert batch.batch_name == "batch-0"
        assert batch.status == "open"

    def test_batch_ref_must_equal_stage_plus_name(self):
        with pytest.raises(ValidationError):
            self._make_batch(batch_execution_ref="batch:my-proj.run-01.train.other")

    def test_stage_must_share_run_prefix(self):
        with pytest.raises(ValidationError):
            self._make_batch(stage_execution_ref="stage:other-proj.run-01.train")

    def test_order_index_negative_raises(self):
        with pytest.raises(ValidationError):
            self._make_batch(order_index=-1)

    def test_to_dict_contains_order_index(self):
        assert self._make_batch(order_index=2).to_dict()["order_index"] == 2


# ---------------------------------------------------------------------------
# DeploymentExecution
# ---------------------------------------------------------------------------

class TestDeploymentExecution:
    def _make_deployment(self, **overrides):
        defaults = dict(
            deployment_execution_ref="deployment:my-proj.recommendation-api",
            project_ref="project:my-proj",
            deployment_name="recommendation-api",
            status="open",
            started_at=TS,
        )
        defaults.update(overrides)
        return DeploymentExecution(**defaults)

    def test_minimal_valid(self):
        deployment = self._make_deployment()
        assert deployment.deployment_name == "recommendation-api"
        assert deployment.status == "open"

    def test_ref_must_equal_project_plus_name(self):
        with pytest.raises(ValidationError):
            self._make_deployment(deployment_execution_ref="deployment:my-proj.other")

    def test_run_ref_must_share_project_prefix(self):
        with pytest.raises(ValidationError):
            self._make_deployment(run_ref="run:other-proj.run-01")

    def test_to_dict_contains_optional_links(self):
        deployment = self._make_deployment(
            run_ref="run:my-proj.run-01",
            artifact_ref="artifact:my-proj.run-01.model",
        )
        data = deployment.to_dict()
        assert data["run_ref"] == "run:my-proj.run-01"
        assert data["artifact_ref"] == "artifact:my-proj.run-01.model"


# ---------------------------------------------------------------------------
# SampleObservation
# ---------------------------------------------------------------------------

class TestSampleObservation:
    def _make_sample(self, **overrides):
        defaults = dict(
            sample_observation_ref="sample:my-proj.run-01.train.sample-0",
            run_ref="run:my-proj.run-01",
            stage_execution_ref="stage:my-proj.run-01.train",
            sample_name="sample-0",
            observed_at=TS,
        )
        defaults.update(overrides)
        return SampleObservation(**defaults)

    def test_minimal_valid(self):
        sample = self._make_sample()
        assert sample.sample_name == "sample-0"
        assert sample.batch_execution_ref is None
        assert sample.retention_class is None

    def test_ref_must_equal_stage_plus_name(self):
        with pytest.raises(ValidationError):
            self._make_sample(sample_observation_ref="sample:my-proj.run-01.train.other")

    def test_stage_must_share_run_prefix(self):
        with pytest.raises(ValidationError):
            self._make_sample(stage_execution_ref="stage:other-proj.run-01.train")

    def test_batch_owned_ref_must_equal_batch_plus_name(self):
        sample = self._make_sample(
            sample_observation_ref="sample:my-proj.run-01.train.batch-0.sample-0",
            batch_execution_ref="batch:my-proj.run-01.train.batch-0",
            sample_name="sample-0",
        )
        assert sample.batch_execution_ref is not None

    def test_batch_ref_wrong_prefix_raises(self):
        with pytest.raises(ValidationError):
            self._make_sample(
                sample_observation_ref="sample:my-proj.run-01.train.batch-0.sample-0",
                batch_execution_ref="batch:other-proj.run-01.train.batch-0",
                sample_name="sample-0",
            )

    def test_retention_and_redaction_fields_stored(self):
        sample = self._make_sample(
            retention_class="short-term",
            redaction_profile="pii-redact",
        )
        assert sample.retention_class == "short-term"
        assert sample.redaction_profile == "pii-redact"

    def test_to_dict_roundtrip(self):
        sample = self._make_sample(retention_class="long-term")
        data = sample.to_dict()
        assert data["sample_name"] == "sample-0"
        assert data["retention_class"] == "long-term"
        assert data["batch_execution_ref"] is None


# ---------------------------------------------------------------------------
# EnvironmentSnapshot
# ---------------------------------------------------------------------------

class TestEnvironmentSnapshot:
    def test_minimal_valid(self):
        env = EnvironmentSnapshot(
            environment_snapshot_ref="environment:my-proj.run-01.snap",
            run_ref="run:my-proj.run-01",
            captured_at=TS,
            python_version="3.11.0",
            platform="Linux-5.15",
        )
        assert env.python_version == "3.11.0"

    def test_packages_normalized(self):
        env = EnvironmentSnapshot(
            environment_snapshot_ref="environment:my-proj.run-01.snap",
            run_ref="run:my-proj.run-01",
            captured_at=TS,
            python_version="3.11.0",
            platform="Linux",
            packages={"numpy": "1.24.0"},
        )
        assert env.packages["numpy"] == "1.24.0"

    def test_to_dict_includes_packages(self):
        env = EnvironmentSnapshot(
            environment_snapshot_ref="environment:my-proj.run-01.snap",
            run_ref="run:my-proj.run-01",
            captured_at=TS,
            python_version="3.11.0",
            platform="Linux",
        )
        d = env.to_dict()
        assert "packages" in d
        assert "environment_variables" in d
