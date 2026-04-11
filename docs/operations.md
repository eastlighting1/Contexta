# Contexta Operations Guide

This guide is for operators and advanced users working with recovery-oriented `Contexta` workflows.

The current public operations surface is centered on:

- workspace backup
- restore planning and verify-only checks
- outbox replay
- artifact verification and transfer

At the current prototype stage, the most reliable operator paths are the public Python APIs in `contexta.recovery` and the executable examples in [`examples/recovery/`](../examples/recovery/README.md).

## Start Here

If you are new to the recovery surface, use these in order:

1. [Advanced Usage](./user-guide/advanced.md)
2. [Recovery Examples](../examples/recovery/README.md)
3. [CLI Reference](./reference/cli-reference.md)

That path keeps the operational guidance attached to executable examples and current command behavior.

## Core Principles

- Prefer planning before applying.
- Prefer verify-only restore before destructive restore.
- Keep recovery work inside one explicit workspace.
- Use public recovery APIs and examples instead of reaching into internal modules.

## Backup

The current public backup workflow is:

```python
from contexta.recovery import create_workspace_backup, plan_workspace_backup

plan = plan_workspace_backup(config, label="manual")
result = create_workspace_backup(config, plan)
```

What this gives you:

- a stable backup reference
- a backup directory under the configured recovery root
- a manifest describing included sections

Current operational notes:

- cache and exports are excluded by default unless explicitly included
- backup output is workspace-oriented, not a remote snapshot service
- the backup helper is safe to use as a pre-change checkpoint before more invasive work

Executable example:

- [Backup and verify-only restore example](../examples/recovery/backup_restore_verify.py)

## Restore

The safest current restore posture is verify-only:

```python
from contexta.recovery import plan_restore, restore_workspace

restore_plan = plan_restore(config, backup_ref, verify_only=True)
restore_result = restore_workspace(config, restore_plan)
```

Use verify-only when you want to confirm:

- the backup manifest is readable
- the staged workspace can be materialized
- metadata, records, and artifacts pass the current verification path

Current operational notes:

- verify-only does not overwrite the target workspace
- non-verify restore can replace the target workspace contents
- if later enabled by config, restore may create a safety backup before applying

## Replay

Replay is for recovery-outbox processing, not for ordinary query workflows.

The public entrypoint is:

```python
from contexta.recovery import replay_outbox

result = replay_outbox(config)
```

Use replay when you need to:

- retry failed sink deliveries
- inspect acknowledged, pending, and dead-lettered counts
- move failed payloads into a replay target sink

Current operational notes:

- replay requires `config.recovery.outbox_root`
- the default replay sink writes under the workspace exports area
- replay is a recovery action, so run it intentionally rather than as a hidden side effect

Executable example:

- [Replay outbox example](../examples/recovery/replay_outbox_demo.py)

## Artifact Verification And Transfer

Artifact transfer is currently best handled through the artifact store public surface rather than a top-level recovery facade.

Useful current operations:

- `inspect_store(...)`
- `verify_artifact(...)`
- `verify_all(...)`
- `export_artifact(...)`
- `import_export_package(...)`

Use these when you need to:

- verify stored artifact bodies
- export a self-describing package
- import that package into another store root

Executable example:

- [Artifact transfer example](../examples/recovery/artifact_transfer_demo.py)

## Safety Checklist

Before a risky recovery action:

- confirm the target workspace path
- create a fresh backup if data matters
- prefer verify-only restore first
- inspect warnings, loss notes, and verification notes instead of ignoring them

## Command-Line Notes

The embedded CLI already exposes a small maintenance surface:

- `contexta backup create`
- `contexta restore apply`
- `contexta recover replay`

At the current prototype stage:

- public docs use canonical `contexta` naming
- the Python APIs and executable examples remain the clearest current operator contract

See:

- [CLI Reference](./reference/cli-reference.md)

## Validation

If you change operational docs or examples, rerun:

```powershell
uv run pytest tests/e2e/test_recovery_examples.py -q
```

If your change also touches replay behavior or restore logic, expand validation with the nearest recovery suites from the [Testing Guide](./user-guide/testing.md).
