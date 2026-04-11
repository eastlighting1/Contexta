"""TST-004: ArtifactManifest, LineageEdge, ProvenanceRecord tests."""

import pytest

from contexta.common.errors import ValidationError
from contexta.contract.models.artifacts import ARTIFACT_KINDS, ArtifactManifest
from contexta.contract.models.lineage import (
    ASSERTION_MODES,
    CONFIDENCE_MARKERS,
    LINEAGE_ORIGIN_MARKERS,
    RELATION_TYPES,
    LineageEdge,
    ProvenanceRecord,
)


TS = "2024-01-01T00:00:00Z"
RUN = "run:my-proj.run-01"
ARTIFACT = "artifact:my-proj.run-01.model"
DEPLOYMENT = "deployment:my-proj.recommendation-api"
STAGE = "stage:my-proj.run-01.train"
BATCH = "batch:my-proj.run-01.train.batch-0"
OP = "op:my-proj.run-01.train.fit"


# ---------------------------------------------------------------------------
# ArtifactManifest
# ---------------------------------------------------------------------------

class TestArtifactManifest:
    def _make(self, **overrides):
        defaults = dict(
            artifact_ref=ARTIFACT,
            artifact_kind="checkpoint",
            created_at=TS,
            producer_ref="contexta.test",
            run_ref=RUN,
            location_ref="vault://my-proj/run-01/model.pt",
        )
        defaults.update(overrides)
        return ArtifactManifest(**defaults)

    def test_minimal_valid(self):
        m = self._make()
        assert m.artifact_kind == "checkpoint"

    def test_artifact_ref_must_share_run_prefix(self):
        with pytest.raises(ValidationError):
            self._make(artifact_ref="artifact:other.run-01.model")

    def test_invalid_artifact_kind_pattern(self):
        with pytest.raises(ValidationError):
            self._make(artifact_kind="Checkpoint")

    def test_size_bytes_nonnegative(self):
        m = self._make(size_bytes=0)
        assert m.size_bytes == 0

    def test_negative_size_bytes_raises(self):
        with pytest.raises(ValidationError):
            self._make(size_bytes=-1)

    def test_bool_size_bytes_raises(self):
        with pytest.raises(ValidationError):
            self._make(size_bytes=True)

    def test_hash_value_stored(self):
        m = self._make(hash_value="sha256:abc123")
        assert m.hash_value == "sha256:abc123"

    def test_stage_ref_must_share_run_prefix(self):
        with pytest.raises(ValidationError):
            self._make(
                stage_execution_ref="stage:other.run-01.train",
            )

    def test_op_context_requires_stage(self):
        with pytest.raises(ValidationError):
            self._make(
                operation_context_ref=OP,
                stage_execution_ref=None,
            )

    def test_with_stage_and_op(self):
        m = self._make(
            stage_execution_ref=STAGE,
            operation_context_ref=OP,
        )
        assert str(m.stage_execution_ref) == STAGE

    def test_batch_ref_requires_stage(self):
        with pytest.raises(ValidationError):
            self._make(batch_execution_ref=BATCH)

    def test_batch_ref_must_share_stage_prefix(self):
        with pytest.raises(ValidationError):
            self._make(
                stage_execution_ref=STAGE,
                batch_execution_ref="batch:my-proj.run-01.other.batch-0",
            )

    def test_batch_owned_artifact_is_valid(self):
        m = self._make(
            deployment_execution_ref=DEPLOYMENT,
            stage_execution_ref=STAGE,
            batch_execution_ref=BATCH,
            operation_context_ref="op:my-proj.run-01.train.batch-0.fit",
        )
        assert str(m.batch_execution_ref) == BATCH
        assert str(m.deployment_execution_ref) == DEPLOYMENT

    def test_attributes_normalized(self):
        m = self._make(attributes={"format": "pt"})
        assert m.attributes["format"] == "pt"

    def test_to_dict_keys(self):
        m = self._make()
        d = m.to_dict()
        for key in ("artifact_ref", "artifact_kind", "run_ref", "location_ref", "created_at"):
            assert key in d


# ---------------------------------------------------------------------------
# LineageEdge
# ---------------------------------------------------------------------------

class TestLineageEdge:
    def _make(self, **overrides):
        defaults = dict(
            relation_ref="relation:edge-01",
            relation_type="generated_from",
            source_ref="artifact:my-proj.run-01.dataset",
            target_ref="artifact:my-proj.run-01.model",
            recorded_at=TS,
            origin_marker="explicit",
            confidence_marker="high",
        )
        defaults.update(overrides)
        return LineageEdge(**defaults)

    def test_minimal_valid(self):
        e = self._make()
        assert e.relation_type == "generated_from"
        assert e.confidence_marker == "high"

    def test_self_relation_raises(self):
        ref = "artifact:my-proj.run-01.model"
        with pytest.raises(ValidationError, match="differ"):
            self._make(source_ref=ref, target_ref=ref)

    def test_invalid_relation_type_raises(self):
        with pytest.raises(ValidationError):
            self._make(relation_type="unknown_type")

    def test_invalid_origin_marker_raises(self):
        with pytest.raises(ValidationError):
            self._make(origin_marker="explicit_capture")  # not in LINEAGE_ORIGIN_MARKERS

    def test_all_relation_types(self):
        for rtype in RELATION_TYPES:
            e = self._make(relation_type=rtype)
            assert e.relation_type == rtype

    def test_all_confidence_markers(self):
        for marker in CONFIDENCE_MARKERS:
            e = self._make(confidence_marker=marker)
            assert e.confidence_marker == marker

    def test_to_dict_has_source_target(self):
        e = self._make()
        d = e.to_dict()
        assert "source_ref" in d
        assert "target_ref" in d

    def test_evidence_refs_tuple(self):
        e = self._make(evidence_refs=["artifact:my-proj.run-01.ev"])
        assert len(e.evidence_refs) == 1


# ---------------------------------------------------------------------------
# ProvenanceRecord
# ---------------------------------------------------------------------------

class TestProvenanceRecord:
    def _make(self, **overrides):
        defaults = dict(
            provenance_ref="provenance:prov-01",
            relation_ref="relation:edge-01",
            assertion_mode="explicit",
            asserted_at=TS,
        )
        defaults.update(overrides)
        return ProvenanceRecord(**defaults)

    def test_minimal_valid(self):
        p = self._make()
        assert p.assertion_mode == "explicit"

    def test_invalid_assertion_mode(self):
        with pytest.raises(ValidationError):
            self._make(assertion_mode="unknown")

    def test_all_assertion_modes(self):
        for mode in ASSERTION_MODES:
            p = self._make(assertion_mode=mode)
            assert p.assertion_mode == mode

    def test_policy_ref_validated(self):
        p = self._make(policy_ref="my.policy.v1")
        assert p.policy_ref == "my.policy.v1"

    def test_invalid_policy_ref_raises(self):
        with pytest.raises(ValidationError):
            self._make(policy_ref="My Policy")

    def test_evidence_bundle_ref_must_be_artifact(self):
        with pytest.raises(ValidationError):
            self._make(evidence_bundle_ref="run:my-proj.run-01")

    def test_evidence_bundle_valid_artifact(self):
        p = self._make(evidence_bundle_ref="artifact:my-proj.run-01.evidence")
        assert p.evidence_bundle_ref == "artifact:my-proj.run-01.evidence"

    def test_to_dict_keys(self):
        p = self._make()
        d = p.to_dict()
        for key in ("provenance_ref", "relation_ref", "assertion_mode", "asserted_at"):
            assert key in d
