# Contexta FAQ

## Should I import `contexta`?

Yes. `contexta` is the supported Python import root for this repository.

## What names should I use in this repository?

Use `Contexta` for the product name, `contexta` for the Python package and CLI, `CONTEXTA_*` for environment variables, and `.contexta/` for the canonical workspace root.

## What is the canonical workspace root?

The canonical workspace root is `.contexta/`.

## Is Contexta local-first?

Yes. The documented product direction is local-first observability over a canonical workspace that owns metadata, records, artifacts, reports, and recovery state.

## What is the fastest verified way to get started?

Use the verified quickstart example:

- [Quickstart examples](../examples/quickstart/README.md)

That path is regression-covered and currently proves workspace creation, canonical writes, query, and report generation.

## Does the runtime capture API already exist?

Yes. The runtime scope API is live and documented, but the most conservative onboarding path for query/report is still the verified quickstart example rather than a capture-only tutorial.

## Is the HTTP/UI surface a hosted service?

No. The current HTTP/UI surface is an embedded, local-only delivery adapter over the same canonical product semantics.

See:

- [HTTP Reference](./reference/http-reference.md)

## When should I use `contexta.recovery`?

Use `contexta.recovery` for operator-oriented workflows such as backup, restore planning, and replay.

See:

- [Operations Guide](./operations.md)
- [Recovery examples](../examples/recovery/README.md)

## Can I rely on internal namespaces like `contexta.api` or `contexta.runtime`?

No. Public docs intentionally avoid those as import homes. Stick to the documented public surfaces such as `contexta`, `contexta.config`, `contexta.contract`, `contexta.capture`, `contexta.interpretation`, `contexta.recovery`, and the three store packages.

## How do I validate that examples still work?

Use the smallest matching test suite from the testing guide. For example:

- quickstart examples: `uv run pytest tests/e2e/test_quickstart_examples.py -q`
- recovery examples: `uv run pytest tests/e2e/test_recovery_examples.py -q`

See:

- [Testing Guide](./user-guide/testing.md)

## Why do local scripts still need `PYTHONPATH=src`?

Because source-tree script ergonomics are still in the prototype stage. Repository test runs already get `src/` from project configuration, but ad-hoc local example runs still use `PYTHONPATH=src` as the safest current path.

## Where should I look next?

- product onboarding: [User Guide](./user-guide/index.md)
- exact interfaces: [API Reference](./reference/api-reference.md), [CLI Reference](./reference/cli-reference.md), [HTTP Reference](./reference/http-reference.md)
- contributing: [CONTRIBUTING.md](../CONTRIBUTING.md)
