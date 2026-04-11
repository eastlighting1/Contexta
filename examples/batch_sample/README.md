# Batch, Sample & Deployment Examples

This directory demonstrates Contexta's Batch, Sample, and Deployment tracking.

## batch_sample_demo.py

Shows the full lifecycle:

1. Create a project / run / stage
2. Log two batch executions (epoch-0, epoch-1) each with 3 sample observations
3. Register a deployment execution linked to the run
4. Query via `ctx.list_batches()`, `ctx.list_samples()`, `ctx.list_deployments()`
5. Build a snapshot report — confirms Batches, Deployments, and Samples sections appear

No extra packages required (stdlib + contexta only).

```powershell
uv run python examples/batch_sample/batch_sample_demo.py
```

Expected output:

```
Workspace:           C:\...\contexta-batch-XXXX\.contexta
Run ref:             run:batch-demo.run-01
Batches logged:      2
Samples logged:      6
Deployments:         1
Snapshot batches:    2
Snapshot deploys:    1
Report sections:     Run Summary, Stages, Artifacts, Batches, Deployments, Samples, Diagnostics, Completeness Notes
```

## Key concepts

| Contexta type | Ref format | Notes |
|---|---|---|
| `BatchExecution` | `batch:{project}.{run}.{stage}.{name}` | 4-component ref |
| `SampleObservation` | `sample:{project}.{run}.{stage}.{name}` | owned by stage (4-component) |
| `DeploymentExecution` | `deployment:{project}.{name}` | linked to run via `run_ref` |

Status values for all three: `open`, `completed`, `failed`, `cancelled`.
`completed` and `failed` require `ended_at`.
