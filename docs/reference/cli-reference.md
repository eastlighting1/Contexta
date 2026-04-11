# Contexta CLI Reference

This page documents the current embedded command-line surface for `Contexta`.

The canonical CLI name is `contexta`, and the command tree below uses that name throughout.

## Scope Of This Reference

This page documents the command tree that is actually present in the repository today.

It does not document:

- future command groups proposed in migration planning but not yet implemented
- internal helper functions inside `contexta.surfaces.cli`
- hypothetical admin trees that are not part of the current parser


## Global Options

The current parser supports these global options before the command:

| Option | Meaning |
| --- | --- |
| `--workspace <path>` | workspace root, default `.contexta` |
| `--profile local|test` | config profile name |
| `--config <path>` | external config patch file |
| `--set key=value` | direct config override, repeatable |
| `--format text|json` | output format, default `text` |
| `--quiet` | suppress non-result status lines where applicable |

Example:

```bash
contexta --workspace .contexta --format json runs
```

## Exit Behavior

Current CLI exit behavior is:

- `0` on success
- `1` on handled runtime errors
- `2` on argument parsing or usage errors

When `--format json` is used, handled errors are rendered as JSON on stderr.

## Command Tree

```text
contexta
|- runs
|- run
|  |- list
|  |- show
|  |- compare
|  |- compare-many
|  '- diagnose
|- lineage
|- search
|  |- runs
|  '- artifacts
|- compare
|- compare-multi
|- diagnostics
|- trend
|- aggregate
|- anomaly
|- alert
|- report
|  |- snapshot
|  '- compare
|- export
|  |- html
|  '- csv
|     |- runs
|     |- compare
|     |- trend
|     '- anomaly
|- serve
|  '- http
|- provenance
|  |- audit
|  '- diff
|- artifact
|  |- register
|  '- put
|- backup
|  '- create
|- restore
|  '- apply
|- recover
|  '- replay
```

## Query And Investigation Commands

Examples in this section use canonical run refs where possible. The underlying implementation may also accept shorter run identifiers in some repository-local contexts, but canonical refs are the preferred public style.

### `runs`

List runs directly from the current workspace.

```bash
contexta runs [--project NAME] [--status STATUS] [--after ISO] [--before ISO] [--limit N] [--offset N] [--sort started_at|ended_at|name] [--desc]
```

Alias:

- `contexta run list`

### `run show`

Show one run snapshot.

```bash
contexta run show <run_id>
```

### `compare`

Compare two runs.

```bash
contexta compare <left_run_id> <right_run_id>
```

Alias:

- `contexta run compare <left_run_id> <right_run_id>`

### `compare-multi`

Compare multiple runs.

```bash
contexta compare-multi <run_id> <run_id> [...]
```

Alias:

- `contexta run compare-many <run_id> <run_id> [...]`

### `diagnostics`

Diagnose one run.

```bash
contexta diagnostics <run_id> [--fail-on info|warning|error]
```

Alias:

- `contexta run diagnose <run_id> [--fail-on ...]`

### `lineage`

Trace lineage for a subject reference.

```bash
contexta lineage <subject_ref> [--direction upstream|downstream|inbound|outbound|both] [--depth N]
```

Notes:

- `upstream` and `downstream` are accepted user-facing aliases
- the current implementation normalizes them onto inbound/outbound traversal directions

### `search`

Search current workspace data.

Run search:

```bash
contexta search runs <text> [--project NAME] [--status STATUS] [--limit N]
```

Artifact search:

```bash
contexta search artifacts <text> [--kind KIND] [--limit N]
```

### `trend`

Query a metric trend.

```bash
contexta trend <metric_key> [--project NAME] [--stage STAGE] [--status STATUS] [--after ISO] [--before ISO] [--limit N] [--offset N] [--sort started_at|ended_at|name] [--desc]
```

### `aggregate`

Query an aggregate for one metric.

```bash
contexta aggregate <metric_key> [--project NAME] [--stage STAGE] [--status STATUS] [--after ISO] [--before ISO] [--limit N] [--offset N] [--sort started_at|ended_at|name] [--desc]
```

### `anomaly`

Detect anomalies for one run.

```bash
contexta anomaly <run_id> [--metric KEY ...] [--project NAME] [--stage STAGE]
```

### `alert`

Evaluate one threshold alert against one run.

```bash
contexta alert <run_id> --metric <metric_key> --operator gt|lt|gte|lte|eq|ne --threshold <value> [--stage STAGE] [--severity LEVEL]
```

## Report And Export Commands

### `report snapshot`

Build a report for one run snapshot.

```bash
contexta report snapshot <run_id> [--render markdown|json|html|csv] [--output PATH]
```

### `report compare`

Build a report for one run comparison.

```bash
contexta report compare <left_run_id> <right_run_id> [--render markdown|json|html|csv] [--output PATH]
```

### `export html`

Export HTML from either one run or one comparison.

```bash
contexta export html --run <run_id> [--output PATH]
contexta export html --left <left_run_id> --right <right_run_id> [--output PATH]
```

### `export csv`

The current CSV export surface supports four subcommands.

Run list CSV:

```bash
contexta export csv runs [--project NAME] [--status STATUS] [--after ISO] [--before ISO] [--limit N] [--offset N] [--sort started_at|ended_at|name] [--desc] [--output PATH]
```

Comparison CSV:

```bash
contexta export csv compare <left_run_id> <right_run_id> [--output PATH]
```

Trend CSV:

```bash
contexta export csv trend <metric_key> [--project NAME] [--stage STAGE] [--status STATUS] [--after ISO] [--before ISO] [--limit N] [--offset N] [--sort started_at|ended_at|name] [--desc] [--output PATH]
```

Anomaly CSV:

```bash
contexta export csv anomaly <run_id> [--metric KEY ...] [--project NAME] [--stage STAGE] [--output PATH]
```

## Delivery And Provenance Commands

### `serve http`

Start the embedded HTTP server.

```bash
contexta serve http [--host HOST] [--port PORT]
```

Important note:

- the current command group is `serve http`
- there is no separate top-level `ui` group in the current parser

### `provenance audit`

Audit one run for reproducibility-oriented provenance signals.

```bash
contexta provenance audit <run_id>
```

### `provenance diff`

Compare run environments.

```bash
contexta provenance diff <left_run_id> <right_run_id>
```

## Artifact Commands

The current artifact surface is intentionally narrow.

### `artifact register`

Register an artifact into the artifact store.

```bash
contexta artifact register <artifact_kind> <source_path> --run <run_ref> [--stage <stage_ref>] [--artifact-ref <artifact_ref>] [--mode copy|move|adopt]
```

### `artifact put`

Alias for `artifact register`.

```bash
contexta artifact put <artifact_kind> <source_path> --run <run_ref> [--stage <stage_ref>] [--artifact-ref <artifact_ref>] [--mode copy|move|adopt]
```

Important note:

- the current parser does not yet expose separate `artifact verify`, `artifact export`, or `artifact import-package` commands
- those broader flows belong to future CLI alignment work, not to the current embedded command surface

## Backup, Restore, And Replay

### `backup create`

Create a workspace zip backup.

```bash
contexta backup create [--label LABEL] [--output PATH_STEM]
```

Current behavior:

- the current CLI writes a zip archive
- when `--output` is provided, the archive is created at `<PATH_STEM>.zip`
- this is a lightweight workspace-level CLI helper in the prototype

### `restore apply`

Restore or verify a backup archive.

```bash
contexta restore apply <backup_archive_path> [--target-workspace PATH] [--verify-only]
```

Important note:

- although the internal argument name is `backup_ref`, the current command expects a backup archive path

### `recover replay`

Replay records from the record plane.

```bash
contexta recover replay [--mode strict|tolerant] [--run <run_ref>] [--stage <stage_ref>] [--record-type event|metric|span|degraded]
```

## Output Modes

The global `--format` option controls whether command results are emitted as text or JSON.

```bash
contexta --format json runs
contexta --format json diagnostics run:demo.run-01
```

Some report and export commands also support command-local render choices such as `--render html` or `--render json`.

## Current Prototype Notes

At the current prototype stage:

- public docs use the canonical command name `contexta`
- the current launcher is `contexta`
- the current parser supports the command groups documented here
- source-tree workflows may still need repository-local setup while packaging and console-script alignment is in progress

That means this page should be read as the current command contract for the embedded CLI surface, with honest acknowledgment that the final published launcher name is still catching up.
