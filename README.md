<h1 align="center">Contexta</h1>

<p align="center">
  <strong>Local-first observability for ML systems & Harness Engineering.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/contexta/"><img src="https://img.shields.io/pypi/v/contexta" alt="PyPI version"></a>
  <img src="https://img.shields.io/pypi/pyversions/contexta" alt="Python versions">
  <img src="https://img.shields.io/badge/status-alpha-D97706" alt="alpha">
  <img src="https://img.shields.io/badge/focus-local--first-0F766E" alt="local-first">
</p>

<p align="center">
  <a href="https://github.com/eastlighting1/Contexta/actions/workflows/ci.yml"><img src="https://github.com/eastlighting1/Contexta/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/eastlighting1/Contexta/actions/workflows/test-matrix.yml"><img src="https://github.com/eastlighting1/Contexta/actions/workflows/test-matrix.yml/badge.svg" alt="Test Matrix"></a>
  <a href="https://github.com/eastlighting1/Contexta/actions/workflows/examples.yml"><img src="https://github.com/eastlighting1/Contexta/actions/workflows/examples.yml/badge.svg" alt="Docs and Examples"></a>
  <a href="https://github.com/eastlighting1/Contexta/actions/workflows/packaging.yml"><img src="https://github.com/eastlighting1/Contexta/actions/workflows/packaging.yml/badge.svg" alt="Packaging"></a>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> |
  <a href="#product-surface">Product Surface</a> |
  <a href="#documentation-map">Docs Map</a>
</p>

`Contexta` is a local-first ML observability library. It provides one canonical import root, one canonical CLI, one canonical workspace, and one consistent contract for writing, storing, querying, comparing, and recovering observability data — without a cloud backend. 
It is designed as the perfect infrastructure for both human engineers and autonomous AI coding agents — MUST-HAVE for Harness Engineering.

## Why Contexta

- **One product surface**
  Start from `from contexta import Contexta` instead of stitching together separate tools.
- **Canonical local workspace (Agent-Ready)**
  Keep metadata, records, artifacts, reports, and recovery state in a local `.contexta/` workspace—perfectly isolated for autonomous agent worktrees and context resets.
- **Read-oriented investigation & Evaluator Loops**
  Query runs, compare outcomes, inspect diagnostics, follow lineage, and build reports from canonical data. Structured specifically to support QA agents and Generator-Evaluator loops.
- **Recovery built in**
  Replay, backup, restore, and artifact transfer are first-class features, not separate utilities.
- **Framework-agnostic**
  Works alongside scikit-learn, PyTorch, HuggingFace Transformers, vLLM, or any other ML stack.

## Quickstart

### Install

```bash
pip install contexta
```

or with `uv`:

```bash
uv add contexta
```

### Run your first example

The fastest way to see Contexta in action is the sklearn tabular example — no GPU required:

```bash
pip install contexta "scikit-learn>=1.6"
uv run python examples/quickstart/qs01_sklearn_tabular.py
```

This trains an SVM and a Random Forest on the UCI Wine dataset, logs CV fold metrics and evaluation metrics to a local `.contexta/` workspace, then compares the two runs and registers the best model as a deployment.

For deep learning and LLM examples see [`examples/quickstart/`](./examples/quickstart/README.md).

### Minimal usage

```python
from datetime import datetime, timezone
from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    Project, Run, StageExecution,
    MetricPayload, MetricRecord, RecordEnvelope,
)

ctx = Contexta(config=UnifiedConfig(
    project_name="my-project",
    workspace=WorkspaceConfig(root_path=".contexta"),
))
store = ctx.metadata_store

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

store.projects.put_project(Project(project_ref="project:my-project", name="my-project", created_at=now))
store.runs.put_run(Run(run_ref="run:my-project.run-01", project_ref="project:my-project",
                       name="run-01", status="completed", started_at=now, ended_at=now))

ctx.record_store.append(MetricRecord(
    envelope=RecordEnvelope(
        record_ref="record:my-project.run-01.r00001", record_type="metric",
        recorded_at=now, observed_at=now, producer_ref="my-script",
        run_ref="run:my-project.run-01",
        completeness_marker="complete", degradation_marker="none",
    ),
    payload=MetricPayload(metric_key="accuracy", value=0.95, value_type="float64"),
))

snapshot = ctx.get_run_snapshot("run:my-project.run-01")
report   = ctx.build_snapshot_report("run:my-project.run-01")
print(report.title)

store.close()
```

## Optional dependencies

Contexta's core runtime only requires `duckdb`. Install framework extras only for what you use:

```bash
pip install "contexta[sklearn]"       # + scikit-learn
pip install "contexta[torch]"         # + PyTorch
pip install "contexta[transformers]"  # + HuggingFace Transformers + PyTorch
pip install "contexta[all-integrations]"  # all of the above
```

## Product Surface

| Surface | Status | Role | When To Start Here |
| --- | --- | --- | --- |
| `Contexta` | Stable | Unified facade | Default starting point |
| `contexta.config` | Stable | Config models, profiles, env overrides | When you need explicit config control |
| `contexta.contract` | Stable | Canonical models, validation, serialization | When you work directly with schema-level types |
| `contexta.capture` | Stable | Runtime capture scopes and emissions | When facade-level capture is not enough |
| `contexta.store.metadata` | Stable | Metadata truth plane | Advanced store access |
| `contexta.store.records` | Stable | Record truth plane | Replay, scan, export, integrity workflows |
| `contexta.store.artifacts` | Stable | Artifact truth plane | Artifact ingest, verify, export, import |
| `contexta.interpretation` | Stable | Query, compare, diagnostics, lineage, reports | Read and investigation flows |
| `contexta.recovery` | Advanced | Replay, backup, restore | Operator and recovery work |

The internal namespaces `contexta.api`, `contexta.runtime`, `contexta.common`, and `contexta.surfaces` are not public API targets.

## Documentation Map

### Core Entry Points

- `README.md` — product overview, install, quickstart
- `docs/index.md` — document hub

### User Guide

- `docs/user-guide/getting-started.md`
- `docs/user-guide/key-features.md`
- `docs/user-guide/tools-and-surfaces.md`
- `docs/user-guide/core-concepts.md`
- `docs/user-guide/common-workflows.md`
- `docs/user-guide/advanced.md`
- `docs/user-guide/case-studies.md`

### Reference

- `docs/reference/api-reference.md`
- `docs/reference/cli-reference.md`

### Operations And Contribution

- `docs/operations.md`
- `docs/faq.md`
- `CONTRIBUTING.md`
- `SECURITY.md`

### Examples

- `examples/quickstart/` — qs01 (sklearn), qs02 (PyTorch CNN), qs03 (BERT), qs04 (vLLM RAG)
- `examples/case_studies/` — 12 real-world observability scenarios
- `examples/recovery/` — operator-oriented recovery workflows

## Design Notes

- local-first: all data stays on your machine
- schema-first: every record follows a canonical contract
- reproducibility-oriented: environment snapshots and provenance are first-class
- explicit about degraded or incomplete states

Internally, Contexta separates truth-owning planes for metadata, records, and artifact bodies, then builds query, report, and recovery surfaces over those planes.
