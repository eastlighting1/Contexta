"""TST-007: RuntimeSession, RunScope, StageScope, OperationScope tests."""

from __future__ import annotations

import pytest

from contexta.common.errors import ClosedScopeError, LifecycleError
from contexta.config.models import UnifiedConfig, WorkspaceConfig


def _make_config(tmp_path):
    return UnifiedConfig(
        project_name="test-proj",
        workspace=WorkspaceConfig(root_path=tmp_path / ".contexta"),
    )


# ---------------------------------------------------------------------------
# RuntimeSession bootstrapping
# ---------------------------------------------------------------------------

class TestRuntimeSession:
    def test_session_initializes(self, tmp_path):
        from contexta.runtime.session import RuntimeSession
        from contexta.capture.dispatch import CaptureDispatcher

        config = _make_config(tmp_path)
        dispatcher = CaptureDispatcher.with_default_local_sink(config=config)
        session = RuntimeSession(config=config, dispatcher=dispatcher)
        assert session.project_name == "test-proj"

    def test_project_ref_kind(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        assert session.project_ref.kind == "project"

    def test_no_active_run_raises(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with pytest.raises(LifecycleError, match="run"):
            session.current_run()

    def test_no_active_stage_raises(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with pytest.raises(LifecycleError, match="stage"):
            session.current_stage()

    def test_no_active_batch_raises(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with pytest.raises(LifecycleError, match="batch"):
            session.current_batch()

    def test_no_active_sample_raises(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with pytest.raises(LifecycleError, match="sample"):
            session.current_sample()

    def test_no_active_deployment_raises(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with pytest.raises(LifecycleError, match="deployment"):
            session.current_deployment()


# ---------------------------------------------------------------------------
# RunScope
# ---------------------------------------------------------------------------

class TestRunScope:
    def test_start_and_close_run(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        run = session.start_run("my-run")
        assert run.status == "open"
        run.close(status="completed")
        assert run.status == "completed"
        assert run.is_closed

    def test_run_ref_contains_project(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        run = session.start_run("exp-01")
        assert "test-proj" in run.ref
        run.close()

    def test_context_manager_closes_run(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("ctx-run") as run:
            assert not run.is_closed
        assert run.is_closed

    def test_nested_runs_not_allowed(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        run = session.start_run("outer")
        with pytest.raises(LifecycleError, match="[Nn]ested"):
            session.start_run("inner")
        run.close()

    def test_failed_run_on_exception(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        try:
            with session.start_run("failing") as run:
                raise ValueError("boom")
        except ValueError:
            pass
        assert run.status == "failed"

    def test_closed_run_cannot_close_again(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        run = session.start_run("once")
        run.close()
        with pytest.raises((LifecycleError, ClosedScopeError)):
            run.close()


# ---------------------------------------------------------------------------
# StageScope
# ---------------------------------------------------------------------------

class TestStageScope:
    def test_start_and_close_stage(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("run-a") as run:
            stage = run.stage("train")
            assert stage.status == "open"
            stage.close()
            assert stage.is_closed

    def test_stage_ref_contains_run(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("run-b") as run:
            with run.stage("eval") as stage:
                assert "run-b" in stage.ref or "run" in stage.ref

    def test_stage_context_manager(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("r") as run:
            with run.stage("s") as stage:
                assert not stage.is_closed
            assert stage.is_closed


# ---------------------------------------------------------------------------
# OperationScope
# ---------------------------------------------------------------------------

class TestOperationScope:
    def test_start_operation(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("r") as run:
            with run.stage("s") as stage:
                op = stage.operation("forward")
                assert op.status == "open"
                op.close()

    def test_operation_context_manager(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("r") as run:
            with run.stage("s") as stage:
                with stage.operation("op-a") as op:
                    assert not op.is_closed
                assert op.is_closed


# ---------------------------------------------------------------------------
# BatchScope
# ---------------------------------------------------------------------------

class TestBatchScope:
    def test_start_and_close_batch(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("r") as run:
            with run.stage("train") as stage:
                batch = stage.batch("batch-0")
                assert batch.status == "open"
                assert session.current_batch() is batch
                batch.close()
                assert batch.is_closed

    def test_batch_operation_ref_uses_batch_owner(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("r") as run:
            with run.stage("train") as stage:
                with stage.batch("batch-0") as batch:
                    with batch.operation("fit") as op:
                        assert ".train.batch-0.fit" in op.ref

    def test_stage_sample_ref_uses_stage_owner(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("r") as run:
            with run.stage("train") as stage:
                with stage.sample("item-1") as sample:
                    assert ".train.item-1" in sample.ref
                    assert session.current_sample() is sample

    def test_batch_sample_ref_uses_batch_owner(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("r") as run:
            with run.stage("train") as stage:
                with stage.batch("batch-0") as batch:
                    with batch.sample("item-1") as sample:
                        assert ".train.batch-0.item-1" in sample.ref

    def test_operation_blocked_while_sample_active(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_run("r") as run:
            with run.stage("train") as stage:
                with stage.sample("item-1"):
                    with pytest.raises(LifecycleError, match="sample"):
                        stage.operation("fit")


# ---------------------------------------------------------------------------
# DeploymentScope
# ---------------------------------------------------------------------------

class TestDeploymentScope:
    def test_start_and_close_deployment(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        deployment = session.start_deployment("recommendation-api")
        assert deployment.status == "open"
        assert session.current_deployment() is deployment
        deployment.close()
        assert deployment.is_closed

    def test_deployment_capture_uses_linked_run_when_present(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        with session.start_deployment("recommendation-api", run_ref="run:test-proj.run-01") as deployment:
            result = deployment.event("deploy.started", message="started")
            assert str(result.payload.envelope.deployment_execution_ref) == "deployment:test-proj.recommendation-api"

    def test_deployment_scope_blocks_nested_run(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        deployment = session.start_deployment("recommendation-api")
        with pytest.raises(LifecycleError, match="[Rr]un"):
            session.start_run("nested-run")
        deployment.close()
