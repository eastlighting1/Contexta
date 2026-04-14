# Contexta Documentation

This is the public documentation hub for `Contexta`.

`Contexta` is the canonical product surface for local-first ML observability and Harness Engineering workflows. Whether you are a human operator investigating a model degradation or an autonomous AI agent reading structured evidence in a generator-evaluator loop, Contexta provides a machine-readable, stable source of truth. The documentation set is organized so new users can start quickly, advanced users can find stable surface boundaries, and operators (both human and AI) can navigate recovery work without mixing public guidance with internal implementation notes.

## Start Here

### If You Are New To Contexta

Start with:

1. [README](../README.md)
2. [User Guide](./user-guide/index.md)

The README gives you the fastest working path. The User Guide explains how the product surface is organized and where to go next.

### If You Need Exact Interface Boundaries

Start with:

1. [API Reference](./reference/api-reference.md)
2. [CLI Reference](./reference/cli-reference.md)
3. [HTTP Reference](./reference/http-reference.md)

The API, CLI, and HTTP references are now available.

## Documentation Structure

### `README.md`

Use the README for:

- product overview
- install instructions
- the shortest verified quickstart
- the high-level surface map

### Conceptual Overview

Use the conceptual overview when you want the project's broader point of view on the problem space:

- [What Is ML Observability?](./what-is-ml-observability.md)

### User Guide

The User Guide is the task-oriented path through the product:

- overview
- [key features](./user-guide/key-features.md)
- [tools and surfaces](./user-guide/tools-and-surfaces.md)
- [core concepts](./user-guide/core-concepts.md)
- [getting started](./user-guide/getting-started.md)
- [common workflows](./user-guide/common-workflows.md)
- [advanced usage](./user-guide/advanced.md)
- [testing](./user-guide/testing.md)

Entry point:

- [User Guide Index](./user-guide/index.md)

### Reference

The reference layer holds stable public contracts for:

- Python API
- CLI
- embedded HTTP / UI

These pages are:

- [API reference](./reference/api-reference.md)
- [CLI reference](./reference/cli-reference.md)
- [HTTP reference](./reference/http-reference.md)

### Operations

The operations layer covers:

- backup
- restore
- replay
- retention and safe export

- [Operations Guide](./operations.md)

### FAQ

The FAQ collects short answers to the questions that recur across onboarding and operations.

- [FAQ](./faq.md)

### Contribution

Contribution guidance will stay in:

- [CONTRIBUTING.md](../CONTRIBUTING.md)

That guide will cover local setup, testing, public/internal boundary rules, and contribution workflow.

### Examples

Examples are part of the documentation surface, not separate throwaway samples.

Current example groups:

- [quickstart examples](../examples/quickstart/README.md) — qs01 (sklearn), qs02 (PyTorch CNN), qs03 (BERT), qs04 (vLLM RAG)
- [case study examples](../examples/case_studies/README.md) — 12 real-world observability scenarios
- [recovery examples](../examples/recovery/README.md) — operator-oriented recovery workflows

## Reading Paths

### New User Path

1. [README](../README.md)
2. [User Guide](./user-guide/index.md)
3. [Getting Started](./user-guide/getting-started.md)
4. [Common Workflows](./user-guide/common-workflows.md)

### Operator Path

1. [README product surface section](../README.md#product-surface)
2. [Tools and Surfaces](./user-guide/tools-and-surfaces.md)
3. [Advanced Usage](./user-guide/advanced.md)
4. [Testing Guide](./user-guide/testing.md)
5. [Operations Guide](./operations.md)
6. [Recovery Examples](../examples/recovery/README.md)

### Contributor Path

1. [README](../README.md)
2. [Getting Started](./user-guide/getting-started.md)
3. [Testing Guide](./user-guide/testing.md)
4. [CONTRIBUTING.md](../CONTRIBUTING.md)

## Naming Rules Used In Public Docs

Public docs use canonical product names first:

- product: `Contexta`
- Python import: `contexta`
- CLI target: `contexta`
- env prefix: `CONTEXTA_*`
- workspace root: `.contexta/`

## Documentation Coverage

All major sections are available:

- README — product overview, install, quickstart
- User Guide — getting started through advanced usage
- API, CLI, and HTTP references
- Quickstart and recovery examples
- Operations, FAQ, and contribution guides
