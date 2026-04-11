# Release Candidate Checklist

Work through this checklist before tagging and publishing any release.
Check each item off as you confirm it. Do not skip items for patch releases.

## 1. Code and Tests

- [ ] All tests pass locally: `uv run pytest --tb=short -q` (544 passed, 0 failed)
- [ ] No known failing tests on `main` in GitHub Actions CI
- [ ] `uv audit --preview-features audit` reports 0 vulnerabilities
- [ ] `uv lock --check` confirms lockfile is consistent

## 2. Version and Metadata

- [ ] Version in `pyproject.toml` matches the intended release tag
- [ ] `uv version --short` prints the expected version
- [ ] `from contexta import __version__` returns the expected version
- [ ] `classifiers` in `pyproject.toml` reflect the correct Python version(s)

## 3. Package Build

- [ ] `uv build` completes without errors
- [ ] Wheel top-level contains only `contexta` and `contexta-{ver}.dist-info`
- [ ] Sdist contains no internal files (`.claude/`, `Brain.md`, `uv.lock`, etc.)
- [ ] Wheel installs cleanly in a fresh venv:
  ```
  uv venv /tmp/ctx-rc-check
  /tmp/ctx-rc-check/Scripts/pip install dist/contexta-*.whl --quiet
  /tmp/ctx-rc-check/Scripts/python -c "from contexta import __version__; print(__version__)"
  /tmp/ctx-rc-check/Scripts/contexta --help
  ```

## 4. Public API Smoke

- [ ] Root import: `from contexta import Contexta, ContextaError, __version__`
- [ ] Config: `from contexta.config import UnifiedConfig, load_config`
- [ ] Contract: `from contexta.contract import Run, ArtifactManifest, ValidationReport`
- [ ] Capture: `from contexta.capture import EventEmission, MetricEmission, RunScope`
- [ ] Store: `MetadataStore`, `RecordStore`, `ArtifactStore`
- [ ] Interpretation: `QueryService`
- [ ] Recovery: `create_workspace_backup`, `plan_restore`, `replay_outbox`

## 5. CLI Smoke

- [ ] `contexta --help` shows all subcommands
- [ ] `contexta runs` runs without error against a test workspace
- [ ] `contexta run show {id}` runs without error
- [ ] `contexta report snapshot {id}` produces output

## 6. HTTP Surface Smoke

- [ ] `GET /runs` returns HTTP 200
- [ ] `GET /runs/{url-encoded-id}` returns HTTP 200 (not 500)
- [ ] `GET /ui` returns HTTP 200

## 7. Examples

- [ ] `uv run python examples/quickstart/verified_quickstart.py` completes
- [ ] `uv run python examples/quickstart/runtime_capture_preview.py` completes
- [ ] `uv run python examples/recovery/backup_restore_verify.py` completes
- [ ] `uv run python examples/recovery/replay_outbox_demo.py` completes
- [ ] `uv run python examples/recovery/artifact_transfer_demo.py` completes

## 8. Documentation

- [ ] Internal markdown links: 0 broken (run doc-links check script)
- [ ] README quickstart steps work as written
- [ ] `pip install -e .` reference in docs uses correct form (no `[dev]`)
- [ ] `__version__` badge in README matches the release version

## 9. Release Notes

- [ ] `.github/RELEASE_NOTES_v{VERSION}.md` exists and is filled in
- [ ] Breaking changes section is accurate (or explicitly states "None")
- [ ] SHA-256 checksums in the release notes match the built artifacts
- [ ] Full changelog link points to the correct tag comparison URL

## 10. Git and Tagging

- [ ] All release-related commits are on `main`
- [ ] `main` branch is up to date with remote
- [ ] Tag name matches pyproject.toml version: `v$(uv version --short)`
- [ ] Tag has not been pushed yet (push only after all checks above pass)

## 11. GitHub Release (post-tag)

- [ ] `release.yml` workflow triggered successfully after tag push
- [ ] GitHub Release created with correct title and notes
- [ ] Wheel and sdist attached to the release
- [ ] Pre-release flag set correctly (checked for `rc`/`alpha`/`beta`, unchecked for stable)

## 12. PyPI Publish (if applicable)

- [ ] PyPI Trusted Publisher is configured for this repository and `release.yml`
- [ ] `pypi-publish` job completed successfully in GitHub Actions
- [ ] `pip install contexta=={VERSION}` installs correctly from PyPI
- [ ] `uv add contexta=={VERSION}` resolves correctly
