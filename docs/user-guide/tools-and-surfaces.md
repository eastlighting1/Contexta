# Contexta Tools And Surfaces

This page explains how the `Contexta` product surface is organized and where new users should start.

The most important rule is simple:

- start with `Contexta`
- move to sub-namespaces only when you need more control

## Start Here

If you are new to the product, start here:

```python
from contexta import Contexta
```

The root facade is the default public entry point.

## Surface Categories

`Contexta` documentation uses three labels:

- `Stable`
  - recommended public contract
- `Advanced`
  - public, but mainly for operator or power-user flows
- `Internal`
  - implementation detail, not a public import target

## Public Surface Map

| Surface | Status | Use It For | Start Here? |
| --- | --- | --- | --- |
| `Contexta` | Stable | unified facade for core product flows | Yes |
| `contexta.config` | Stable | config models, profiles, env overrides | Sometimes |
| `contexta.contract` | Stable | canonical models, validation, serialization | Usually no |
| `contexta.capture` | Stable | runtime scopes, emissions, capture helpers | Sometimes |
| `contexta.store.metadata` | Stable | metadata truth plane access | Usually no |
| `contexta.store.records` | Stable | record truth plane, scan/replay/export | Usually no |
| `contexta.store.artifacts` | Stable | artifact truth plane, verify/import/export | Usually no |
| `contexta.interpretation` | Stable | query, compare, diagnostics, lineage, reports | Sometimes |
| `contexta.recovery` | Advanced | replay, backup, restore | No |
| CLI | Stable | command-line investigation and operator tasks | Yes, if you prefer shell workflows |
| Embedded HTTP / UI | Stable | local-only delivery surface for read/investigation | No, unless you specifically want browser access |

## Surface Details

### `Contexta`

Use `Contexta` when you want:

- the main Python entry point
- one object that owns config and workspace binding
- a single place to access query, compare, diagnostics, lineage, and report flows

This is the recommended starting point for almost everyone.

### `contexta.config`

Use `contexta.config` when you need:

- explicit `UnifiedConfig` control
- profile selection
- env override handling
- direct configuration models

Start here when the default facade construction is not enough.

### `contexta.contract`

Use `contexta.contract` when you work directly with:

- canonical models
- `StableRef`
- validation
- serialization

This surface is stable, but it is not the first thing most new users need.

### `contexta.capture`

Use `contexta.capture` when you want more direct control over:

- runtime scopes
- capture emissions
- capture result types
- sink-related capture behavior

This is where you go when the facade-level capture path is not specific enough.

### `contexta.store.metadata`

Use this when you need direct access to:

- projects
- runs
- stages
- relations
- provenance
- metadata migration or integrity helpers

This is a stable public surface, but it is an advanced one.

### `contexta.store.records`

Use this when you need:

- record append
- scan
- replay
- export
- integrity and repair operations on the record plane

This surface matters most for operator and advanced data-path workflows.

### `contexta.store.artifacts`

Use this when you need:

- artifact ingest
- artifact verification
- artifact import/export
- retention planning
- quarantine and repair flows

This is the artifact-plane public home.

### `contexta.interpretation`

Use this when you want read-oriented analysis over canonical stored data:

- query
- compare
- diagnostics
- lineage
- reports

This is often the second most important stable surface after the root facade.

### `contexta.recovery`

Use this for operator workflows:

- replay
- backup
- restore

This surface is public, but it is intentionally documented as `Advanced`.

### `contexta.adapters`

Use this for optional integrations with external systems.

Built-in lightweight adapters (no external dependencies):

- `contexta.adapters.export` — CSV export helpers
- `contexta.adapters.html` — HTML rendering helpers
- `contexta.adapters.notebook` — Notebook display surface

Vendor-gated adapters (raise `DependencyError` when deps are absent):

- `contexta.adapters.otel` — OpenTelemetry bridge (`[otel]` extra)
- `contexta.adapters.mlflow` — MLflow Tracking bridge (`[mlflow]` extra)

`StdoutSink` is available without extras via `contexta.capture.sinks`.

See [Adapters](./adapters.md) for full details.

### `ctx.notebook`

Use `ctx.notebook` when working in Jupyter or IPython environments.

This property provides `show_run()`, `compare_runs()`, `show_metric_trend()`,
and DataFrame conversion helpers. Works without IPython installed — display
calls degrade gracefully.

See [Notebook Surface](./notebook.md) for full details.

## CLI And HTTP/UI

### CLI

The canonical CLI target is `contexta`.

Use the CLI when you want:

- shell-oriented workflows
- run inspection
- comparison
- report generation
- operator tasks

The CLI is part of the public surface, but its naming and packaging are still being fully aligned during the prototype transition.

### Embedded HTTP / UI

Use embedded HTTP/UI when you want:

- local browser-based inspection
- JSON transport for read flows
- a local-only delivery surface over the same product semantics

Important boundary:

- it is not a separate SaaS platform
- it is not the primary write surface
- it should be understood as a local delivery adapter

## Internal Namespaces You Should Not Use Directly

The following namespaces are not public import targets:

- `contexta.api`
- `contexta.runtime`
- `contexta.common`
- `contexta.surfaces`

These may appear in the repository because they are real implementation modules, but they are not the contract new users should build against.

## Which Surface Should I Pick?

### I Just Want To Start

Use:

- `Contexta`
- README quickstart

### I Need Explicit Config Control

Use:

- `Contexta`
- `contexta.config`

### I Need To Work With Canonical Models

Use:

- `contexta.contract`

### I Need Investigation And Reporting

Use:

- `Contexta`
- `contexta.interpretation`

### I Need Recovery

Use:

- `contexta.recovery`

### I Prefer The Shell

Use:

- CLI

## Next Reading

Continue with:

- [Core Concepts](./core-concepts.md)
- [Getting Started](./getting-started.md)
