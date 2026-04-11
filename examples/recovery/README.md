# Contexta Recovery Examples

This directory holds executable operator-oriented examples for `Contexta`.

The examples focus on the recovery and maintenance flows that are already available through the current public Python surface:

- workspace backup and verify-only restore
- outbox replay
- artifact export/import package flow

Run examples from the repository root with:

```powershell
$env:PYTHONPATH = "src"
uv run python examples/recovery/<script>.py
```

## Example Set

### Backup And Verify-Only Restore

[`backup_restore_verify.py`](./backup_restore_verify.py)

Use this when you want to:

- create a workspace backup under the configured recovery root
- inspect the generated backup reference
- verify a restore plan without overwriting the target workspace

### Replay Outbox

[`replay_outbox_demo.py`](./replay_outbox_demo.py)

Use this when you want to:

- simulate a failed delivery in the recovery outbox
- replay that entry into the default replay sink
- confirm acknowledged and pending counts

### Artifact Export And Import Package

[`artifact_transfer_demo.py`](./artifact_transfer_demo.py)

Use this when you want to:

- register one artifact into a source artifact store
- export that artifact as a self-describing package
- import the package into a second artifact store

## Validation

The example set is regression-covered by:

```powershell
uv run pytest tests/e2e/test_recovery_examples.py -q
```

That suite validates the current public recovery-example scripts rather than treating them as prose-only samples.
