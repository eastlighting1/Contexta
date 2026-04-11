"""TST-009: span and register_artifact tests."""

from __future__ import annotations

import pytest

from contexta.capture.models import ArtifactRegistrationEmission, SpanEmission
from contexta.common.errors import ValidationError
from contexta.config.models import UnifiedConfig, WorkspaceConfig


def _make_config(tmp_path):
    return UnifiedConfig(
        project_name="test-proj",
        workspace=WorkspaceConfig(root_path=tmp_path / ".contexta"),
    )


# ---------------------------------------------------------------------------
# SpanEmission model
# ---------------------------------------------------------------------------

class TestSpanEmission:
    def test_minimal_valid(self):
        from contexta.common.time import iso_utc_now
        ts = iso_utc_now()
        s = SpanEmission(name="forward", started_at=ts, ended_at=ts)
        assert s.name == "forward"

    def test_invalid_span_kind_raises(self):
        from contexta.common.time import iso_utc_now
        ts = iso_utc_now()
        with pytest.raises(ValidationError):
            SpanEmission(name="x", started_at=ts, ended_at=ts, span_kind="rpc")

    def test_invalid_status_raises(self):
        from contexta.common.time import iso_utc_now
        ts = iso_utc_now()
        with pytest.raises(ValidationError):
            SpanEmission(name="x", started_at=ts, ended_at=ts, status="running")


# ---------------------------------------------------------------------------
# ArtifactRegistrationEmission model
# ---------------------------------------------------------------------------

class TestArtifactRegistrationEmission:
    def test_minimal_valid(self, tmp_path):
        fake_path = tmp_path / "model.pt"
        fake_path.write_bytes(b"x")
        e = ArtifactRegistrationEmission(
            artifact_kind="checkpoint",
            path=str(fake_path),
        )
        assert e.artifact_kind == "checkpoint"

    def test_blank_kind_raises(self, tmp_path):
        fake_path = tmp_path / "f.bin"
        fake_path.write_bytes(b"y")
        with pytest.raises(ValidationError):
            ArtifactRegistrationEmission(artifact_kind="", path=str(fake_path))


# ---------------------------------------------------------------------------
# capture_span via scope
# ---------------------------------------------------------------------------

class TestCaptureSpan:
    def test_span_capture_returns_result(self, tmp_path):
        from contexta.runtime.session import RuntimeSession
        from contexta.common.time import iso_utc_now

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        ts = iso_utc_now()
        with session.start_run("run-sp") as run:
            with run.stage("train") as stage:
                result = stage.span("forward", started_at=ts, ended_at=ts)
                assert result is not None

    def test_emit_spans_batch(self, tmp_path):
        from contexta.runtime.session import RuntimeSession
        from contexta.common.time import iso_utc_now

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        ts = iso_utc_now()
        with session.start_run("run-sp2") as run:
            with run.stage("s") as stage:
                emissions = [
                    SpanEmission(name="op.a", started_at=ts, ended_at=ts),
                    SpanEmission(name="op.b", started_at=ts, ended_at=ts),
                ]
                result = stage.emit_spans(emissions)
                assert result is not None


# ---------------------------------------------------------------------------
# register_artifact via scope
# ---------------------------------------------------------------------------

class TestRegisterArtifact:
    def test_register_artifact_creates_receipt(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)

        artifact_path = tmp_path / "model.bin"
        artifact_path.write_bytes(b"model weights")

        with session.start_run("run-art") as run:
            with run.stage("train") as stage:
                result = stage.register_artifact(
                    "checkpoint",
                    str(artifact_path),
                )
                assert result is not None

    def test_register_artifact_missing_file_raises_by_default(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)

        with session.start_run("run-art2") as run:
            with run.stage("s") as stage:
                with pytest.raises(Exception):
                    stage.register_artifact(
                        "checkpoint",
                        str(tmp_path / "nonexistent.bin"),
                        allow_missing=False,
                    )

    def test_batch_scope_artifact_manifest_carries_batch_ref(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        artifact_path = tmp_path / "batch-model.bin"
        artifact_path.write_bytes(b"batch model")

        with session.start_run("run-batch-artifact") as run:
            with run.stage("train") as stage:
                with stage.batch("batch-0") as batch:
                    result = batch.register_artifact("checkpoint", str(artifact_path))
                    manifest = result.payload["manifest"]
                    assert str(manifest.batch_execution_ref) == "batch:test-proj.run-batch-artifact.train.batch-0"

    def test_deployment_scope_artifact_manifest_carries_deployment_ref(self, tmp_path):
        from contexta.runtime.session import RuntimeSession

        config = _make_config(tmp_path)
        session = RuntimeSession(config=config)
        artifact_path = tmp_path / "deploy-model.bin"
        artifact_path.write_bytes(b"deploy model")

        with session.start_deployment("recommendation-api", run_ref="run:test-proj.run-01") as deployment:
            result = deployment.register_artifact("checkpoint", str(artifact_path))
            manifest = result.payload["manifest"]
            assert str(manifest.deployment_execution_ref) == "deployment:test-proj.recommendation-api"
