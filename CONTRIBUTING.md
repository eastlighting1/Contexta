# Contributing To Contexta

This guide explains how to work on `Contexta` in the current repository.

The most important rule is simple:

- contribute against the documented public product surface
- avoid turning internal implementation paths into accidental public contracts

## Development Setup

Clone the repository and install the development environment:

```powershell
uv sync --dev
```

For ad-hoc local scripts run directly against the source tree (without
installing), add `src` to the Python path:

```powershell
$env:PYTHONPATH = "src"
```

For normal usage, `uv sync --dev` installs the package in editable mode so
`PYTHONPATH` is not needed.

## Repository Layout

Key areas:

- `src/contexta/`
  - product code
- `tests/`
  - repository test suites
- `docs/`
  - public documentation
- `examples/`
  - executable public examples
## Public Boundary Rules

Safe public targets for docs, examples, and new user-facing code:

- `contexta`
- `contexta.config`
- `contexta.contract`
- `contexta.capture`
- `contexta.store.metadata`
- `contexta.store.records`
- `contexta.store.artifacts`
- `contexta.interpretation`
- `contexta.recovery`

Do not introduce new examples or docs that anchor on:

- `contexta.api`
- `contexta.runtime`
- `contexta.common`
- `contexta.surfaces`

Those modules exist, but they are not the public contract we want contributors to normalize.

## Documentation Rules

When editing public docs:

- use canonical product names first
- prefer task-oriented guidance over internal architecture narration
- point to executable examples whenever possible
- avoid promising behavior that is not already implemented or tested

Public docs should describe:

- stable product usage
- known limitations or caveats when they matter

Public docs should not expose:

- WBS progress
- internal scratch notes
- accidental internal import paths as if they were supported APIs

## Example Rules

Examples in `examples/` are part of the public documentation surface.

That means they should:

- use public imports only
- run from a normal repository checkout
- match the docs that point to them
- have regression coverage when practical

If you change:

- `examples/quickstart/`
  - rerun `uv run pytest tests/e2e/test_quickstart_examples.py -q`
- `examples/recovery/`
  - rerun `uv run pytest tests/e2e/test_recovery_examples.py -q`

## Testing

The project uses `pytest`.

Broad validation:

```powershell
uv run pytest -q
```

Smaller targeted suites you will likely use often:

```powershell
uv run pytest tests/e2e/test_quickstart_examples.py -q
uv run pytest tests/e2e/test_recovery_examples.py -q
uv run pytest tests/e2e/test_capture_to_report.py -q
```

When choosing tests:

- run the smallest suite that proves your change
- expand to broader suites when public behavior moved
- keep examples and docs tied to executable evidence

## Code And Change Style

When making code changes:

- preserve canonical naming in public-facing code paths
- prefer explicit, typed models over loose ad-hoc payload handling
- respect the separation between metadata, records, and artifacts as truth-owning planes
- keep recovery flows explicit about warnings, degradation, and loss notes

When making documentation changes:

- keep wording honest about current limitations
- update hubs and entry pages when new docs appear
- avoid leaving “planned” language behind once a page exists

## Submitting Changes

Before you consider a change ready:

- confirm the changed docs or examples still match reality
- run the nearest relevant test suite
- check that new public examples avoid internal imports
- update adjacent navigation pages when you add a new public document

If you touch public behavior, consider whether these also need updates:

- `README.md`
- `docs/index.md`
- `docs/user-guide/index.md`
- reference pages
- examples

## Versioning Policy

Contexta uses [Semantic Versioning](https://semver.org) with PEP 440 pre-release identifiers.

**Single source of truth:** `[project].version` in `pyproject.toml`.
`contexta.__version__` reads this at runtime via `importlib.metadata` — do not duplicate it.

### Version scheme

| Version form | When to use |
|---|---|
| `0.MINOR.PATCH` | Current pre-1.0 series |
| `0.MINOR.0` | New public API surface; may include breaking changes (pre-1.0 convention) |
| `0.x.PATCH` | Bug fixes only, no breaking changes |
| `1.0.0` | Stable public API contract — requires full REL sign-off |

### Pre-release identifiers (PEP 440)

| Identifier | Example | Use for |
|---|---|---|
| alpha | `0.2.0a1` | Early preview, incomplete features |
| beta | `0.2.0b1` | Feature complete, stabilizing |
| rc | `0.2.0rc1` | Release candidate, final validation |

### Bumping the version

Use `uv version` to update `pyproject.toml` in one command:

```powershell
uv version --bump patch              # 0.1.0 -> 0.1.1
uv version --bump minor              # 0.1.0 -> 0.2.0
uv version --bump minor --bump rc   # 0.1.0 -> 0.2.0rc1
uv version 0.2.0                     # set explicitly
```

After bumping:

```powershell
git add pyproject.toml
git commit -m "chore: bump version to $(uv version --short)"
git tag "v$(uv version --short)"
```

### Git tag convention

Tags use a `v` prefix: `v0.1.0`, `v0.2.0rc1`.
The release workflow (REL-026) triggers on `v*` tag pushes.

## Release Process

This section describes how to cut a release. Steps 1–5 are the pre-release gate; steps 6–8 are the actual publish.

### 1. Confirm the release gate passes

```powershell
uv run pytest --tb=short -q
```

All tests must pass (0 failures). Also confirm CI is green on `main`.

### 2. Bump the version

```powershell
uv version --bump minor              # new features
uv version --bump patch              # bug fixes only
uv version --bump minor --bump rc   # release candidate
```

Verify the bump:

```powershell
uv version --short   # prints the new version
```

### 3. Build and verify distributions

```powershell
uv build
```

Spot-check the wheel in a clean environment:

```powershell
uv venv /tmp/ctx-release-check
uv pip install --python /tmp/ctx-release-check/Scripts/python dist/contexta-*.whl --quiet
/tmp/ctx-release-check/Scripts/python -c "from contexta import __version__; print(__version__)"
/tmp/ctx-release-check/Scripts/contexta --help
```

### 4. Generate checksums

```powershell
uv run python -c "
import hashlib, pathlib
for f in sorted(pathlib.Path('dist').glob('contexta-*')):
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    print(f'{h}  {f.name}')
"
```

Paste the output into `.github/RELEASE_NOTES_v{VERSION}.md`.

### 5. Commit and tag

```powershell
git add pyproject.toml
git commit -m "chore: bump version to $(uv version --short)"
git tag "v$(uv version --short)"
```

### 6. Push the tag

```powershell
git push origin main "v$(uv version --short)"
```

Pushing the tag triggers the `release.yml` workflow (REL-026), which builds distributions and uploads them to the GitHub Release automatically.

### 7. Verify the automated release

Pushing the tag triggers `release.yml`, which:

1. Runs the full test suite as a release gate
2. Builds the wheel and sdist
3. Creates the GitHub Release and attaches the distributions automatically
4. Publishes to PyPI via Trusted Publishing (OIDC)

Check **Actions → Release** to confirm all three jobs (`build`, `github-release`, `pypi-publish`) passed.

### 8. Post-release

- Verify the GitHub Release page looks correct
- Confirm the PyPI release appears at `https://pypi.org/project/contexta/`
- Delete the local `/tmp/ctx-release-check` venv

## CI Workflows

Four GitHub Actions workflows run on every push and pull request:

| Workflow | File | Runs on |
|---|---|---|
| CI | `.github/workflows/ci.yml` | push / PR → main, master |
| Test Matrix | `.github/workflows/test-matrix.yml` | push / PR → main, master + nightly |
| Packaging | `.github/workflows/packaging.yml` | push / PR → main, master |
| Docs and Examples | `.github/workflows/examples.yml` | push / PR → main, master |

**Release gate** — the command every workflow mirrors locally:

```powershell
uv run pytest --tb=short -q
```

All 544 tests must pass with 0 failures before any release.

## Branch Protection (main)

The following checks are **required** before a PR can merge into `main`:

- `CI / Test (Python 3.14)` — full test suite + import smoke + CLI smoke
- `Packaging / Build wheel + sdist` — build succeeds, wheel contents are clean
- `Packaging / Install from wheel + smoke` — wheel installs and imports correctly in a clean venv

The following checks are **informational** (not blocking):

- `Test Matrix / pytest / Python 3.14 / ubuntu-latest`
- `Test Matrix / pytest / Python 3.14 / windows-latest`
- `Docs and Examples / Internal link check`
- `Docs and Examples / Quickstart examples`
- `Docs and Examples / Recovery examples`

To configure branch protection in GitHub:

1. Go to **Settings → Branches → Add rule** for `main`
2. Enable **Require status checks to pass before merging**
3. Search for and add the three required check names above
4. Enable **Require branches to be up to date before merging**

## Where To Go Next

- product docs: [docs/index.md](./docs/index.md)
- user guide: [docs/user-guide/index.md](./docs/user-guide/index.md)
- examples: [examples/quickstart/README.md](./examples/quickstart/README.md), [examples/recovery/README.md](./examples/recovery/README.md)
