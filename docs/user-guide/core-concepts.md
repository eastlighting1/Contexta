# Contexta Core Concepts

This page introduces the core concepts you need before the rest of the User Guide makes sense.

You do not need every internal detail to use `Contexta`, but you do need a clear mental model for:

- the workspace
- runs and stages
- records and artifacts
- lineage and provenance
- query and reports
- completeness and degraded states

## The Core Loop

The product is built around a local-first core loop:

1. capture
2. store
3. query
4. report

This is the shortest conceptual path through the system.

You create or ingest canonical data, store it in a workspace, read it back through investigation surfaces, and turn it into reports or comparisons.

## Workspace

A workspace is the local root where `Contexta` keeps canonical product data.

Canonical public name:

- `.contexta/`

Conceptually, the workspace is where the product keeps:

- metadata and relations
- records
- artifacts
- reports and exports
- recovery state

You do not need to memorize every internal file path to use the product. What matters is that the workspace is the local home for canonical stored data.

## Project

A project is the top-level grouping for related runs.

Use a project when you want to group:

- one experiment family
- one training/evaluation system
- one product workflow
- one logical application boundary

In practice, many query and reporting flows become easier when runs belong to a clearly named project.

## Run

A run is the primary unit of investigation.

You can think of a run as one execution instance you may later want to:

- inspect
- compare
- diagnose
- report on

Runs are central because most higher-level read flows are anchored on them.

## Stage

A stage is a named part of a run.

Typical stage examples might include:

- prepare
- train
- evaluate
- export

Stages help organize the internal structure of a run so that records, timings, and artifacts can be interpreted in context.

## Operation

An operation is a finer-grained unit inside a stage.

You may care about operations when you need:

- more detailed tracing
- narrower evidence links
- more precise investigation around a sub-step

Not every user needs to think about operations immediately, but they are part of the product's core model.

## Records

Records are append-style observability entries associated with a run, and often with a stage or operation.

The main record families are:

- events
- metrics
- spans
- degraded markers

Use records for time-sequenced observability facts you want to replay, scan, query, or diagnose later.

### Events

Events describe something that happened.

Examples:

- dataset loaded
- checkpoint saved
- fallback used
- validation failed

### Metrics

Metrics describe measured values.

Examples:

- accuracy
- loss
- duration
- artifact size

### Spans

Spans describe timed execution segments.

Examples:

- one operation duration
- one inference call
- one retrieval step

### Degraded Markers

Degraded markers exist so the system can be honest about incomplete or lowered-confidence states.

Examples:

- partial capture
- missing inputs
- replay gaps
- imported loss

This is important because `Contexta` prefers explicit degradation over silent ambiguity.

## Batch

A batch execution is one discrete unit of data processing within a stage.

Examples:

- one epoch in a training loop
- one chunk in a streaming pipeline
- one file in a batch-import workflow

Batches belong to the `Run → Stage → Batch` hierarchy. Use them when you
need finer-grained progress tracking inside a stage.

See [Batch, Sample & Deployment](./batch-sample-deployment.md) for full details.

## Sample

A sample observation records one individual item encountered during a stage.

Examples:

- one input row in a validation pass
- one image in a dataset scan
- one prediction in an inference batch

Samples are primarily useful when you need per-item evidence — for example,
to identify which specific inputs caused a degradation.

## Deployment

A deployment execution tracks one instance of a model or artifact being
made available in an environment.

Examples:

- a model pushed to a serving endpoint
- a checkpoint promoted to staging
- an artifact registered in a model registry

Deployments are scoped to a project and can link back to the run that
produced the deployed artifact.

## Artifacts

Artifacts are stored outputs or files associated with runs and stages.

Examples:

- checkpoints
- generated reports
- exported bundles
- intermediate model outputs

Artifacts are not just file paths. They are part of canonical stored data and can participate in verification, lineage, import/export, and reporting flows.

## Lineage

Lineage describes how entities are connected.

Use lineage when you want to answer questions like:

- where did this artifact come from?
- which run produced this result?
- what sits upstream or downstream of this subject?

Lineage is especially useful when debugging pipelines or explaining how a result was derived.

## Provenance

Provenance describes contextual origin information that helps you trust or reproduce a result.

Examples:

- environment information
- code revision context
- execution metadata
- relation history

Lineage tells you how things connect. Provenance helps explain under what conditions they happened.

## Query

Query is the read-oriented surface for retrieving canonical stored data.

Typical query actions include:

- list runs
- get one run snapshot
- find related artifacts
- inspect stage and record evidence

Query is the first investigation layer after storage.

## Compare

Compare answers the question:

- how does one run differ from another?

Use compare when you want to inspect:

- metric changes
- structural differences
- report differences
- outcome changes across runs

## Diagnostics

Diagnostics is the product's interpretation layer for issues and investigation hints.

Use diagnostics when you want the system to tell you:

- what looks incomplete
- what looks suspicious
- which issues are worth investigating further

Diagnostics is not only about failure. It is also about making hidden problems visible.

## Report

A report is a structured, derived document built from canonical stored data.

Reports let you turn run or comparison data into something easier to:

- review
- share
- archive
- inspect outside the raw store

Reports are downstream of canonical stored data, not a replacement for it.

## Recovery

Recovery covers workflows that help you preserve, replay, restore, or migrate data safely.

Examples:

- replay
- backup
- restore

Recovery is part of the product because observability data only remains useful if it can be safely recovered and moved.

## Stable, Advanced, Internal

You will see these labels repeatedly in the docs.

### Stable

Recommended public contract for new code and new docs.

### Advanced

Public surface, but mainly for power users and operators.

### Internal

Implementation detail, not a supported public import target.

## Mental Model Summary

If you want one short mental model, use this:

- a **workspace** holds canonical data
- a **project** groups related runs
- a **run** is the main unit of investigation
- a **stage** organizes run structure
- **records** capture observable events, metrics, spans, and degraded states
- **artifacts** represent stored outputs and files
- **lineage** and **provenance** explain how results connect and where they came from
- **query**, **compare**, **diagnostics**, and **report** turn stored data into investigation output
- **recovery** keeps the system operable during failure and change

## Next Reading

Continue with:

- [Getting Started](./getting-started.md)
- [Tools and Surfaces](./tools-and-surfaces.md)
