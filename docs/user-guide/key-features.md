# Contexta Key Features

`Contexta` is a single product surface for local-first ML observability workflows.

Instead of treating capture, storage, query, comparison, reporting, and recovery as separate tools, `Contexta` brings them under one canonical product identity:

- Python import root: `contexta`
- CLI target: `contexta`
- env prefix: `CONTEXTA_*`
- workspace root: `.contexta/`

## What Is Contexta?

`Contexta` is designed for teams that want to:

- keep observability data local and inspectable
- use canonical models instead of ad-hoc payloads
- query and compare runs from the same product surface that wrote them
- keep recovery inside the product instead of as external scripts

The intended core loop is:

1. capture
2. store
3. query
4. report

Everything else in the product is organized around making that loop reliable and inspectable.

## The Main Product Outcomes

### One Product Instead Of Six Separate Surfaces

`Contexta` replaces the idea of many independent primary surfaces with one canonical surface.

What this gives you:

- one public product identity
- one public import root
- one public workspace shape
- one place to look first when starting new code

### Local-First By Default

The product is built around a local workspace and local inspection.

This means:

- you can create and inspect data without a remote service
- canonical data lives in a workspace you control
- query and reporting do not require a hosted platform to make sense

Embedded HTTP/UI may exist as delivery surfaces, but they are still local-first and local-only by design.

### Canonical Data Instead Of Ad-Hoc Logs

`Contexta` is organized around canonical models for:

- context
- records
- artifacts
- lineage and provenance

This matters because:

- query results are more stable
- reports can be built from a predictable schema
- degraded or incomplete states can be expressed explicitly instead of being hidden in free-form text

### Unified Read And Investigation Flow

Once canonical data exists in the workspace, `Contexta` can read it through one investigation surface.

That includes:

- run listing
- run snapshots
- comparison
- diagnostics
- lineage traversal
- report generation

The point is not only to store data, but to make it inspectable in a consistent way.

### Recovery Is Part Of The Product

`Contexta` treats recovery as a first-class concern rather than an afterthought.

That includes:

- replay
- backup
- restore

This matters because observability systems become hard to trust when recovery depends on custom scripts and undocumented operator knowledge.

## Feature Map

| Feature Area | What It Gives You |
| --- | --- |
| Unified facade | A single starting point for the product |
| Local workspace | Inspectable, local-first canonical storage |
| Canonical contract | Stable models, validation, and serialization |
| Investigation layer | Query, compare, diagnostics, lineage, reports |
| Recovery layer | Replay, backup, restore |

## Who Benefits Most

### New Users

New users benefit from:

- one place to start
- one naming system to learn
- a clear path from quickstart to deeper usage

### Operators

Operators benefit from:

- explicit workspace ownership
- recovery in the same product story
- a clearer boundary between public surface and internal implementation

## What This Section Does Not Promise

This section describes the product direction and stable public shape. It does not claim that every release-alignment detail is already complete.

In the current prototype stage:

- canonical naming is already `Contexta` / `contexta`
- some packaging and CLI alignment work is still in progress
- the public docs set is still being filled out

Use this section as the conceptual overview, then continue with:

- [Tools and Surfaces](./tools-and-surfaces.md)
- [Core Concepts](./core-concepts.md)
- [Getting Started](./getting-started.md)
