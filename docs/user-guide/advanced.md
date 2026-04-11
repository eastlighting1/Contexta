# Advanced Contexta Usage

This guide is for users who need to move beyond the root facade and work with configuration, truth planes, interpretation services, or recovery flows directly.

The rule of thumb is:

- use `Contexta` first
- step down only when the facade is not specific enough
- stay inside public namespaces while doing so

## When To Move Beyond The Facade

You usually do not need advanced APIs for basic query, compare, report, or diagnostics flows.

Move beyond the facade when you need:

- explicit config resolution
- direct writes to metadata, record, or artifact planes
- direct replay, verification, or integrity operations
- recovery planning

## Explicit Config Control

The most explicit public config surface is `contexta.config`.

You can build a config directly:

```python
from pathlib import Path

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig

config = UnifiedConfig(
    project_name="advanced-proj",
    workspace=WorkspaceConfig(root_path=Path(".contexta")),
)

ctx = Contexta(config=config)
```

Or resolve config through the loader:

```python
from contexta.config import load_config

resolved = load_config(
    profile="test",
    workspace=".contexta",
    config={"project_name": "advanced-proj"},
)
```

Use explicit config control when you want:

- deterministic onboarding for scripts and tests
- profile-based behavior
- direct config patching without ambient state
- clearer workspace ownership

## Direct Truth-Plane Access

The facade exposes the three persisted truth-owning planes:

- `ctx.metadata_store`
- `ctx.record_store`
- `ctx.artifact_store`

### Metadata Plane

Use the metadata plane when you need direct control over canonical project, run, stage, relation, or provenance writes:

```python
from contexta.contract import Project

project = Project(
    project_ref="project:advanced-proj",
    name="advanced-proj",
    created_at="2024-06-01T12:00:00Z",
)

ctx.metadata_store.projects.put_project(project)
```

### Record Plane

Use the record plane when you need replay, export, or integrity-oriented behavior:

```python
from contexta.store.records import ReplayMode

replay = ctx.record_store.replay(mode=ReplayMode.TOLERANT)
print(replay.record_count)
print(replay.integrity_state.value)
```

### Artifact Plane

Use the artifact plane when you need verification or store-level inspection:

```python
summary = ctx.artifact_store.inspect_store()
print(summary.artifact_count)
print(summary.verified_count)
```

Move to these plane APIs only when the task is truly plane-specific. For most read workflows, the facade remains the better entry point.

## Direct Interpretation Services

If you already have a `Contexta` instance, the most natural advanced path is to use the lazily constructed services behind it:

- `ctx.query_service`
- `ctx.compare_service`
- `ctx.diagnostics_service`
- `ctx.lineage_service`
- `ctx.trend_service`
- `ctx.alert_service`
- `ctx.provenance_service`
- `ctx.report_builder`

For example:

```python
query_service = ctx.query_service
compare_service = ctx.compare_service

snapshot = query_service.get_run_snapshot("run:advanced-proj.demo-run")
comparison = compare_service.compare_runs(
    "run:advanced-proj.demo-run",
    "run:advanced-proj.demo-run-v2",
)
```

This is useful when you want service-level control without rebuilding the store and repository graph yourself.

## Recovery Workflows

Recovery belongs in the product, not in ad-hoc shell scripts.

### Backup Planning And Creation

```python
from contexta.recovery import create_workspace_backup, plan_workspace_backup

plan = plan_workspace_backup(ctx.config, label="manual")
result = create_workspace_backup(ctx.config, plan)

print(result.backup_ref)
print(result.location)
```

Executable example:

- [Recovery backup/restore example](../../examples/recovery/backup_restore_verify.py)

### Restore Planning

```python
from contexta.recovery import plan_restore, restore_workspace

restore_plan = plan_restore(
    ctx.config,
    result.backup_ref,
    verify_only=True,
)
restore_check = restore_workspace(ctx.config, restore_plan)

print(restore_check.status)
print(restore_check.verification_notes)
```

Executable examples:

- [Recovery outbox replay example](../../examples/recovery/replay_outbox_demo.py)
- [Recovery artifact transfer example](../../examples/recovery/artifact_transfer_demo.py)

Use the recovery package when you need:

- backup or restore planning
- outbox replay

## Public Boundaries To Respect

Safe public targets:

- `contexta`
- `contexta.config`
- `contexta.contract`
- `contexta.capture`
- `contexta.store.metadata`
- `contexta.store.records`
- `contexta.store.artifacts`
- `contexta.interpretation`
- `contexta.recovery`

Do not build new code against these internal namespaces:

- `contexta.api`
- `contexta.runtime`
- `contexta.common`
- `contexta.surfaces`

Those modules exist in the repository, but they are not the public contract we want users or contributors to anchor on.

## Prototype Caveats

At the current prototype stage:

- source-tree scripts still need `PYTHONPATH=src` in a local checkout unless packaging is handled externally

These are transition details, not the intended long-term product identity.

## Where To Go Next

Continue with:

- [Testing Guide](./testing.md)
- API, CLI, and HTTP references once they are written
