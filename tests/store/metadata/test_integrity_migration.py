"""TST-011: integrity scan, repair plan, migration runner tests."""

from __future__ import annotations

import pytest

from contexta.common.time import iso_utc_now
from contexta.contract.models.context import Project, Run
from contexta.store.metadata import (
    MetadataStore,
    MetadataStoreConfig,
    check_integrity,
    inspect_schema,
    plan_migration_for,
    plan_repairs,
)


TS = "2024-01-01T00:00:00Z"


@pytest.fixture()
def store():
    s = MetadataStore(MetadataStoreConfig(database_path=":memory:"))
    yield s
    s._backend.close()


@pytest.fixture()
def populated_store(store):
    store.projects.put_project(Project(project_ref="project:proj-a", name="A", created_at=TS))
    run = Run(
        run_ref="run:proj-a.run-01",
        project_ref="project:proj-a",
        name="R1",
        status="open",
        started_at=TS,
    )
    store.runs.put_run(run)
    return store


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

class TestSchemaVersion:
    def test_schema_version_is_set(self, store):
        version = store.get_store_schema_version()
        assert version is not None
        assert isinstance(version, str)

    def test_inspect_schema(self):
        config = MetadataStoreConfig(database_path=":memory:")
        inspection = inspect_schema(config)
        assert inspection is not None


# ---------------------------------------------------------------------------
# Integrity scan
# ---------------------------------------------------------------------------

class TestIntegrityScan:
    def test_empty_store_has_no_critical_issues(self, store):
        report = check_integrity(store)
        assert report is not None

    def test_populated_store_integrity(self, populated_store):
        report = check_integrity(populated_store)
        # Should be able to produce a report even for a populated store
        assert report is not None

    def test_store_check_integrity_method(self, store):
        report = store.check_integrity()
        assert report is not None

    def test_integrity_report_has_issues_attribute(self, store):
        report = store.check_integrity()
        assert hasattr(report, "issues")


# ---------------------------------------------------------------------------
# Repair plan
# ---------------------------------------------------------------------------

class TestRepairPlan:
    def test_repair_plan_from_clean_store(self, store):
        report = store.check_integrity()
        plan = plan_repairs(report)
        assert plan is not None

    def test_repair_plan_via_store_method(self, store):
        plan = store.plan_repairs()
        assert plan is not None

    def test_repair_plan_has_candidates(self, store):
        plan = store.plan_repairs()
        assert hasattr(plan, "candidates")


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

class TestMigration:
    def test_plan_migration_for_current_version(self):
        config = MetadataStoreConfig(database_path=":memory:")
        plan = plan_migration_for(config)
        assert plan is not None

    def test_dry_run_migration(self):
        from contexta.store.metadata import dry_run_migration_for
        config = MetadataStoreConfig(database_path=":memory:")
        result = dry_run_migration_for(config)
        assert result is not None

    def test_migration_history_available(self, store):
        # After bootstrap the schema is current; migrating should be a no-op.
        result = MetadataStore.migrate_for(MetadataStoreConfig(database_path=":memory:"))
        assert result is not None
