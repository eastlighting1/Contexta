# Batch, Sample & Deployment Tracking

This page explains Contexta's three additional execution context types:
Batch, Sample, and Deployment.

These types extend the core Run → Stage hierarchy for workflows that involve
repeated data processing, per-item observation, or model deployment tracking.

## Batch

A batch execution represents one discrete unit of data processing within a stage.

Typical uses:

- one epoch in a training loop
- one chunk in a streaming pipeline
- one file in a batch-import workflow

Batch executions are owned by a stage:

```
Run → Stage → Batch
```

### Ref format

```
batch:{project}.{run}.{stage}.{batch_name}
```

Example: `batch:my-proj.run-01.train.epoch-0`

### Status values

`open` | `completed` | `failed` | `cancelled`

`completed` and `failed` require `ended_at`.

### Logging a batch

```python
from contexta.contract import BatchExecution

batch = BatchExecution(
    batch_execution_ref="batch:my-proj.run-01.train.epoch-0",
    run_ref="run:my-proj.run-01",
    stage_execution_ref="stage:my-proj.run-01.train",
    batch_name="epoch-0",
    status="completed",
    started_at="2025-01-01T00:01:00Z",
    ended_at="2025-01-01T00:02:00Z",
    order_index=0,
)
ctx.metadata_store.batches.put_batch_execution(batch)
```

### Querying batches

```python
batches = ctx.list_batches("run:my-proj.run-01")
for b in batches:
    print(b.name, b.status, b.started_at)
```

---

## Sample

A sample observation records one item seen during a stage or batch.

Typical uses:

- one input row in a validation pass
- one image in a dataset scan
- one prediction in an inference batch

Samples are owned by a stage. The ref must encode the parent stage name and
the sample name as the fourth component:

### Ref format

```
sample:{project}.{run}.{stage}.{sample_name}
```

Example: `sample:my-proj.run-01.train.s-0001`

Note: the 4-component constraint means the sample name must not contain dots.

### Logging a sample

```python
from contexta.contract import SampleObservation

sample = SampleObservation(
    sample_observation_ref="sample:my-proj.run-01.train.s-0001",
    run_ref="run:my-proj.run-01",
    stage_execution_ref="stage:my-proj.run-01.train",
    sample_name="s-0001",
    observed_at="2025-01-01T00:01:30Z",
)
ctx.metadata_store.samples.put_sample_observation(sample)
```

### Querying samples

```python
samples = ctx.list_samples("run:my-proj.run-01")
for s in samples:
    print(s.name, s.observed_at)
```

---

## Deployment

A deployment execution tracks one instance of a model or artifact being
deployed to an environment.

Typical uses:

- a model pushed to a serving endpoint
- a checkpoint promoted to staging
- a trained artifact registered in a model registry

Deployments are scoped to a project and can optionally link to the run that
produced the deployed artifact:

```
Project → Deployment (→ Run, optional)
```

### Ref format

```
deployment:{project}.{deployment_name}
```

Example: `deployment:my-proj.model-v1`

### Logging a deployment

```python
from contexta.contract import DeploymentExecution

deploy = DeploymentExecution(
    deployment_execution_ref="deployment:my-proj.model-v1",
    project_ref="project:my-proj",
    deployment_name="model-v1",
    status="completed",
    started_at="2025-01-01T00:09:00Z",
    ended_at="2025-01-01T00:10:00Z",
    run_ref="run:my-proj.run-01",   # optional link to the producing run
)
ctx.metadata_store.deployments.put_deployment_execution(deploy)
```

### Querying deployments

```python
deployments = ctx.list_deployments("my-proj")
for d in deployments:
    print(d.name, d.status, d.run_id)
```

---

## In snapshot reports

When you call `ctx.build_snapshot_report(run_ref)`, the report automatically
includes **Batches**, **Deployments**, and **Samples** sections when data is present.

```python
report = ctx.build_snapshot_report("run:my-proj.run-01")
for section in report.sections:
    print(section.title)
# → Run Summary, Stages, Artifacts, Batches, Deployments, Samples, Diagnostics, ...
```

---

## Diagnostics

The `DiagnosticsService` checks batch and deployment health automatically:

| Condition | Severity | Issue key |
|---|---|---|
| `BatchExecution.status == "failed"` | `error` | `failed_batch` |
| `BatchExecution` in non-terminal status | `warning` | `incomplete_batch` |
| `DeploymentExecution.status == "failed"` | `error` | `failed_deployment` |

These issues appear in the Diagnostics section of the snapshot report.

---

## Example

See [`examples/batch_sample/batch_sample_demo.py`](../../examples/batch_sample/batch_sample_demo.py)
for a complete runnable example.
