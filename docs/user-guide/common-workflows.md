# Common Contexta Workflows

This guide focuses on the day-to-day tasks most users care about once a workspace already contains canonical data.

The safest default remains:

- start with `Contexta`
- bind it to one workspace
- use facade methods first
- move to direct store or recovery APIs only when you need more control

If you have not created a working workspace yet, finish [Getting Started](./getting-started.md) first.

## Open One Workspace

Most workflows begin by opening one workspace through one facade:

```python
from pathlib import Path

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig

ctx = Contexta(
    config=UnifiedConfig(
        project_name="guide-proj",
        workspace=WorkspaceConfig(root_path=Path(".contexta")),
    )
)
```

Use one workspace per logical project or experiment family. That keeps run refs, reports, and recovery actions easier to reason about.

## Inspect One Run

If you already know a canonical run ref, the fastest read path is a run snapshot:

```python
snapshot = ctx.get_run_snapshot("run:guide-proj.demo-run")

print(snapshot.run.run_id)
print(snapshot.run.status)
print(len(snapshot.stages))
print(len(snapshot.records))
print(len(snapshot.artifacts))
```

Use this workflow when you want to answer:

- what happened in this run?
- which stages were present?
- how much evidence exists in the workspace already?

## Compare Two Runs

Run comparison is the next most common workflow once you have more than one execution to inspect:

```python
comparison = ctx.compare_runs(
    "run:guide-proj.demo-run",
    "run:guide-proj.demo-run-v2",
)

print(comparison.summary)
print(len(comparison.stage_comparisons))
```

If you are comparing multiple candidate runs and want one best run by a metric:

```python
best = ctx.select_best_run(
    [
        "run:guide-proj.demo-run",
        "run:guide-proj.demo-run-v2",
    ],
    metric_key="accuracy",
    higher_is_better=True,
)

print(best)
```

Use compare when you want to inspect:

- metric changes
- stage-level differences
- report-level differences
- best-run selection for one metric

## Build Reports

Once the data is in canonical form, report generation stays under the same facade:

```python
snapshot_report = ctx.build_snapshot_report("run:guide-proj.demo-run")
compare_report = ctx.build_run_report(
    "run:guide-proj.demo-run",
    "run:guide-proj.demo-run-v2",
)
project_report = ctx.build_project_summary_report("guide-proj")
```

Reports can then be materialized into formats that fit the downstream task:

```python
markdown_text = snapshot_report.to_markdown()
html_text = snapshot_report.to_html()
json_payload = snapshot_report.to_json()
```

Use report generation when you want output that is easier to:

- review
- share
- archive
- render into HTML or export workflows later

## Inspect Diagnostics

Diagnostics are useful when you want the system to point at incomplete or suspicious states:

```python
diagnostics = ctx.diagnose_run("run:guide-proj.demo-run")

for issue in diagnostics.issues:
    print(issue.severity, issue.code, issue.summary)
```

Use diagnostics when you want a quicker answer to:

- what looks incomplete?
- what looks inconsistent?
- which issues should I inspect first?

## Trace Lineage

Lineage helps when the question is about relationships rather than one run in isolation:

```python
traversal = ctx.traverse_lineage(
    "artifact:guide-proj.demo-run.model",
    direction="outbound",
    max_depth=3,
)

print(len(traversal.edges))
print(len(traversal.visited_refs))
```

Use lineage when you want to ask:

- where did this artifact come from?
- what depends on this result?
- what sits upstream or downstream of this subject?

## Analyze Metric Trends

If the question is about run-to-run movement instead of a single comparison, use a trend query:

```python
trend = ctx.get_metric_trend(
    "accuracy",
    project_name="guide-proj",
)

print(trend.metric_key)
print(len(trend.points))
```

Trend workflows are useful for:

- metric drift across runs
- project-level progress over time
- identifying values worth deeper comparison

## Runtime Capture Preview

The runtime capture surface is already usable, but in the current prototype it should still be understood as the forward-looking write path rather than the most conservative read/query onboarding path.

```python
with ctx.run("training-run") as run:
    run.event("dataset.loaded", message="dataset prepared")
    run.metric("accuracy", 0.93, unit="ratio")

    with run.stage("train") as stage:
        stage.metric("loss", 0.42)
```

Use runtime capture when you want:

- live instrumentation in application code
- scope-aware event and metric emission
- one product surface for lifecycle and capture behavior

For the shortest currently verified path from write to query/report, keep using the canonical-data tutorial in [Getting Started](./getting-started.md).

## When To Use Something Else

Stay with the facade when your goal is:

- inspect one run
- compare runs
- build reports
- diagnose problems
- trace lineage

Move to the advanced guide when you need:

- explicit config resolution
- direct store access
- backup or restore planning

## Where To Go Next

Continue with:

- [Advanced Usage](./advanced.md)
- [Testing Guide](./testing.md)
