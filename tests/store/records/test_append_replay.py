"""TST-012: append, append_many, scan, replay tests."""

from __future__ import annotations

import pytest

from contexta.common.time import iso_utc_now
from contexta.contract.models.context import Run
from contexta.contract.models.records import (
    MetricPayload,
    MetricRecord,
    RecordEnvelope,
    StructuredEventPayload,
    StructuredEventRecord,
)
from contexta.store.records import RecordStore, ScanFilter, StoreConfig


TS = "2024-01-01T00:00:00Z"
RUN = "run:my-proj.run-01"
STAGE = "stage:my-proj.run-01.train"
BATCH = "batch:my-proj.run-01.train.batch-0"


@pytest.fixture()
def record_store(tmp_path):
    store = RecordStore(StoreConfig(root_path=tmp_path / "records"))
    return store


def _make_event_record(key="test.event", run_ref=RUN, stage_ref=None, batch_ref=None):
    envelope = RecordEnvelope(
        record_ref=f"record:{run_ref.split(':')[1]}.{key.replace('.', '-')}",
        run_ref=run_ref,
        stage_execution_ref=stage_ref,
        batch_execution_ref=batch_ref,
        record_type="event",
        observed_at=TS,
        recorded_at=TS,
        producer_ref="contexta.test",
        completeness_marker="complete",
        degradation_marker="none",
    )
    payload = StructuredEventPayload(event_key=key, level="info", message="test")
    return StructuredEventRecord(envelope=envelope, payload=payload)


def _make_metric_record(key="loss", value=0.5, run_ref=RUN):
    suffix = key.replace(".", "-")
    envelope = RecordEnvelope(
        record_ref=f"record:{run_ref.split(':')[1]}.m-{suffix}",
        run_ref=run_ref,
        record_type="metric",
        observed_at=TS,
        recorded_at=TS,
        producer_ref="contexta.test",
        completeness_marker="complete",
        degradation_marker="none",
    )
    payload = MetricPayload(metric_key=key, value=value, value_type="float", aggregation_scope="run")
    return MetricRecord(envelope=envelope, payload=payload)


# ---------------------------------------------------------------------------
# append / append_many
# ---------------------------------------------------------------------------

class TestAppend:
    def test_append_single_event(self, record_store):
        result = record_store.append(_make_event_record())
        assert len(result.accepted) == 1
        assert len(result.rejected) == 0

    def test_append_many(self, record_store):
        records = [
            _make_event_record("ev.a"),
            _make_metric_record("loss"),
        ]
        # Use unique record refs
        result = record_store.append_many(records)
        assert len(result.accepted) == 2

    def test_append_returns_receipt_with_sequence(self, record_store):
        result = record_store.append(_make_event_record())
        receipt = result.accepted[0]
        assert receipt.sequence >= 1

    def test_append_invalid_type_rejected(self, record_store):
        result = record_store.append_many(["not_a_record"])
        assert len(result.rejected) == 1

    def test_append_partial_acceptance(self, record_store):
        records = [_make_event_record(), "bad_record"]
        result = record_store.append_many(records)
        assert len(result.accepted) == 1
        assert len(result.rejected) == 1


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

class TestScan:
    def test_scan_returns_records(self, record_store):
        record_store.append(_make_event_record("ev.scan"))
        records = list(record_store.scan())
        assert len(records) >= 1

    def test_scan_with_run_filter(self, record_store):
        record_store.append(_make_event_record(run_ref=RUN))
        scan_filter = ScanFilter(run_ref=RUN)
        records = list(record_store.scan(scan_filter))
        assert len(records) >= 1

    def test_scan_with_record_type_filter(self, record_store):
        record_store.append(_make_event_record())
        record_store.append(_make_metric_record())
        scan_filter = ScanFilter(record_type="metric")
        records = list(record_store.scan(scan_filter))
        # All returned records must be metrics
        for rec in records:
            assert rec.record_type == "metric"

    def test_scan_with_batch_filter(self, record_store):
        record_store.append(_make_event_record("ev.batch", stage_ref=STAGE, batch_ref=BATCH))
        record_store.append(_make_event_record("ev.stage", stage_ref=STAGE))
        scan_filter = ScanFilter(batch_execution_ref=BATCH)
        records = list(record_store.scan(scan_filter))
        assert len(records) == 1
        assert records[0].batch_execution_ref == BATCH

    def test_scan_empty_store(self, tmp_path):
        store = RecordStore(StoreConfig(root_path=tmp_path / "empty-records"))
        records = list(store.scan())
        assert records == []


# ---------------------------------------------------------------------------
# replay
# ---------------------------------------------------------------------------

class TestReplay:
    def test_replay_result_has_counts(self, record_store):
        record_store.append(_make_event_record())
        result = record_store.replay()
        assert hasattr(result, "record_count")

    def test_replay_empty_store(self, tmp_path):
        store = RecordStore(StoreConfig(root_path=tmp_path / "empty-replay"))
        result = store.replay()
        assert result is not None

    def test_iter_replay_yields_results(self, record_store):
        record_store.append(_make_event_record("ev.iter"))
        results = list(record_store.iter_replay())
        assert len(results) >= 1
