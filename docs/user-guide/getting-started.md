# Getting Started With Contexta

This guide expands the README quickstart into a fuller onboarding path.

At the current prototype stage, the most reliable end-to-end path is:

1. install the project
2. create a canonical workspace
3. run the verified quickstart example
4. query that workspace through the facade
5. build a report

This keeps the tutorial aligned with the currently verified prototype behavior.

## Before You Start

You need:

- Python `>=3.14`
- a local checkout of this repository
- a local filesystem where `.contexta/` can be created

## Step 1: Install The Project

For the current prototype checkout, the reliable local development path is:

```powershell
uv sync --dev
$env:PYTHONPATH = "src"
```

This makes the source tree importable for local guide examples while packaging alignment is still in progress.

If you prefer a session-local variant without setting the variable permanently:

```powershell
$env:PYTHONPATH = "src"
uv run python your_script.py
```

If you prefer editable installation with `pip`, treat it as forward-looking packaging work rather than the most conservative prototype path:

```powershell
python -m pip install -e .
```

Once packaging and console-script alignment is complete, this guide can collapse back to a simpler install story.

## Step 2: Understand The Goal

This tutorial is not trying to show every feature at once.

Its goal is to prove four things:

- the canonical import path works
- a `.contexta/` workspace can be created
- canonical data can be written
- the unified facade can read that data and build a report

## Step 3: Run The Verified Quickstart Example

Run the example from the repository root:

```powershell
$env:PYTHONPATH = "src"
uv run python examples/quickstart/verified_quickstart.py
```

The exact example source lives at [examples/quickstart/verified_quickstart.py](../../examples/quickstart/verified_quickstart.py).

This script:

- creates a temporary `.contexta/` workspace
- writes one project, one run, one stage, and one metric record
- queries the run back through the facade
- saves a markdown snapshot report under the workspace `reports/` directory

## Step 4: What Happened

The script did the following:

1. created a temporary root and a `.contexta/` workspace path
2. bound a `Contexta` facade to that workspace through `UnifiedConfig`
3. wrote minimal canonical metadata and one metric record
5. queried the run back through `get_run_snapshot(...)`
6. built a report through `build_snapshot_report(...)`

This is the shortest honest prototype tutorial because it exercises real canonical write and read paths without pretending every capture shortcut is already fully packaged as a polished onboarding flow.

## Step 5: What To Look At Next

After running the script, inspect these ideas:

- the workspace path exists
- the run is queryable by its canonical run ref
- the report object has a title and sections
- the product surface stays under the same `Contexta` facade

## Runtime Capture Preview

The runtime capture surface is already available and worth trying once you understand the canonical workspace story:

```powershell
$env:PYTHONPATH = "src"
uv run python examples/quickstart/runtime_capture_preview.py
```

The preview source lives at [examples/quickstart/runtime_capture_preview.py](../../examples/quickstart/runtime_capture_preview.py).

At the current prototype stage, treat this as the forward-looking runtime entry path, while the verified quickstart above remains the conservative route for query/report onboarding.

## Common Questions

### Why Does This Tutorial Use The Verified Quickstart Script?

Because the goal here is to give you a reliable, currently verified path from workspace creation to report generation.

The example itself still uses canonical model writes under the hood, which avoids promising more runtime capture integration than the current prototype has already proven in the onboarding path.

The example uses public re-export surfaces such as `contexta.config` and `contexta.contract` instead of internal module paths.

### Why Use Full Refs Like `run:guide-proj.demo-run`?

Because `Contexta` uses canonical identifiers as part of its stable contract. Using explicit refs makes the read path clearer and keeps the tutorial aligned with the contract layer.

### Do I Need To Use `UnifiedConfig`?

Not always. The facade can also be opened through other config-resolution paths. This guide uses `UnifiedConfig` because it is explicit and predictable for onboarding.

## Where To Go Next

After this tutorial, continue with:

- [Key Features](./key-features.md)
- [Tools and Surfaces](./tools-and-surfaces.md)
- [Core Concepts](./core-concepts.md)
