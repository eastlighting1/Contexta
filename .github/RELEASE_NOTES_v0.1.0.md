# Contexta 0.1.0

First public release of Contexta — local-first observability for ML systems.

## Highlights

- Single `contexta` import root covering capture, store, query, compare, and recovery
- Local `.contexta/` workspace backed by DuckDB metadata, JSONL record store, and file artifact store
- Embedded CLI (`contexta --help`), HTTP server, HTML export, and CSV export surfaces
- Recovery built in: replay, backup, restore, artifact transfer
- Full test suite (544 tests), GitHub Actions CI, and SHA-pinned third-party actions

## What's New

This is the initial release. All public surfaces are new:

- `contexta` — unified facade (`Contexta`, `ContextaError`, `__version__`)
- `contexta.config` — config models, profiles, env overrides, `load_config`
- `contexta.contract` — canonical models (`Run`, `RecordEnvelope`, `ArtifactManifest`, …), validation, serialization
- `contexta.capture` — runtime capture scopes (`RunScope`, `StageScope`, `OperationScope`) and emissions
- `contexta.store.metadata` — DuckDB-backed metadata truth plane
- `contexta.store.records` — JSONL record append, replay, scan, integrity
- `contexta.store.artifacts` — artifact ingest, verify, export, import
- `contexta.interpretation` — query, compare, diagnostics, lineage, trend, anomaly, alert, provenance, reports
- `contexta.recovery` — replay outbox, backup, restore

**CLI:** `contexta runs`, `run show`, `diagnostics`, `trend`, `aggregate`, `lineage`, `compare`, `report`, `export`, `serve`, `provenance`, `artifact`, `backup`, `restore`, `recover`

**HTTP surface:** `/runs`, `/projects`, `/runs/{id}`, `/runs/{id}/diagnostics`, `/runs/{id}/report`, `/ui`

## Bug Fixes

- HTTP server: `GET /runs/{run_id}` failed with 500 when the run ID contained URL-encoded characters (`:` → `%3A`). Fixed by applying `urllib.parse.unquote` to path parameters in `surfaces/http/server.py`.

## Breaking Changes

None — initial release.

## Deprecations

None — initial release.

## Dependency Updates

Initial pinned versions:

| Package | Version |
|---|---|
| duckdb | 1.5.1 |
| numpy | 2.4.4 |
| scikit-learn | 1.8.0 |

## Installation

```
pip install contexta==0.1.0
```

Or with uv:

```
uv add contexta==0.1.0
```

## Checksums

```
63d3db24a1f303917c459e8f1deecd8bb27a7f080dae99263ca2cdbad842b002  contexta-0.1.0-py3-none-any.whl
66aa035c2d881c096cd3f2f650555c84825cc42fcd09713c97d927ec8b8db66c  contexta-0.1.0.tar.gz
```
