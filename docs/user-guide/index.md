# Contexta User Guide

The User Guide is the task-oriented path through `Contexta`.

Use this guide when you want to understand how the product surface is organized, which tools to start with, and how to move from a first local workspace to more advanced query, reporting, and recovery workflows.

## Who This Guide Is For

This guide is for:

- new users starting from `README.md`
- advanced users who want to work directly with stable sub-namespaces
- operators who need to understand where recovery fits

If you only want the fastest working path, start with the [README quickstart](../../README.md#quickstart) first.

## Recommended Reading Paths

### New User

1. [README](../../README.md)
2. [Key Features](./key-features.md)
3. [Tools and Surfaces](./tools-and-surfaces.md)
4. [Core Concepts](./core-concepts.md)
5. [Getting Started](./getting-started.md)
6. [Quickstart Examples](../../examples/quickstart/README.md)
7. [Common Workflows](./common-workflows.md)

### Advanced Python User

1. product surface in [README](../../README.md#product-surface)
2. [Tools and Surfaces](./tools-and-surfaces.md)
3. [Advanced Usage](./advanced.md)
4. [API Reference](../reference/api-reference.md)

### Operator

1. [README product surface section](../../README.md#product-surface)
2. [Advanced Usage](./advanced.md)
3. [Testing Guide](./testing.md)
4. [Recovery Examples](../../examples/recovery/README.md)
5. [Operations Guide](../operations.md)

## Guide Roadmap

The User Guide is organized into the following sections.

| Section | Purpose | Status |
| --- | --- | --- |
| [`key-features.md`](./key-features.md) | Explain what `Contexta` gives you as a single product | Available |
| [`tools-and-surfaces.md`](./tools-and-surfaces.md) | Show the public surface map and when to use each tool | Available |
| [`core-concepts.md`](./core-concepts.md) | Define runs, stages, records, artifacts, lineage, reports, and completeness | Available |
| [`getting-started.md`](./getting-started.md) | Expand the README quickstart into a fuller onboarding tutorial | Available |
| [`common-workflows.md`](./common-workflows.md) | Cover the most frequent day-to-day usage flows | Available |
| [`advanced.md`](./advanced.md) | Cover direct config, store, interpretation, and recovery usage | Available |
| [`testing.md`](./testing.md) | Explain the testing posture and how to validate examples and workflows | Available |
| [`batch-sample-deployment.md`](./batch-sample-deployment.md) | Batch, Sample, and Deployment tracking — logging, querying, diagnostics | Available |
| [`adapters.md`](./adapters.md) | Optional sink adapters — StdoutSink, OTelSink, MLflowSink | Available |
| [`notebook.md`](./notebook.md) | Notebook surface — `ctx.notebook`, inline display, DataFrame conversion | Available |
| [`case-studies.md`](./case-studies.md) | 12 real-world scenarios — why Contexta, without vs with, key APIs per case | Available |

## What The Guide Will Cover

### Key Features

This section will explain the product in terms of user-visible outcomes:

- unified product surface
- local-first workspace
- canonical storage
- query, comparison, diagnostics, lineage, and reports
- recovery support

### Tools And Surfaces

This section will show how the product is divided across:

- `Contexta`
- `contexta.config`
- `contexta.contract`
- `contexta.capture`
- `contexta.store.metadata`
- `contexta.store.records`
- `contexta.store.artifacts`
- `contexta.interpretation`
- `contexta.recovery`
- CLI
- embedded HTTP / UI

Each tool or surface will be described in terms of:

- what it is
- when to use it
- whether it is the recommended starting point
- whether it is `Stable` or `Advanced`

### Getting Started

The getting started path will expand the README into a more complete onboarding flow:

1. install
2. create a workspace
3. write minimal canonical data
4. query a run
5. build a report
6. understand what the workspace now contains

### Common Workflows

This section will focus on common user goals rather than module structure, for example:

- create and inspect a run
- compare two runs
- build a report
- inspect diagnostics
- trace lineage

### Advanced Usage

This section will explain how to move beyond the facade when needed:

- explicit config control
- direct store usage
- interpretation-level services
- recovery workflows

### Testing

This section will explain how to think about validation in the product:

- what is covered by the test suite
- how example validation should work
- what semantic parity means across Python, CLI, and HTTP

## Public Naming Rules

The User Guide uses canonical product names first:

- product: `Contexta`
- Python import: `contexta`
- CLI target: `contexta`
- env prefix: `CONTEXTA_*`
- workspace root: `.contexta/`

## What To Read Right Now

The core and advanced User Guide pages are now available. Use these entry points:

- [README](../../README.md)
- [README quickstart](../../README.md#quickstart)
- [README product surface section](../../README.md#product-surface)
- [Key Features](./key-features.md)
- [Tools and Surfaces](./tools-and-surfaces.md)
- [Core Concepts](./core-concepts.md)
- [Getting Started](./getting-started.md)
- [Quickstart Examples](../../examples/quickstart/README.md)
- [Common Workflows](./common-workflows.md)
- [Advanced Usage](./advanced.md)
- [Testing Guide](./testing.md)
- [Recovery Examples](../../examples/recovery/README.md)
- [Batch, Sample & Deployment](./batch-sample-deployment.md)
- [Adapters](./adapters.md)
- [Notebook Surface](./notebook.md)
- [Batch & Sample Examples](../../examples/batch_sample/README.md)
- [Adapter Examples](../../examples/adapters/README.md)
- [Case Studies](./case-studies.md)
- [Case Study Examples](../../examples/case_studies/README.md)
- [API Reference](../reference/api-reference.md)
- [CLI Reference](../reference/cli-reference.md)
- [HTTP Reference](../reference/http-reference.md)
- [Operations Guide](../operations.md)
- [FAQ](../faq.md)
- [CONTRIBUTING.md](../../CONTRIBUTING.md)

This page remains the stable entry point for the full User Guide as reference, operations, FAQ, and contribution documents are added.
