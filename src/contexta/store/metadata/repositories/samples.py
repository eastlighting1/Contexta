"""Sample repository for metadata persistence."""

from __future__ import annotations

from ....common.errors import NotFoundError
from ....contract import SampleObservation, deserialize_sample_observation
from ._base import BaseRepository, normalize_ref_text


class SampleRepository(BaseRepository):
    table_name = "sample_observations"

    def put_sample_observation(self, sample: SampleObservation) -> SampleObservation:
        self.store._ensure_writable()
        if not self.store.runs.exists_run(str(sample.run_ref)):
            raise NotFoundError(
                "Sample owner run does not exist.",
                code="metadata_missing_sample_run",
                details={"run_ref": str(sample.run_ref), "sample_ref": str(sample.sample_observation_ref)},
            )
        if not self.store.stages.exists_stage_execution(str(sample.stage_execution_ref)):
            raise NotFoundError(
                "Sample owner stage does not exist.",
                code="metadata_missing_sample_stage",
                details={"stage_ref": str(sample.stage_execution_ref), "sample_ref": str(sample.sample_observation_ref)},
            )
        if sample.batch_execution_ref is not None and not self.store.batches.exists_batch_execution(str(sample.batch_execution_ref)):
            raise NotFoundError(
                "Sample owner batch does not exist.",
                code="metadata_missing_sample_batch",
                details={"batch_ref": str(sample.batch_execution_ref), "sample_ref": str(sample.sample_observation_ref)},
            )
        payload_json = self._serialize(sample)
        self._backend.upsert_payload_row(
            self.table_name,
            payload_json=payload_json,
            values={
                "ref": str(sample.sample_observation_ref),
                "run_ref": str(sample.run_ref),
                "stage_ref": str(sample.stage_execution_ref),
                "batch_ref": None if sample.batch_execution_ref is None else str(sample.batch_execution_ref),
                "sample_name": sample.sample_name,
                "observed_at": sample.observed_at,
                "retention_class": sample.retention_class,
                "redaction_profile": sample.redaction_profile,
            },
        )
        self.store._register_refs(((str(sample.sample_observation_ref), "sample", "sample_observation"),))
        return sample

    def get_sample_observation(self, ref: str) -> SampleObservation:
        return self._fetch_one_payload(ref, deserializer=deserialize_sample_observation, entity_name="SampleObservation")

    def find_sample_observation(self, ref: str) -> SampleObservation | None:
        return self._find_one_payload(ref, deserializer=deserialize_sample_observation)

    def exists_sample_observation(self, ref: str) -> bool:
        return self._exists(ref)

    def list_sample_observations(
        self,
        *,
        run_ref: str | None = None,
        stage_ref: str | None = None,
        batch_ref: str | None = None,
    ) -> tuple[SampleObservation, ...]:
        if batch_ref is not None:
            return self._list_payloads(
                deserializer=deserialize_sample_observation,
                where="batch_ref = ?",
                params=(normalize_ref_text(batch_ref, expected_kind="batch"),),
                order_by="observed_at, ref",
            )
        if stage_ref is not None:
            return self._list_payloads(
                deserializer=deserialize_sample_observation,
                where="stage_ref = ?",
                params=(normalize_ref_text(stage_ref, expected_kind="stage"),),
                order_by="batch_ref, observed_at, ref",
            )
        if run_ref is not None:
            return self._list_payloads(
                deserializer=deserialize_sample_observation,
                where="run_ref = ?",
                params=(normalize_ref_text(run_ref, expected_kind="run"),),
                order_by="stage_ref, batch_ref, observed_at, ref",
            )
        return self._list_payloads(
            deserializer=deserialize_sample_observation,
            order_by="run_ref, stage_ref, batch_ref, observed_at, ref",
        )


__all__ = ["SampleRepository"]
