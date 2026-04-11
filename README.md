<h1 align="center">Contexta</h1>

<p align="center">
  <strong>Local-first observability for ML systems.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-prototype-D97706" alt="prototype status">
  <img src="https://img.shields.io/badge/python-3.14%2B-2563EB" alt="python 3.14+">
  <img src="https://img.shields.io/badge/import-contexta-111827" alt="contexta import">
  <img src="https://img.shields.io/badge/workspace-.contexta-059669" alt=".contexta workspace">
  <img src="https://img.shields.io/badge/focus-local--first-0F766E" alt="local-first">
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> |
  <a href="#product-surface">Product Surface</a> |
  <a href="#documentation-map">Docs Map</a>
</p>

`Contexta` brings the six legacy library roles into one product surface. The intended developer experience is one canonical Python import root, one canonical CLI, one canonical workspace, and one consistent contract for writing, storing, querying, comparing, and recovering observability data.

> [!NOTE]
> `Contexta` is in a prototype-to-product transition. The canonical public identity is already `Contexta` and `contexta`, but some packaging and CLI alignment work is still in progress. This README uses the final product language first and calls out transitional behavior only where it matters.

## Why Contexta

- **One product surface**
  Start from `from contexta import Contexta` instead of stitching together separate package roots.
- **Canonical local workspace**
  Keep metadata, records, artifacts, reports, and recovery state in a local `.contexta/` workspace.
- **Read-oriented investigation**
  Query runs, compare outcomes, inspect diagnostics, follow lineage, and build reports from canonical data.
- **Recovery built in**
  Replay, backup, restore, and artifact transfer are part of the product direction, not separate utilities.

## Quickstart

The shortest fully verified prototype path is:

1. Install the project in editable mode.
2. Run the verified quickstart example.
3. Inspect the generated report and workspace output.

### 1. Install

For local development inside this repository:

```powershell
uv sync --dev
```

Or with `pip`:

```powershell
python -m pip install -e .
```

After installation, the canonical import is:

```python
from contexta import Contexta
```

### 2. Run The Verified Quickstart Example

```powershell
$env:PYTHONPATH = "src"
uv run python examples/quickstart/verified_quickstart.py
```

The example source lives at [`examples/quickstart/verified_quickstart.py`](./examples/quickstart/verified_quickstart.py).

It creates a temporary workspace, writes minimal canonical data, queries the resulting run, and saves a markdown snapshot report.

### 3. What This Confirms

- the `contexta` import path is live
- a canonical `.contexta/` workspace can be created locally
- canonical metadata and records can be written
- the unified facade can query that workspace and build a report
- the quickstart example is executable and regression-covered

## Runtime Capture Preview

The runtime capture surface is already part of the product direction:

```powershell
$env:PYTHONPATH = "src"
uv run python examples/quickstart/runtime_capture_preview.py
```

The preview source lives at [`examples/quickstart/runtime_capture_preview.py`](./examples/quickstart/runtime_capture_preview.py).

The verified README quickstart intentionally uses the currently proven query/report path. The runtime capture preview is included separately so new users can see the scope API without over-promising the current onboarding workflow.

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

The internal namespaces `contexta.api`, `contexta.runtime`, `contexta.common`, and `contexta.surfaces` are not documented as public import targets.

## Documentation Map

The public documentation set is being built in the following structure:

### Core Entry Points

- `README.md`
  - product overview, install, quickstart, migration note
- `docs/index.md`
  - document hub

### User Guide

- `docs/user-guide/index.md`
- `docs/user-guide/key-features.md`
- `docs/user-guide/tools-and-surfaces.md`
- `docs/user-guide/core-concepts.md`
- `docs/user-guide/getting-started.md`
- `docs/user-guide/common-workflows.md`
- `docs/user-guide/advanced.md`
- `docs/user-guide/testing.md`

### Reference

- `docs/reference/api-reference.md`
- `docs/reference/cli-reference.md`
- `docs/reference/http-reference.md`

### Operations And Contribution

- `docs/operations.md`
- `docs/faq.md`
- `CONTRIBUTING.md`

### Examples

- `examples/quickstart/`
  - verified quickstart and runtime capture preview
- `examples/recovery/`
  - operator-oriented recovery workflows

## Design Notes

The product direction is:

- local-first
- schema-first
- reproducibility-oriented
- explicit about degraded or incomplete states

Internally, `Contexta` keeps separate truth-owning planes for:

- metadata and relations
- records
- artifact bodies and bindings

and then builds query/report/recovery surfaces over those planes.

## Current Caveats

- Some prototype-to-release packaging polish is still in progress.
- Source-tree example runs still commonly use `PYTHONPATH=src`.

These are release-alignment issues, not a change in the canonical product identity.
