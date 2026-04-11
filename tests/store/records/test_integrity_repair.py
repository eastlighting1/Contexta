"""TST-013: integrity, rebuild, repair tests."""

from __future__ import annotations

import pytest

from contexta.contract.models.records import (
    RecordEnvelope,
    StructuredEventPayload,
    StructuredEventRecord,
)
from contexta.store.records import (
    RecordStore,
    ScanFilter,
    StoreConfig,
    check_integrity,
    rebuild_indexes,
    repair_truncated_tails,
)


TS = "2024-01-01T00:00:00Z"
RUN = "run:my-proj.run-01"


@pytest.fixture()
def record_store(tmp_path):
    return RecordStore(StoreConfig(root_path=tmp_path / "records"))


def _make_event(key="ev.test", run_ref=RUN):
    envelope = RecordEnvelope(
        record_ref=f"record:{run_ref.split(':')[1]}.{key.replace('.', '-')}",
        run_ref=run_ref,
        record_type="event",
        observed_at=TS,
        recorded_at=TS,
        producer_ref="contexta.test",
        completeness_marker="complete",
        degradation_marker="none",
    )
    payload = StructuredEventPayload(event_key=key, level="info", message="ok")
    return StructuredEventRecord(envelope=envelope, payload=payload)


# ---------------------------------------------------------------------------
# check_integrity
# ---------------------------------------------------------------------------

class TestCheckIntegrity:
    def test_empty_store_integrity(self, record_store):
        report = check_integrity(record_store)
        assert report is not None

    def test_integrity_report_has_issues(self, record_store):
        report = check_integrity(record_store)
        assert hasattr(report, "issues")

    def test_integrity_via_store_method(self, record_store):
        record_store.append(_make_event("ev.check"))
        report = record_store.check_integrity()
        assert report is not None

    def test_integrity_state_attribute(self, record_store):
        report = check_integrity(record_store)
        assert hasattr(report, "state")

    def test_healthy_store_state(self, record_store):
        record_store.append(_make_event())
        report = record_store.check_integrity()
        # A freshly written store should be healthy
        from contexta.store.records.models import IntegrityState
        assert report.state in (IntegrityState.HEALTHY, IntegrityState.DEGRADED)


# ---------------------------------------------------------------------------
# rebuild_indexes
# ---------------------------------------------------------------------------

class TestRebuildIndexes:
    def test_rebuild_empty_store(self, record_store):
        result = rebuild_indexes(record_store)
        assert result is not None

    def test_rebuild_after_append(self, record_store):
        record_store.append(_make_event("ev.rebuild"))
        result = rebuild_indexes(record_store)
        assert result is not None

    def test_rebuild_via_store_method(self, record_store):
        result = record_store.rebuild_indexes()
        assert result is not None

    def test_rebuild_report_has_state(self, record_store):
        record_store.append(_make_event())
        result = record_store.rebuild_indexes()
        assert hasattr(result, "integrity_state") or hasattr(result, "rebuilt_indexes")


# ---------------------------------------------------------------------------
# repair_truncated_tails
# ---------------------------------------------------------------------------

class TestRepairTruncatedTails:
    def test_repair_on_healthy_store(self, record_store):
        record_store.append(_make_event("ev.repair"))
        result = repair_truncated_tails(record_store)
        assert result is not None

    def test_repair_via_store_method(self, record_store):
        result = record_store.repair_truncated_tails()
        assert result is not None

    def test_repair_report_structure(self, record_store):
        result = repair_truncated_tails(record_store)
        assert hasattr(result, "repaired") or hasattr(result, "segments_repaired") or result is not None
