"""TST-014: put, staged ingest, get/open/read/list tests."""

from __future__ import annotations

import io

import pytest

from contexta.contract.models.artifacts import ArtifactManifest
from contexta.store.artifacts import (
    ArtifactStore,
    VaultConfig,
    artifact_exists,
    get_artifact,
    list_refs,
    open_artifact,
    read_artifact_bytes,
)


TS = "2024-01-01T00:00:00Z"
RUN = "run:my-proj.run-01"


@pytest.fixture()
def artifact_store(tmp_path):
    return ArtifactStore(VaultConfig(root_path=tmp_path / "artifacts"))


def _make_manifest(ref="artifact:my-proj.run-01.model", kind="checkpoint"):
    return ArtifactManifest(
        artifact_ref=ref,
        artifact_kind=kind,
        created_at=TS,
        producer_ref="contexta.test",
        run_ref=RUN,
        location_ref="vault://my-proj/run-01/model.bin",
    )


def _write_artifact_file(tmp_path, content=b"model weights", name="model.bin"):
    path = tmp_path / name
    path.write_bytes(content)
    return path


# ---------------------------------------------------------------------------
# put_artifact
# ---------------------------------------------------------------------------

class TestPutArtifact:
    def test_put_returns_receipt(self, artifact_store, tmp_path):
        path = _write_artifact_file(tmp_path)
        manifest = _make_manifest()
        receipt = artifact_store.put_artifact(manifest, path)
        assert receipt is not None
        assert receipt.binding.artifact_ref == "artifact:my-proj.run-01.model"

    def test_put_records_size(self, artifact_store, tmp_path):
        content = b"hello world"
        path = _write_artifact_file(tmp_path, content)
        receipt = artifact_store.put_artifact(_make_manifest(), path)
        assert receipt.binding.size_bytes == len(content)

    def test_put_records_hash(self, artifact_store, tmp_path):
        path = _write_artifact_file(tmp_path)
        receipt = artifact_store.put_artifact(_make_manifest(), path)
        assert receipt.binding.hash_value is not None

    def test_put_idempotent_same_content(self, artifact_store, tmp_path):
        path = _write_artifact_file(tmp_path)
        artifact_store.put_artifact(_make_manifest(), path)
        # Second put with same content should return without error
        receipt2 = artifact_store.put_artifact(_make_manifest(), path)
        assert receipt2.bytes_written == 0  # no bytes re-written

    def test_put_different_content_conflict(self, artifact_store, tmp_path):
        from contexta.common.errors import ConflictError
        path1 = _write_artifact_file(tmp_path, b"content1", "m1.bin")
        path2 = _write_artifact_file(tmp_path, b"content2", "m2.bin")
        artifact_store.put_artifact(_make_manifest(), path1)
        with pytest.raises(ConflictError):
            artifact_store.put_artifact(_make_manifest(), path2)


# ---------------------------------------------------------------------------
# put_artifact_from_stream
# ---------------------------------------------------------------------------

class TestPutArtifactFromStream:
    def test_stream_ingest(self, artifact_store):
        manifest = _make_manifest("artifact:my-proj.run-01.streamed")
        data = b"streamed data"
        stream = io.BytesIO(data)
        receipt = artifact_store.put_artifact_from_stream(manifest, stream, source_name="streamed.bin")
        assert receipt.binding.size_bytes == len(data)


# ---------------------------------------------------------------------------
# get_artifact / artifact_exists / open_artifact / read_artifact_bytes
# ---------------------------------------------------------------------------

class TestReadArtifact:
    def test_artifact_exists_true(self, artifact_store, tmp_path):
        path = _write_artifact_file(tmp_path)
        artifact_store.put_artifact(_make_manifest(), path)
        assert artifact_exists(artifact_store, "artifact:my-proj.run-01.model")

    def test_artifact_exists_false(self, artifact_store):
        assert not artifact_exists(artifact_store, "artifact:my-proj.run-01.missing")

    def test_get_artifact_handle(self, artifact_store, tmp_path):
        path = _write_artifact_file(tmp_path)
        artifact_store.put_artifact(_make_manifest(), path)
        handle = get_artifact(artifact_store, "artifact:my-proj.run-01.model")
        assert handle is not None
        assert handle.binding.artifact_ref == "artifact:my-proj.run-01.model"

    def test_get_missing_artifact_raises(self, artifact_store):
        from contexta.common.errors import NotFoundError
        with pytest.raises(NotFoundError):
            get_artifact(artifact_store, "artifact:my-proj.run-01.missing")

    def test_read_artifact_bytes(self, artifact_store, tmp_path):
        content = b"binary content"
        path = _write_artifact_file(tmp_path, content)
        artifact_store.put_artifact(_make_manifest(), path)
        data = read_artifact_bytes(artifact_store, "artifact:my-proj.run-01.model")
        assert data == content

    def test_open_artifact_readable(self, artifact_store, tmp_path):
        content = b"read me"
        path = _write_artifact_file(tmp_path, content)
        artifact_store.put_artifact(_make_manifest(), path)
        with open_artifact(artifact_store, "artifact:my-proj.run-01.model") as f:
            data = f.read()
        assert data == content


# ---------------------------------------------------------------------------
# list_refs
# ---------------------------------------------------------------------------

class TestListRefs:
    def test_list_refs_empty(self, artifact_store):
        refs = list_refs(artifact_store)
        assert refs == () or refs == []

    def test_list_refs_after_put(self, artifact_store, tmp_path):
        path = _write_artifact_file(tmp_path)
        artifact_store.put_artifact(_make_manifest(), path)
        refs = list_refs(artifact_store)
        assert "artifact:my-proj.run-01.model" in refs
