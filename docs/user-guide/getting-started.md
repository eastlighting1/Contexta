# Getting Started With Contexta

This guide walks you from installation to your first logged ML run.

## Before You Start

You need:

- Python `>=3.14`
- A local filesystem where `.contexta/` can be created

No cloud account, no API key, no additional infrastructure required.

## Step 1: Install

```bash
pip install contexta
```

or with `uv`:

```bash
uv add contexta
```

For ML framework extras, install only what you use:

```bash
pip install "contexta[sklearn]"       # scikit-learn
pip install "contexta[torch]"         # PyTorch
pip install "contexta[transformers]"  # HuggingFace Transformers
```

### Development install (from source)

If you are contributing to Contexta or want to run the examples against the
working tree:

```bash
git clone https://github.com/eastlighting1/Contexta.git
cd Contexta
uv sync --dev
```

## Step 2: Run the Quickstart Example

The fastest end-to-end example needs only `contexta` and `scikit-learn`:

```bash
pip install "contexta[sklearn]"
python examples/quickstart/qs01_sklearn_tabular.py
```

The script:

1. Loads the UCI Wine dataset and splits it into train / test sets.
2. Trains an SVM baseline and a Random Forest, logging 5-fold CV metrics and evaluation metrics to a local `.contexta/` workspace as each run completes.
3. Compares the two runs with `compare_runs`, picks the winner with `select_best_run`, and registers it as a deployment.
4. Runs `diagnose_run` and `build_snapshot_report` on the best run.

After it finishes, the workspace lives at `examples/quickstart/.contexta/wine-quality-clf/`.

## Step 3: Understand The Core Concepts

Contexta organises observability data into three truth planes:

| Plane | What it stores |
|-------|----------------|
| Metadata | Projects, Runs, Stages, Environments, Deployments, Samples |
| Records | MetricRecord, StructuredEventRecord, DegradedRecord, … |
| Artifacts | Model files, dataset snapshots, any binary blob |

Everything is addressed by a **canonical ref** string:

```
project:{name}
run:{project}.{run}
stage:{project}.{run}.{stage}
record:{project}.{run}.{id}
environment:{project}.{run}.{snap}
deployment:{project}.{deploy}
```

## Step 4: Write Your First Run

```python
from datetime import datetime, timezone
from pathlib import Path
from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    Project, Run, StageExecution,
    MetricPayload, MetricRecord, RecordEnvelope,
)

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

ctx = Contexta(config=UnifiedConfig(
    project_name="my-project",
    workspace=WorkspaceConfig(root_path=Path(".contexta")),
))
store = ctx.metadata_store

# Register project and run
store.projects.put_project(
    Project(project_ref="project:my-project", name="my-project", created_at=now())
)
run_start = now()
store.runs.put_run(
    Run(run_ref="run:my-project.run-01", project_ref="project:my-project",
        name="run-01", status="open", started_at=run_start, ended_at=None)
)

# Register a stage
store.stages.put_stage_execution(
    StageExecution(stage_execution_ref="stage:my-project.run-01.train",
                   run_ref="run:my-project.run-01", stage_name="train",
                   status="completed", started_at=run_start, ended_at=now(), order_index=0)
)

# Log a metric
ts = now()
ctx.record_store.append(MetricRecord(
    envelope=RecordEnvelope(
        record_ref="record:my-project.run-01.r00001", record_type="metric",
        recorded_at=ts, observed_at=ts, producer_ref="getting-started",
        run_ref="run:my-project.run-01",
        stage_execution_ref="stage:my-project.run-01.train",
        completeness_marker="complete", degradation_marker="none",
    ),
    payload=MetricPayload(metric_key="accuracy", value=0.95, value_type="float64"),
))

# Close the run
store.runs.put_run(
    Run(run_ref="run:my-project.run-01", project_ref="project:my-project",
        name="run-01", status="completed", started_at=run_start, ended_at=now())
)

store.close()
```

## Step 5: Query And Report

```python
snapshot = ctx.get_run_snapshot("run:my-project.run-01")
for rec in snapshot.records:
    print(rec.key, rec.value)

report = ctx.build_snapshot_report("run:my-project.run-01")
print(report.title)
for section in report.sections:
    print(" -", section.title)
```

## Common Questions

### Do I need to set PYTHONPATH?

No. `pip install contexta` or `uv add contexta` puts the package on your
Python path normally. `PYTHONPATH=src` is only needed if you run scripts
directly against the repository source tree without installing.

### Do I need a cloud account or API key?

No. Contexta is fully local. The `.contexta/` workspace is a directory on
your filesystem.

### What is the canonical ref format?

See [Core Concepts](./core-concepts.md) for the full ref grammar.

## Where To Go Next

- [Key Features](./key-features.md)
- [Tools and Surfaces](./tools-and-surfaces.md)
- [Core Concepts](./core-concepts.md)
- [Common Workflows](./common-workflows.md)
- [Case Studies](./case-studies.md)
- [`examples/quickstart/`](../../examples/quickstart/README.md)
- [`examples/case_studies/`](../../examples/case_studies/README.md)
