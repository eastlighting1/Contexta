"""TST-015: verify, verify-all, export/import, retention tests."""

from __future__ import annotations

import pytest

from contexta.contract.models.artifacts import ArtifactManifest
from contexta.store.artifacts import (
    ArtifactStore,
    VaultConfig,
    VerificationStatus,
    export_artifact,
    import_export_package,
    inspect_store,
    plan_retention,
    verify_all,
    verify_artifact,
)


TS = "2024-01-01T00:00:00Z"
RUN = "run:my-proj.run-01"


@pytest.fixture()
def artifact_store(tmp_path):
    return ArtifactStore(VaultConfig(root_path=tmp_path / "artifacts"))


@pytest.fixture()
def artifact_store_with_content(artifact_store, tmp_path):
    content = b"artifact content for testing"
    path = tmp_path / "model.bin"
    path.write_bytes(content)
    manifest = ArtifactManifest(
        artifact_ref="artifact:my-proj.run-01.model",
        artifact_kind="checkpoint",
        created_at=TS,
        producer_ref="contexta.test",
        run_ref=RUN,
        location_ref="vault://my-proj/run-01/model.bin",
    )
    artifact_store.put_artifact(manifest, path)
    return artifact_store


# ---------------------------------------------------------------------------
# verify_artifact
# ---------------------------------------------------------------------------

class TestVerifyArtifact:
    def test_verify_existing_artifact(self, artifact_store_with_content):
        report = verify_artifact(artifact_store_with_content, "artifact:my-proj.run-01.model")
        assert report is not None
        assert report.status == VerificationStatus.VERIFIED

    def test_verify_missing_artifact(self, artifact_store):
        from contexta.common.errors import NotFoundError
        with pytest.raises(NotFoundError):
            verify_artifact(artifact_store, "artifact:my-proj.run-01.missing")


# ---------------------------------------------------------------------------
# verify_all
# ---------------------------------------------------------------------------

class TestVerifyAll:
    def test_verify_all_returns_sweep_report(self, artifact_store_with_content):
        report = verify_all(artifact_store_with_content)
        assert report is not None
        assert hasattr(report, "verification_records")

    def test_verify_all_empty_store(self, artifact_store):
        report = verify_all(artifact_store)
        assert report is not None
        assert len(report.missing_refs) == 0

    def test_all_artifacts_verified(self, artifact_store_with_content):
        report = verify_all(artifact_store_with_content)
        assert len(report.missing_refs) == 0
        assert len(report.drifted_refs) == 0


# ---------------------------------------------------------------------------
# inspect_store
# ---------------------------------------------------------------------------

class TestInspectStore:
    def test_inspect_empty_store(self, artifact_store):
        summary = inspect_store(artifact_store)
        assert summary is not None
        assert summary.artifact_count == 0

    def test_inspect_store_with_content(self, artifact_store_with_content):
        summary = inspect_store(artifact_store_with_content)
        assert summary.artifact_count == 1
        assert summary.verified_count == 1
        assert summary.total_size_bytes > 0


# ---------------------------------------------------------------------------
# export_artifact / import_export_package
# ---------------------------------------------------------------------------

class TestExportImport:
    def test_export_creates_package(self, artifact_store_with_content, tmp_path):
        receipt = export_artifact(artifact_store_with_content, "artifact:my-proj.run-01.model")
        assert receipt is not None
        assert receipt.export_directory.exists()

    def test_export_to_custom_root(self, artifact_store_with_content, tmp_path):
        export_root = tmp_path / "my_exports"
        receipt = export_artifact(
            artifact_store_with_content,
            "artifact:my-proj.run-01.model",
            export_root=export_root,
        )
        assert receipt is not None
        assert receipt.export_directory.exists()
        assert receipt.body_path.exists()

    def test_import_from_exported_package(self, artifact_store_with_content, tmp_path):
        receipt = export_artifact(
            artifact_store_with_content,
            "artifact:my-proj.run-01.model",
            export_root=tmp_path / "exports",
        )

        # Import into a new store
        target_store = ArtifactStore(VaultConfig(root_path=tmp_path / "imported"))
        import_receipt = import_export_package(target_store, receipt.export_directory)
        assert import_receipt is not None
        assert import_receipt.outcome is not None


# ---------------------------------------------------------------------------
# plan_retention
# ---------------------------------------------------------------------------

class TestRetention:
    def test_plan_retention_empty_store(self, artifact_store):
        plan = plan_retention(artifact_store)
        assert plan is not None
        assert hasattr(plan, "keep")
        assert hasattr(plan, "review")

    def test_plan_retention_all_in_review(self, artifact_store_with_content):
        plan = plan_retention(artifact_store_with_content)
        assert len(plan.review) == 1
        assert len(plan.keep) == 0

    def test_plan_retention_with_keep_refs(self, artifact_store_with_content):
        plan = plan_retention(
            artifact_store_with_content,
            refs_to_keep={"artifact:my-proj.run-01.model"},
        )
        assert len(plan.keep) == 1
        assert len(plan.review) == 0
