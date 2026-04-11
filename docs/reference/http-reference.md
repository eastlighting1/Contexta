# Contexta HTTP Reference

This page documents the current embedded HTTP delivery surface for `Contexta`.

The key boundary is:

- the embedded HTTP surface is a local-only delivery adapter over the same canonical product semantics
- it is not a separate hosted service
- it is not the primary public Python import surface

For most users, the HTTP surface should be reached through the CLI launcher:

```bash
contexta serve http --host 127.0.0.1 --port 8080
```

At the current prototype stage, the same embedded server is exposed through the canonical `contexta` CLI in the repository.

## Scope Of This Reference

This page documents:

- the current GET endpoints present in the embedded server
- expected content types and query parameters
- the current error envelope behavior
- the distinction between JSON API routes and HTML UI routes

It does not treat `contexta.surfaces.http` as a public Python import home. That module exists in the repository, but the public contract here is the HTTP interface itself.

## Transport Model

The current embedded HTTP surface is:

- local-only
- request/response over HTTP
- GET-only in the current implementation
- split into JSON API routes and server-rendered HTML UI routes

Successful responses use:

- `application/json; charset=utf-8` for JSON routes
- `text/html; charset=utf-8` for UI routes

## Starting The Server

The documented entry path is the CLI:

```bash
contexta serve http [--host HOST] [--port PORT]
```

Current defaults:

- host: `127.0.0.1`
- port: `8080`

The HTTP server is created around a live `Contexta` instance bound to one workspace.

## Error Model

JSON error responses use a consistent envelope:

```json
{
  "error": {
    "code": "http_not_found",
    "message": "Unknown endpoint: /does/not/exist",
    "details": null
  }
}
```

Current error families include:

- `http_not_found`
- `http_bad_request`
- `http_internal_error`
- `contexta`-derived error codes when a product exception is raised directly

Important current behavior:

- unknown API routes return JSON `404`
- many validation errors return JSON `400`
- unexpected internal failures return JSON `500`
- several UI-route failures also currently fall back to the same JSON error envelope instead of an HTML error page

That last point is a prototype limitation worth knowing if you are building browser-side tooling around the UI routes.

## ID Style

The current query layer often accepts shorter run identifiers such as `my-proj.run-01`, and the repository tests use that style heavily.

When you control client code, prefer canonical identifiers where practical. For example:

- run ref style: `run:my-proj.run-01`
- artifact ref style: `artifact:my-proj.run-01.model`

The embedded server passes route values through to the underlying query layer, so accepted identifier forms may be broader than the long-term canonical documentation style.

## JSON API Routes

### `GET /projects`

List project names.

Response shape:

```json
{
  "projects": ["my-proj"]
}
```

Regression-covered:

- yes

### `GET /runs`

List runs.

Query parameters:

- `project`
- `status`
- `after`
- `before`
- `limit`
- `offset`
- `sort`
- `desc`

Response shape:

```json
{
  "runs": [...]
}
```

Current notes:

- `sort` is passed through to the run-list query builder
- when `desc` is omitted, the current HTTP builder defaults to descending sort on `started_at`

Regression-covered:

- yes

### `GET /runs/{run_id}`

Return a run summary payload for one run.

Response includes:

- `run_id`
- `project_name`
- `name`
- `status`
- `started_at`
- `ended_at`
- `stages`
- `artifact_count`
- `record_count`
- `completeness_notes`
- `provenance`

Regression-covered:

- yes

### `GET /runs/{run_id}/diagnostics`

Return diagnostics for one run.

Response:

- diagnostics payload serialized as JSON

Regression-covered:

- yes

### `GET /runs/{run_id}/lineage`

Return lineage traversal for one run-derived subject.

Query parameters:

- `direction`
- `depth`

Accepted directions:

- `upstream`
- `downstream`
- `inbound`
- `outbound`
- `both`

Current behavior:

- `upstream` maps to `inbound`
- `downstream` maps to `outbound`
- invalid directions return `400`

Regression-covered:

- yes

### `GET /runs/{run_id}/report`

Return a snapshot report document as JSON.

Regression-covered:

- yes

### `GET /runs/{run_id}/anomalies`

Return anomaly results for one run.

Query parameters:

- `metric`
- `project`
- `stage`

Response shape:

```json
{
  "anomalies": [...]
}
```

Regression-covered:

- not explicitly in the current HTTP route tests

### `GET /runs/{run_id}/reproducibility`

Return a reproducibility-oriented payload derived from provenance data.

Response includes fields such as:

- `run_id`
- `environment_ref`
- `missing_fields`
- `reproducibility_score`
- `is_fully_reproducible`
- `completeness_notes`

Regression-covered:

- not explicitly in the current HTTP route tests

### `GET /runs/{run_id}/environment-diff/{other_run_id}`

Return an environment-diff payload between two runs.

Response includes fields such as:

- `left_run_id`
- `right_run_id`
- `changed_fields`
- `missing_fields`
- `has_differences`
- package and environment variable change blocks

Regression-covered:

- not explicitly in the current HTTP route tests

### `GET /compare`

Compare two runs.

Required query parameters:

- `left`
- `right`

Missing required parameters return `400`.

Regression-covered:

- yes

### `GET /compare/multi`

Compare multiple runs.

Required query parameter:

- `run_ids`

Current format:

- comma-separated run ids

At least two run ids are required.

Regression-covered:

- yes

### `GET /metrics/trend`

Return a metric trend.

Required query parameter:

- `metric`

Optional query parameters:

- `project`
- `stage`
- `status`
- `after`
- `before`
- `limit`
- `offset`
- `sort`
- `desc`

Regression-covered:

- yes

### `GET /metrics/aggregate`

Return an aggregate for one metric.

Required query parameter:

- `metric`

Optional query parameters:

- `project`
- `stage`
- `status`
- `after`
- `before`
- `limit`
- `offset`
- `sort`
- `desc`

Regression-covered:

- yes

### `GET /alerts/evaluate/{run_id}`

Evaluate one alert rule against one run.

Required query parameters:

- `metric`
- `operator`
- `threshold`

Optional query parameters:

- `stage`
- `severity`

Response shape:

```json
{
  "results": [...]
}
```

Regression-covered:

- not explicitly in the current HTTP route tests

### `GET /search/runs`

Search runs.

Required query parameter:

- `q`

Optional query parameters:

- `project`
- `status`
- `limit`

Regression-covered:

- yes

### `GET /search/artifacts`

Search artifacts.

Required query parameter:

- `q`

Optional query parameter:

- `kind`

Response shape:

```json
{
  "artifacts": [...]
}
```

Regression-covered:

- implemented, but not explicitly covered in the current HTTP route tests

## HTML UI Routes

Successful UI routes return server-rendered HTML.

Current UI surface is read-oriented and local-only.

### `GET /ui`

Render the run list page.

Current behavior:

- `/ui` renders the same run-list view directly
- it does not issue an HTTP redirect

Regression-covered:

- yes

### `GET /ui/runs`

Render the run list page.

Query parameters:

- `project`
- `status`
- `after`
- `before`
- `limit`
- `offset`
- `sort`
- `desc`

Observed page structure includes:

- `run-list-summary`
- `runs-table`

Regression-covered:

- yes

### `GET /ui/runs/{run_id}`

Render run detail.

Observed page structure includes:

- `run-summary`
- `stage-table`
- `artifact-table`
- `record-preview`
- `provenance-summary`
- `completeness-notes`

Regression-covered:

- yes

### `GET /ui/runs/{run_id}/diagnostics`

Render a diagnostics page.

Observed page structure includes:

- `diagnostics-summary`
- `diagnostics-issues`
- `diagnostics-notes`

Regression-covered:

- yes

### `GET /ui/runs/{run_id}/anomalies`

Render an anomalies page.

Observed page structure includes:

- `anomalies-table`

Regression-covered:

- implemented, but not explicitly covered in the current HTTP UI tests

### `GET /ui/compare`

Render run comparison.

Required query parameters:

- `left`
- `right`

Observed page structure includes:

- `comparison-run-header`
- `comparison-summary`
- `comparison-stage-table`
- `comparison-artifact-table`
- `comparison-provenance`
- `comparison-notes`

Regression-covered:

- yes

### `GET /ui/compare/multi`

Render multi-run comparison.

Required query parameter:

- `run_ids`

Current format:

- comma-separated run ids

Observed page structure includes:

- `comparison-summary`
- `comparison-stage-table`

Regression-covered:

- implemented, but not explicitly covered in the current HTTP UI tests

### `GET /ui/metrics/trend`

Render a metric trend page.

Required query parameter:

- `metric`

Optional query parameters:

- `project`
- `stage`
- `status`
- `after`
- `before`
- `limit`
- `offset`
- `sort`
- `desc`

Observed page structure includes:

- `trend-summary`
- `trend-chart`
- `trend-run-table`
- `trend-notes`

Regression-covered:

- yes

### `GET /ui/metrics/aggregate`

Render an aggregate page.

Required query parameter:

- `metric`

Observed page structure includes:

- `trend-summary`
- `trend-notes`

Regression-covered:

- implemented, but not explicitly covered in the current HTTP UI tests

## Regression Coverage Summary

The strongest current route-level evidence comes from:

- `tests/surfaces/test_http_json.py`
- `tests/surfaces/test_http_ui.py`

Those suites explicitly cover:

- `/projects`
- `/runs`
- `/runs/{run_id}`
- `/runs/{run_id}/diagnostics`
- `/runs/{run_id}/report`
- `/runs/{run_id}/lineage`
- `/compare`
- `/compare/multi`
- `/metrics/trend`
- `/metrics/aggregate`
- `/search/runs`
- `/ui`
- `/ui/runs`
- `/ui/runs/{run_id}`
- `/ui/runs/{run_id}/diagnostics`
- `/ui/compare`
- `/ui/metrics/trend`
- unknown-path error handling

Additional routes are present in the server implementation and documented above, but they currently rely more on implementation reading than on dedicated route tests.

## Current Prototype Notes

At the current prototype stage:

- the HTTP surface is embedded and local-only
- the public start path is still the CLI rather than a separate packaged server product
- successful UI routes return HTML, but several UI error cases still fall back to JSON error envelopes
- the route set is richer than the current explicit route-test matrix

That means this page should be read as an honest contract for the current embedded delivery surface, with clear separation between what is implemented and what is already strongly regression-covered.
