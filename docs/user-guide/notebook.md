# Notebook Surface

This page explains `ctx.notebook` — the facade property that exposes
Contexta's investigation surfaces for use inside Jupyter notebooks and
IPython environments.

## Overview

`ctx.notebook` returns a `NotebookSurface` instance bound to the current
`Contexta` object. It provides convenience methods that build HTML fragments
or display them inline.

```python
from contexta import Contexta

ctx = Contexta(...)

# Display a run snapshot inline in a notebook cell
ctx.notebook.show_run("run:my-proj.run-01")
```

The property is lazy — `NotebookSurface` is created on first access and
reused afterwards.

---

## Methods

### `show_run(run_id, *, display=True)`

Renders a run snapshot as an HTML fragment.

- When `display=True` (default) and IPython is available, calls
  `IPython.display.display(HTML(...))` to render inline.
- Returns a `NotebookFragment` with the raw HTML in `.html`.

```python
fragment = ctx.notebook.show_run("run:my-proj.run-01", display=False)
print(fragment.html[:200])
```

### `compare_runs(left_run_id, right_run_id, *, display=True)`

Side-by-side comparison of two runs.

```python
ctx.notebook.compare_runs(
    "run:my-proj.run-01",
    "run:my-proj.run-02",
)
```

### `show_metric_trend(metric_key, *, project_name=None, stage_name=None, query=None, display=True)`

Renders a metric trend chart across runs.

```python
ctx.notebook.show_metric_trend("accuracy", project_name="my-proj")
```

### `render(value)`

Renders an arbitrary Contexta result object (snapshot, report, comparison)
to an HTML string.

```python
snapshot = ctx.get_run_snapshot("run:my-proj.run-01")
html = ctx.notebook.render(snapshot)
```

### `to_pandas(value)` / `to_polars(value)`

Converts a Contexta result to a pandas or polars DataFrame.

```python
# Requires pandas or polars to be installed
df = ctx.notebook.to_pandas(ctx.list_runs("my-proj"))
```

---

## IPython availability

`ctx.notebook` works without IPython installed.

- When IPython **is** available: `show_*` methods render inline in the
  notebook cell via `IPython.display`.
- When IPython **is not** available: `show_*` methods return the
  `NotebookFragment` but do not display anything. No error is raised.

---

## NotebookFragment

All `show_*` methods return a `NotebookFragment` dataclass:

```python
from contexta.surfaces.notebook import NotebookFragment

fragment: NotebookFragment = ctx.notebook.show_run(..., display=False)
fragment.html        # raw HTML string
fragment.title       # page/section title
fragment.metadata    # dict with run_ref, etc.
```

---

## Direct import

`NotebookSurface` and its helpers are also available via:

```python
from contexta.adapters.notebook import (
    NotebookSurface,
    NotebookFragment,
    display_run_snapshot,
    display_run_comparison,
    display_metric_trend,
    render_html_fragment,
    to_pandas,
    to_polars,
)
```

This is the recommended path when you want the surface functions without
constructing a full `Contexta` instance.
