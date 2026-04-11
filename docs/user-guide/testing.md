# Contexta Testing Guide

This guide explains how to validate `Contexta` workflows during the current prototype stage.

The key idea is simple:

- test semantics first
- use the smallest suite that proves the change
- keep examples tied to real execution, not only prose

## Current Test Runner

The project uses `pytest`.

For repository-based test runs, `pytest` already receives `src/` through the project configuration, so the usual commands work without manually setting `PYTHONPATH`.

That is different from ad-hoc scripts in a local checkout, where `PYTHONPATH=src` is still the safest current path.

## Useful Commands

### Full Suite

```powershell
uv run pytest -q
```

Use this when you want the broadest confidence before a larger merge or release step.

### Core End-To-End Flow

```powershell
uv run pytest tests/e2e/test_capture_to_report.py -q
```

Use this when your change affects:

- core onboarding
- query/report behavior
- facade-level read workflows

### Quickstart Example Validation

```powershell
uv run pytest tests/e2e/test_quickstart_examples.py -q
```

Use this when your change affects:

- `README.md` quickstart guidance
- `docs/user-guide/getting-started.md`
- `examples/quickstart/`
- the public onboarding path for new users

### Recovery Example Validation

```powershell
uv run pytest tests/e2e/test_recovery_examples.py -q
```

Use this when your change affects:

- `examples/recovery/`
- backup, replay, or artifact transfer examples
- operator-facing recovery onboarding

## What The Current Evidence Covers

The strongest workflow-level evidence in the repository today comes from:

- `tests/e2e/test_capture_to_report.py`
- `tests/e2e/test_quickstart_examples.py`
- `tests/e2e/test_recovery_examples.py`

Together, these cover:

- facade lifecycle and read flows
- query, compare, diagnostics, and report behavior
- quickstart example validation
- recovery example validation

## Layered Testing Model

The documentation and design baseline describe the test story in layers.

### Unit

Use unit tests for:

- helper functions
- serializers and deserializers
- small validation and parsing rules

### Contract

Use contract tests for canonical model validation, deterministic serialization, and stable result shapes.

### Plane Integration

Use plane integration tests for:

- metadata store behavior
- record append and replay
- artifact ingest and verification

### Recovery

Use recovery and migration tests for:

- replay behavior
- backup and restore

### Surface

Use surface tests for:

- Python facade behavior
- CLI behavior
- HTTP JSON behavior
- HTML UI behavior

### End-To-End

Use end-to-end tests when you want confidence that a user journey still works across multiple layers at once.

## How To Validate Documentation Changes

Documentation should stay attached to executable reality.

If you change:

- getting-started examples
  - rerun the onboarding script or the nearest e2e flow
- common query or report guidance
  - rerun the core e2e flow
- recovery guidance
  - rerun recovery example coverage or the nearest recovery suite

For doc-heavy changes, the goal is not to rerun everything blindly. The goal is to rerun the closest proof that the guidance is still true.

## What To Assert

Prefer semantic assertions over formatting-sensitive assertions.

Good assertions:

- a run snapshot contains the expected run id, stages, and records
- a comparison exposes the expected metric or stage differences
- a report has the expected title and sections

Weaker assertions:

- exact incidental ordering when ordering is not part of the contract
- large brittle string snapshots for outputs that are still evolving quickly

## Example Validation Expectations

Examples in public docs should prove at least one of these:

- canonical import paths work
- a workspace can be created and read
- a run can be queried
- a report can be built

Examples should not silently depend on internal modules or private helper paths.

## Prototype Notes

At the current prototype stage:

- the source-tree script story still relies on `PYTHONPATH=src`
- the package and CLI names are aligned as `contexta`

That is why the testing guide emphasizes executable repository commands and file-scoped test suites rather than a polished install-and-run-from-anywhere story.

## Where To Go Next

Continue with:

- [Common Workflows](./common-workflows.md)
- [Advanced Usage](./advanced.md)
