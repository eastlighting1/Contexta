# Contexta API Reference

This page documents the current public Python API surface for `Contexta`.

The reference below uses the canonical public import homes and the current repository state.

## Scope Of This Reference

This page documents:

- the `Contexta` facade
- public `contexta.config` functions and model classes
- public `contexta.contract` serialization and validation functions
- public `contexta.capture` emission and result models
- public `contexta.interpretation` service classes
- public store and recovery entry points exposed from `contexta.*`

It does not document:

- internal modules under `contexta.api`, `contexta.runtime`, `contexta.common`, or `contexta.surfaces`
- undocumented deep import paths
- retired legacy shim packages or migration-only prototype artifacts
- hypothetical APIs that are not present in the repository today

---

## `contexta.Contexta`

```python
class Contexta(
    *,
    workspace: str = ".contexta",
    profile: str | None = None,
    config: UnifiedConfig | Mapping[str, object] | None = None,
    sinks: Sequence[Sink] | None = None,
)
```

Primary facade for all Contexta operations. Manages a runtime session, capture sinks, and service accessors for query, comparison, diagnostics, lineage, trend, alert, and report workflows.

**Parameters:**

`workspace`
Root directory of the Contexta workspace. Resolved relative to the current working directory.

`profile`
Named built-in profile to load (`"local"`, `"test"`, etc.). Ignored if `config` is provided directly.

`config`
Explicit config object or raw mapping. When provided, `workspace` and `profile` are ignored except as fallback defaults inside the config.

`sinks`
Capture sinks to attach to the session. When `None`, sinks are resolved from config.

**Returns:** `Contexta`

**See also:** `Contexta.open` — alternative classmethod constructor.

---

### `Contexta.open`

```python
@classmethod
Contexta.open(
    *,
    workspace: str = ".contexta",
    profile: str | None = None,
    config: UnifiedConfig | Mapping[str, object] | None = None,
    sinks: Sequence[Sink] | None = None,
) -> Contexta
```

Classmethod alias for `Contexta(...)`. Identical in behavior.

---

### Properties

`Contexta.project_name` → `str`
Resolved project name from config.

`Contexta.session` → `RuntimeSession`
Runtime session object backing capture scopes.

`Contexta.sinks` → `tuple[Sink, ...]`
Configured capture sinks.

`Contexta.metadata_store` → `MetadataStore`
Direct access to the metadata truth-plane store.

`Contexta.record_store` → `RecordStore`
Direct access to the record truth-plane store.

`Contexta.artifact_store` → `ArtifactStore`
Direct access to the artifact truth-plane store.

`Contexta.repository` → `CompositeStoreRepository`
Composite read repository across all stores.

`Contexta.query_service` → `QueryService`

`Contexta.compare_service` → `CompareService`

`Contexta.diagnostics_service` → `DiagnosticsService`

`Contexta.lineage_service` → `LineageService`

`Contexta.trend_service` → `TrendService`

`Contexta.alert_service` → `AlertService`

`Contexta.provenance_service` → `ProvenanceService`

`Contexta.report_builder` → `ReportBuilder`

---

### `Contexta.run`

```python
Contexta.run(
    name: str,
    *,
    run_id: str | None = None,
    tags: Mapping[str, str] | None = None,
    metadata: Mapping[str, Any] | None = None,
    code_revision: str | None = None,
    config_snapshot: Mapping[str, Any] | None = None,
    dataset_ref: str | None = None,
) -> contextmanager
```

Open a run scope as a context manager. All capture calls inside the `with` block are associated with this run.

**Parameters:**

`name`
Human-readable name for this run.

`run_id`
Explicit run ID. When `None`, a stable ID is generated automatically.

`tags`
Key-value string tags attached to the run record.

`metadata`
Arbitrary JSON-serializable metadata attached to the run record.

`code_revision`
Git commit SHA or other code revision identifier.

`config_snapshot`
Snapshot of the config used for this run, attached as provenance.

`dataset_ref`
Stable reference string identifying the primary dataset for this run.

**Example:**

```python
with ctx.run("training", tags={"env": "prod"}) as run:
    ctx.metric("accuracy", 0.94)
```

---

### `Contexta.current_run`

```python
Contexta.current_run() -> RunScope | None
```

Return the active `RunScope`, or `None` if no run scope is open.

---

### `Contexta.current_stage`

```python
Contexta.current_stage() -> StageScope | None
```

Return the active `StageScope`, or `None` if no stage scope is open.

---

### `Contexta.current_operation`

```python
Contexta.current_operation() -> OperationScope | None
```

Return the active `OperationScope`, or `None` if no operation scope is open.

---

### `Contexta.event`

```python
Contexta.event(
    key: str,
    *,
    message: str,
    level: str = "info",
    attributes: Mapping[str, Any] | None = None,
    tags: Mapping[str, str] | None = None,
) -> CaptureResult
```

Emit a single structured event into the current scope.

**Parameters:**

`key`
Dot-separated event key, e.g. `"training.epoch_complete"`.

`message`
Human-readable event message.

`level`
Severity level. One of `"debug"`, `"info"`, `"warning"`, `"error"`.

`attributes`
Arbitrary JSON-serializable structured fields attached to the event.

`tags`
Key-value string tags for filtering and grouping.

**Returns:** `CaptureResult`

---

### `Contexta.emit_events`

```python
Contexta.emit_events(
    emissions: Sequence[EventEmission | Mapping[str, Any]],
) -> BatchCaptureResult
```

Emit a batch of events. Each element may be an `EventEmission` instance or a raw mapping with the same fields.

**Returns:** `BatchCaptureResult`

---

### `Contexta.metric`

```python
Contexta.metric(
    key: str,
    value: Any,
    *,
    unit: str | None = None,
    aggregation_scope: str = "step",
    tags: Mapping[str, str] | None = None,
    summary_basis: str = "raw_observation",
) -> CaptureResult
```

Emit a single metric observation into the current scope.

**Parameters:**

`key`
Dot-separated metric key, e.g. `"train.loss"`.

`value`
Numeric or structured metric value.

`unit`
Optional unit label, e.g. `"seconds"`, `"bytes"`.

`aggregation_scope`
Granularity hint for downstream aggregation. One of `"step"`, `"stage"`, `"run"`.

`tags`
Key-value string tags for filtering and grouping.

`summary_basis`
Basis for summary computation. One of `"raw_observation"`, `"mean"`, `"max"`, `"min"`, `"last"`.

**Returns:** `CaptureResult`

---

### `Contexta.emit_metrics`

```python
Contexta.emit_metrics(
    emissions: Sequence[MetricEmission | Mapping[str, Any]],
) -> BatchCaptureResult
```

Emit a batch of metrics.

**Returns:** `BatchCaptureResult`

---

### `Contexta.span`

```python
Contexta.span(
    name: str,
    *,
    started_at: str | None = None,
    ended_at: str | None = None,
    status: str = "ok",
    span_kind: str = "operation",
    attributes: Mapping[str, Any] | None = None,
    linked_refs: Sequence[str] | None = None,
    parent_span_id: str | None = None,
) -> CaptureResult
```

Emit a single trace span into the current scope.

**Parameters:**

`name`
Human-readable span name.

`started_at`
ISO 8601 timestamp string. Defaults to the time of this call.

`ended_at`
ISO 8601 timestamp string. Defaults to the time of this call.

`status`
Span status. One of `"ok"`, `"error"`, `"unset"`.

`span_kind`
Semantic kind of this span. One of `"operation"`, `"stage"`, `"call"`, `"internal"`.

`attributes`
Arbitrary JSON-serializable structured fields.

`linked_refs`
Stable reference strings this span is causally linked to.

`parent_span_id`
Parent span ID for explicit parent-child linking.

**Returns:** `CaptureResult`

---

### `Contexta.emit_spans`

```python
Contexta.emit_spans(
    emissions: Sequence[SpanEmission | Mapping[str, Any]],
) -> BatchCaptureResult
```

Emit a batch of spans.

**Returns:** `BatchCaptureResult`

---

### `Contexta.register_artifact`

```python
Contexta.register_artifact(
    artifact_kind: str,
    path: str,
    *,
    artifact_ref: str | None = None,
    attributes: Mapping[str, Any] | None = None,
    compute_hash: bool = True,
    allow_missing: bool = False,
) -> CaptureResult
```

Register a single artifact in the current scope.

**Parameters:**

`artifact_kind`
Semantic kind label, e.g. `"model"`, `"dataset"`, `"checkpoint"`.

`path`
File system path to the artifact. Ingested into the artifact store.

`artifact_ref`
Explicit stable reference string. Auto-generated when `None`.

`attributes`
Arbitrary JSON-serializable metadata attached to the artifact manifest.

`compute_hash`
When `True`, compute and store a content hash for later verification.

`allow_missing`
When `True`, registration succeeds even if the file does not exist at `path`.

**Returns:** `CaptureResult`

---

### `Contexta.register_artifacts`

```python
Contexta.register_artifacts(
    emissions: Sequence[ArtifactRegistrationEmission | Mapping[str, Any]],
) -> BatchCaptureResult
```

Register a batch of artifacts.

**Returns:** `BatchCaptureResult`

---

### `Contexta.list_projects`

```python
Contexta.list_projects() -> tuple[str, ...]
```

Return all project names known to the metadata store.

---

### `Contexta.list_runs`

```python
Contexta.list_runs(
    project_name: str | None = None,
    *,
    status: str | None = None,
    tags: Mapping[str, str] | None = None,
    metric_conditions: Sequence[MetricCondition] = (),
    time_range: TimeRange | None = None,
    limit: int | None = None,
    offset: int = 0,
    sort_by: str = "started_at",
    sort_desc: bool = True,
    query: RunListQuery | None = None,
) -> tuple[Any, ...]
```

Return a filtered, sorted listing of runs from the metadata store.

**Parameters:**

`project_name`
Restrict to runs belonging to this project. When `None`, all projects are searched.

`status`
Filter by run status string, e.g. `"completed"`, `"failed"`.

`tags`
Exact tag filter. Only runs that carry all provided key-value pairs are returned.

`metric_conditions`
Sequence of `MetricCondition` filters applied to stored metric summaries.

`time_range`
Restrict runs to those started within the given `TimeRange`.

`limit`
Maximum number of runs to return.

`offset`
Skip this many runs before returning results.

`sort_by`
Field to sort on. Typically `"started_at"` or `"ended_at"`.

`sort_desc`
When `True`, return newest-first.

`query`
Pre-built `RunListQuery` object. When provided, all other filter arguments are ignored.

**Returns:** `tuple` of run summary objects.

---

### `Contexta.get_run_snapshot`

```python
Contexta.get_run_snapshot(run_id: str) -> RunSnapshot
```

Return a full `RunSnapshot` for the given run ID, including record and artifact evidence.

**Parameters:**

`run_id`
The run's stable ID string.

**Returns:** `contexta.interpretation.RunSnapshot`

---

### `Contexta.get_provenance`

```python
Contexta.get_provenance(run_id: str) -> ProvenanceView
```

Return a `ProvenanceView` for the given run.

---

### `Contexta.get_artifact_origin`

```python
Contexta.get_artifact_origin(artifact_ref: str) -> RunSnapshot | None
```

Return the `RunSnapshot` of the run that produced the given artifact, or `None` if unknown.

---

### `Contexta.compare_runs`

```python
Contexta.compare_runs(left_run_id: str, right_run_id: str) -> RunComparison
```

Compare two runs side-by-side.

**Returns:** `RunComparison`

---

### `Contexta.compare_multiple_runs`

```python
Contexta.compare_multiple_runs(run_ids: Sequence[str]) -> MultiRunComparison
```

Compare three or more runs together.

**Returns:** `MultiRunComparison`

---

### `Contexta.compare_report_documents`

```python
Contexta.compare_report_documents(left: ReportDocument, right: ReportDocument) -> ReportComparison
```

Produce a diff between two `ReportDocument` objects.

**Returns:** `ReportComparison`

---

### `Contexta.select_best_run`

```python
Contexta.select_best_run(
    run_ids: Sequence[str],
    metric_key: str,
    *,
    stage_name: str | None = None,
    higher_is_better: bool = True,
) -> str | None
```

Return the run ID from `run_ids` with the best value for `metric_key`, or `None` if no qualifying run is found.

**Parameters:**

`run_ids`
Candidate run IDs to compare.

`metric_key`
Dot-separated metric key to rank by.

`stage_name`
When provided, restrict metric lookup to this stage.

`higher_is_better`
When `True`, the run with the highest metric value wins. When `False`, the lowest wins.

**Returns:** `str | None`

---

### `Contexta.diagnose_run`

```python
Contexta.diagnose_run(run_id: str) -> DiagnosticsResult
```

Run the diagnostics service on the given run and return structured findings.

**Returns:** `DiagnosticsResult`

---

### `Contexta.traverse_lineage`

```python
Contexta.traverse_lineage(
    subject_ref: str,
    *,
    direction: str | None = None,
    max_depth: int | None = None,
) -> LineageTraversal
```

Traverse lineage edges starting from `subject_ref`.

**Parameters:**

`subject_ref`
Stable reference string of the starting artifact or run.

`direction`
Traversal direction. One of `"upstream"`, `"downstream"`, or `None` for both.

`max_depth`
Maximum edge depth to traverse. `None` means unlimited.

**Returns:** `LineageTraversal`

---

### `Contexta.get_metric_trend`

```python
Contexta.get_metric_trend(
    metric_key: str,
    *,
    project_name: str | None = None,
    stage_name: str | None = None,
    query: RunListQuery | None = None,
) -> MetricTrend
```

Return time-series trend data for a metric across runs.

**Returns:** `MetricTrend`

---

### `Contexta.get_step_series`

```python
Contexta.get_step_series(
    run_id: str,
    metric_key: str,
    *,
    stage_id: str | None = None,
    stage_name: str | None = None,
) -> StepSeries
```

Return step-level series data for a metric within a single run.

**Returns:** `StepSeries`

---

### `Contexta.get_stage_duration_trend`

```python
Contexta.get_stage_duration_trend(
    stage_name: str,
    *,
    project_name: str | None = None,
    query: RunListQuery | None = None,
) -> DurationTrend
```

Return wall-clock duration trend for a named stage across runs.

**Returns:** `DurationTrend`

---

### `Contexta.get_artifact_size_trend`

```python
Contexta.get_artifact_size_trend(
    artifact_kind: str,
    *,
    project_name: str | None = None,
    query: RunListQuery | None = None,
) -> ArtifactSizeTrend
```

Return artifact size trend for a given artifact kind across runs.

**Returns:** `ArtifactSizeTrend`

---

### `Contexta.evaluate_alerts`

```python
Contexta.evaluate_alerts(
    run_id: str,
    rules: Sequence[AlertRule],
) -> tuple[AlertResult, ...]
```

Evaluate alert rules against a single run.

**Returns:** `tuple[AlertResult, ...]`

---

### `Contexta.evaluate_alerts_fleet`

```python
Contexta.evaluate_alerts_fleet(
    rules: Sequence[AlertRule],
    *,
    project_name: str | None = None,
    query: RunListQuery | None = None,
) -> AlertReport
```

Evaluate alert rules across a fleet of runs.

**Returns:** `AlertReport`

---

### `Contexta.audit_reproducibility`

```python
Contexta.audit_reproducibility(run_id: str) -> ReproducibilityAudit
```

Audit the reproducibility evidence attached to the given run.

**Returns:** `ReproducibilityAudit`

---

### `Contexta.compare_environments`

```python
Contexta.compare_environments(left_run_id: str, right_run_id: str) -> EnvironmentDiff
```

Diff the environment snapshots of two runs.

**Returns:** `EnvironmentDiff`

---

### `Contexta.build_snapshot_report`

```python
Contexta.build_snapshot_report(run_id: str) -> ReportDocument
```

Build a `ReportDocument` summarizing a single run snapshot.

**Returns:** `ReportDocument`

---

### `Contexta.build_run_report`

```python
Contexta.build_run_report(left_run_id: str, right_run_id: str) -> ReportDocument
```

Build a `ReportDocument` for a two-run comparison.

**Returns:** `ReportDocument`

---

### `Contexta.build_project_summary_report`

```python
Contexta.build_project_summary_report(project_name: str) -> ReportDocument
```

Build a `ReportDocument` summarizing all runs in a project.

**Returns:** `ReportDocument`

---

### `Contexta.build_trend_report`

```python
Contexta.build_trend_report(
    metric_key: str,
    *,
    project_name: str | None = None,
    stage_name: str | None = None,
    query: RunListQuery | None = None,
) -> ReportDocument
```

Build a `ReportDocument` for a metric trend query.

**Returns:** `ReportDocument`

---

### `Contexta.build_alert_report`

```python
Contexta.build_alert_report(run_id: str, rules: Sequence[AlertRule]) -> ReportDocument
```

Build a `ReportDocument` for alert evaluation on a single run.

**Returns:** `ReportDocument`

---

### `Contexta.build_multi_run_report`

```python
Contexta.build_multi_run_report(run_ids: Sequence[str]) -> ReportDocument
```

Build a `ReportDocument` for a multi-run comparison.

**Returns:** `ReportDocument`

---

## `contexta.config`

### `load_config`

```python
contexta.config.load_config(
    *,
    profile: ProfileName | None = None,
    overlays: Sequence[ProfileOverlayName] | None = None,
    config_file: str | Path | None = None,
    config: UnifiedConfig | Mapping[str, object] | None = None,
    workspace: str | Path | None = None,
    project_name: str | None = None,
    env: Mapping[str, str] | None = None,
    use_env: bool = True,
) -> UnifiedConfig
```

Resolve a `UnifiedConfig` from profile, file, environment variables, and direct patches. Resolution order: profile → config file → env overrides → `config` patch.

**Parameters:**

`profile`
Named built-in profile to load as the base.

`overlays`
Additional named overlays applied on top of the base profile.

`config_file`
Path to a TOML/YAML config file. Applied after the base profile.

`config`
Direct config object or mapping patch. Applied last, overriding everything else.

`workspace`
Workspace root path override.

`project_name`
Project name shorthand override.

`env`
Custom environment variable mapping. Defaults to `os.environ` when `None`.

`use_env`
When `False`, skip environment variable resolution entirely.

**Returns:** `UnifiedConfig`

---

### `load_profile`

```python
contexta.config.load_profile(
    name: ProfileName,
    *,
    overlays: Sequence[ProfileOverlayName] = (),
    workspace: str | Path | None = None,
    project_name: str | None = None,
) -> UnifiedConfig
```

Load a built-in profile with optional overlays and shorthand overrides.

**Parameters:**

`name`
Profile name. One of the values in `PROFILE_NAMES`.

`overlays`
Named overlays to apply on top of the base profile.

`workspace`
Workspace root path shorthand.

`project_name`
Project name shorthand.

**Returns:** `UnifiedConfig`

---

### `make_local_config`

```python
contexta.config.make_local_config(
    *,
    overlays: Sequence[ProfileOverlayName] | None = None,
    config_file: str | Path | None = None,
    config: UnifiedConfig | Mapping[str, object] | None = None,
    workspace: str | Path | None = None,
    project_name: str | None = None,
    env: Mapping[str, str] | None = None,
    use_env: bool = True,
) -> UnifiedConfig
```

Build a validated config using the `local` base profile. Equivalent to `load_config(profile="local", ...)`.

**Returns:** `UnifiedConfig`

---

### `make_test_config`

```python
contexta.config.make_test_config(
    *,
    overlays: Sequence[ProfileOverlayName] | None = None,
    config_file: str | Path | None = None,
    config: UnifiedConfig | Mapping[str, object] | None = None,
    workspace: str | Path | None = None,
    project_name: str | None = None,
    env: Mapping[str, str] | None = None,
    use_env: bool = False,
) -> UnifiedConfig
```

Build a validated config using the `test` base profile. Environment variables are ignored by default (`use_env=False`) for test isolation.

**Returns:** `UnifiedConfig`

---

## `contexta.contract`

### `to_json`

```python
contexta.contract.to_json(obj: Any) -> str
```

Serialize a canonical contract model to deterministic canonical JSON.

**Parameters:**

`obj`
A canonical model instance (e.g. `Run`, `MetricRecord`, `ArtifactManifest`).

**Returns:** `str` — UTF-8 JSON string with sorted keys.

---

### `to_payload`

```python
contexta.contract.to_payload(obj: Any) -> Any
```

Convert a canonical model to a JSON-safe Python structure (dicts, lists, primitives). Use when you need the intermediate dict rather than a string.

**Returns:** `dict | list | str | int | float | bool | None`

---

### `validate_run`

```python
contexta.contract.validate_run(
    run: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

Validate a `Run` model against the canonical contract rules.

**Parameters:**

`run`
A `Run` instance to validate.

`registry`
Extension registry for validating extension fields. When `None`, extension fields are not validated.

**Returns:** `ValidationReport`

---

## `contexta.interpretation` service classes

### `QueryService`

```python
class QueryService:
    def __init__(self, repository: CompositeRepository) -> None
```

**Parameters:**

`repository`
Composite read repository used for project, run, stage, relation, record, artifact, and provenance lookups.

**Returns:** `QueryService`

---

#### `QueryService.list_projects`

```python
QueryService.list_projects() -> tuple[str, ...]
```

**Returns:** `tuple[str, ...]`

---

#### `QueryService.list_runs`

```python
QueryService.list_runs(
    project_name: str | None = None,
    *,
    query: RunListQuery | None = None,
) -> tuple[RunRecord, ...]
```

**Parameters:**

`project_name`
Optional project-name filter.

`query`
Optional `RunListQuery` containing metadata filters, metric conditions, sort options, offset, and limit.

**Returns:** `tuple[RunRecord, ...]`

---

#### `QueryService.get_run_snapshot`

```python
QueryService.get_run_snapshot(run_id: str) -> RunSnapshot
```

**Parameters:**

`run_id`
Run identifier.

**Returns:** `RunSnapshot`

---

#### `QueryService.get_artifact_origin`

```python
QueryService.get_artifact_origin(artifact_ref: str) -> RunSnapshot | None
```

**Parameters:**

`artifact_ref`
Artifact reference string.

**Returns:** `RunSnapshot | None`

---

### `CompareService`

```python
class CompareService:
    def __init__(
        self,
        query_service: QueryService,
        *,
        config: ComparisonPolicy | None = None,
    ) -> None
```

**Parameters:**

`query_service`
Query service used to load run snapshots.

`config`
Optional comparison policy.

**Returns:** `CompareService`

---

#### `CompareService.compare_runs`

```python
CompareService.compare_runs(left_run_id: str, right_run_id: str) -> RunComparison
```

**Parameters:**

`left_run_id`
Left-hand run identifier.

`right_run_id`
Right-hand run identifier.

**Returns:** `RunComparison`

---

#### `CompareService.compare_multiple_runs`

```python
CompareService.compare_multiple_runs(run_ids: Sequence[str]) -> MultiRunComparison
```

**Parameters:**

`run_ids`
Run identifiers to compare. At least two distinct IDs are required.

**Returns:** `MultiRunComparison`

---

#### `CompareService.select_best_run`

```python
CompareService.select_best_run(
    run_ids: Sequence[str],
    metric_key: str,
    *,
    stage_name: str | None = None,
    higher_is_better: bool = True,
) -> str | None
```

**Parameters:**

`run_ids`
Candidate run identifiers.

`metric_key`
Metric key used for ranking.

`stage_name`
Optional stage-name restriction.

`higher_is_better`
Whether larger metric values rank ahead of smaller ones.

**Returns:** `str | None`

---

#### `CompareService.compare_report_documents`

```python
CompareService.compare_report_documents(left: object, right: object) -> ReportComparison
```

**Parameters:**

`left`
Left report-like object.

`right`
Right report-like object.

**Returns:** `ReportComparison`

---

### `DiagnosticsService`

```python
class DiagnosticsService:
    def __init__(
        self,
        query_service: QueryService,
        *,
        config: DiagnosticsPolicy | None = None,
    ) -> None
```

**Parameters:**

`query_service`
Query service used to load run snapshots.

`config`
Optional diagnostics policy.

**Returns:** `DiagnosticsService`

---

#### `DiagnosticsService.diagnose_run`

```python
DiagnosticsService.diagnose_run(run_id: str) -> DiagnosticsResult
```

**Parameters:**

`run_id`
Run identifier.

**Returns:** `DiagnosticsResult`

---

### `LineageService`

```python
class LineageService:
    def __init__(
        self,
        query_service: QueryService,
        *,
        config: LineagePolicy | None = None,
    ) -> None
```

**Returns:** `LineageService`

---

#### `LineageService.traverse_lineage`

```python
LineageService.traverse_lineage(
    subject_ref: str,
    *,
    direction: str | None = None,
    max_depth: int | None = None,
) -> LineageTraversal
```

**Parameters:**

`subject_ref`
Root run, artifact, stage, operation, or relation subject.

`direction`
Traversal direction. Valid values are `"inbound"`, `"outbound"`, or `"both"`.

`max_depth`
Maximum traversal depth.

**Returns:** `LineageTraversal`

---

### `TrendService`

```python
class TrendService:
    def __init__(
        self,
        query_service: QueryService,
        *,
        config: TrendPolicy | None = None,
    ) -> None
```

**Returns:** `TrendService`

---

#### `TrendService.get_metric_trend`

```python
TrendService.get_metric_trend(
    metric_key: str,
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
    stage_name: str | None = None,
) -> MetricTrend
```

**Parameters:**

`metric_key`
Metric key to aggregate across runs.

`query`
Optional run population filter.

`project_name`
Optional project-name filter.

`stage_name`
Optional stage-name restriction.

**Returns:** `MetricTrend`

---

#### `TrendService.get_step_series`

```python
TrendService.get_step_series(
    run_id: str,
    metric_key: str,
    *,
    stage_id: str | None = None,
) -> StepSeries
```

**Parameters:**

`run_id`
Run identifier.

`metric_key`
Metric key to read within the run.

`stage_id`
Optional exact stage identifier.

**Returns:** `StepSeries`

---

#### `TrendService.get_stage_duration_trend`

```python
TrendService.get_stage_duration_trend(
    stage_name: str,
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
) -> DurationTrend
```

**Parameters:**

`stage_name`
Stage name to aggregate across runs.

`query`
Optional run population filter.

`project_name`
Optional project-name filter.

**Returns:** `DurationTrend`

---

#### `TrendService.get_artifact_size_trend`

```python
TrendService.get_artifact_size_trend(
    artifact_kind: str,
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
) -> ArtifactSizeTrend
```

**Parameters:**

`artifact_kind`
Artifact kind to aggregate across runs.

`query`
Optional run population filter.

`project_name`
Optional project-name filter.

**Returns:** `ArtifactSizeTrend`

---

### `AlertService`

```python
class AlertService:
    def __init__(
        self,
        query_service: QueryService,
        *,
        metric_aggregation: str = "latest",
    ) -> None
```

**Returns:** `AlertService`

---

#### `AlertService.evaluate_alerts`

```python
AlertService.evaluate_alerts(
    run_id: str,
    rules: tuple[AlertRule, ...] | list[AlertRule],
) -> tuple[AlertResult, ...]
```

**Parameters:**

`run_id`
Run identifier.

`rules`
Alert rules to evaluate against the run snapshot.

**Returns:** `tuple[AlertResult, ...]`

---

#### `AlertService.evaluate_alerts_fleet`

```python
AlertService.evaluate_alerts_fleet(
    rules: tuple[AlertRule, ...] | list[AlertRule],
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
) -> AlertReport
```

**Parameters:**

`rules`
Alert rules to evaluate across the selected run population.

`query`
Optional run population filter.

`project_name`
Optional project-name filter.

**Returns:** `AlertReport`

---

### `ProvenanceService`

```python
class ProvenanceService:
    def __init__(self, query_service: QueryService) -> None
```

**Returns:** `ProvenanceService`

---

#### `ProvenanceService.audit_reproducibility`

```python
ProvenanceService.audit_reproducibility(run_id: str) -> ReproducibilityAudit
```

**Parameters:**

`run_id`
Run identifier.

**Returns:** `ReproducibilityAudit`

---

#### `ProvenanceService.compare_environments`

```python
ProvenanceService.compare_environments(
    left_run_id: str,
    right_run_id: str,
) -> EnvironmentDiff
```

**Parameters:**

`left_run_id`
Left-hand run identifier.

`right_run_id`
Right-hand run identifier.

**Returns:** `EnvironmentDiff`

---

### `AggregationService`

```python
class AggregationService:
    def __init__(
        self,
        query_service: QueryService,
        *,
        metric_aggregation: str = "latest",
    ) -> None
```

**Returns:** `AggregationService`

---

#### `AggregationService.aggregate_metric`

```python
AggregationService.aggregate_metric(
    metric_key: str,
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
    stage_name: str | None = None,
) -> MetricAggregate
```

**Parameters:**

`metric_key`
Metric key to aggregate.

`query`
Optional run population filter.

`project_name`
Optional project-name filter.

`stage_name`
Optional stage-name restriction.

**Returns:** `MetricAggregate`

---

#### `AggregationService.aggregate_by_stage`

```python
AggregationService.aggregate_by_stage(
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
) -> RunSummaryTable
```

**Parameters:**

`query`
Optional run population filter.

`project_name`
Optional project-name filter.

**Returns:** `RunSummaryTable`

---

#### `AggregationService.run_status_distribution`

```python
AggregationService.run_status_distribution(
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
) -> RunStatusDistribution
```

**Parameters:**

`query`
Optional run population filter.

`project_name`
Optional project-name filter.

**Returns:** `RunStatusDistribution`

---

### `AnomalyService`

```python
class AnomalyService:
    def __init__(
        self,
        query_service: QueryService,
        *,
        z_score_threshold: float = 2.5,
        min_baseline_runs: int = 3,
        metric_aggregation: str = "latest",
        monitored_metrics: tuple[str, ...] = (),
    ) -> None
```

**Returns:** `AnomalyService`

---

#### `AnomalyService.compute_baseline`

```python
AnomalyService.compute_baseline(
    metric_key: str,
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
    stage_name: str | None = None,
) -> MetricBaseline
```

**Parameters:**

`metric_key`
Metric key used to build the baseline.

`query`
Optional baseline run population filter.

`project_name`
Optional project-name filter.

`stage_name`
Optional stage-name restriction.

**Returns:** `MetricBaseline`

---

#### `AnomalyService.detect_anomalies`

```python
AnomalyService.detect_anomalies(
    run_id: str,
    *,
    baseline: MetricBaseline,
    stage_name: str | None = None,
) -> tuple[AnomalyResult, ...]
```

**Parameters:**

`run_id`
Run identifier.

`baseline`
Precomputed metric baseline.

`stage_name`
Optional stage-name restriction.

**Returns:** `tuple[AnomalyResult, ...]`

---

#### `AnomalyService.detect_anomalies_in_run`

```python
AnomalyService.detect_anomalies_in_run(
    run_id: str,
    *,
    baseline_query: RunListQuery | None = None,
    metric_keys: tuple[str, ...] | None = None,
    stage_name: str | None = None,
) -> tuple[AnomalyResult, ...]
```

**Parameters:**

`run_id`
Run identifier.

`baseline_query`
Optional query used to select the baseline run population.

`metric_keys`
Optional explicit metric-key list.

`stage_name`
Optional stage-name restriction.

**Returns:** `tuple[AnomalyResult, ...]`

---

### `ReportBuilder`

```python
class ReportBuilder:
```

**Returns:** `ReportBuilder`

---

#### `ReportBuilder.build_snapshot_report`

```python
ReportBuilder.build_snapshot_report(
    snapshot: RunSnapshot,
    diagnostics: DiagnosticsResult,
) -> ReportDocument
```

**Parameters:**

`snapshot`
Run snapshot used as the primary report source.

`diagnostics`
Diagnostics result merged into the report.

**Returns:** `ReportDocument`

---

#### `ReportBuilder.build_run_report`

```python
ReportBuilder.build_run_report(
    comparison: RunComparison,
    diagnostics: DiagnosticsResult,
) -> ReportDocument
```

**Parameters:**

`comparison`
Run comparison result used as the primary report source.

`diagnostics`
Diagnostics result merged into the report.

**Returns:** `ReportDocument`

---

#### `ReportBuilder.build_project_summary_report`

```python
ReportBuilder.build_project_summary_report(
    project_name: str,
    *,
    runs: tuple[RunRecord, ...] = (),
    notes: tuple[CompletenessNote, ...] = (),
) -> ReportDocument
```

**Parameters:**

`project_name`
Project name displayed in the report title.

`runs`
Run records included in the summary.

`notes`
Completeness notes rendered into the report.

**Returns:** `ReportDocument`

---

#### `ReportBuilder.build_trend_report`

```python
ReportBuilder.build_trend_report(trend: MetricTrend) -> ReportDocument
```

**Parameters:**

`trend`
Trend result used as the report source.

**Returns:** `ReportDocument`

---

#### `ReportBuilder.build_alert_report`

```python
ReportBuilder.build_alert_report(
    results: list[AlertResult] | tuple[AlertResult, ...],
) -> ReportDocument
```

**Parameters:**

`results`
Alert results included in the report.

**Returns:** `ReportDocument`

---

#### `ReportBuilder.build_multi_run_report`

```python
ReportBuilder.build_multi_run_report(
    comparison: MultiRunComparison,
) -> ReportDocument
```

**Parameters:**

`comparison`
Multi-run comparison used as the report source.

**Returns:** `ReportDocument`

---

### `validate_metric_record`

```python
contexta.contract.validate_metric_record(
    record: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

Validate a `MetricRecord` model.

**Returns:** `ValidationReport`

---

### Deserialization functions

All deserialization functions follow the same pattern:

```python
contexta.contract.deserialize_run(
    data: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> Run

contexta.contract.deserialize_metric_record(
    data: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> MetricRecord

contexta.contract.deserialize_artifact_manifest(
    data: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ArtifactManifest

# ... analogous functions for all contract model types
```

`data`
Raw dict (e.g. from `json.loads`) or an already-constructed model instance.

`registry`
Extension registry used to resolve extension fields. When `None`, extension fields are passed through without validation.

---

## `contexta.store.metadata`

### `MetadataStore`

```python
class MetadataStore(
    config: MetadataStoreConfig | None = None,
)
```

Canonical metadata truth-plane store. Manages project, run, stage, and environment records in a local DuckDB database.

Supports use as a context manager:

```python
with MetadataStore(config) as store:
    report = store.check_integrity()
```

**Properties:**

`MetadataStore.duckdb` — DuckDB frame adapter.

`MetadataStore.pandas` — Pandas frame adapter.

`MetadataStore.polars` — Polars frame adapter.

---

#### `MetadataStore.check_integrity`

```python
MetadataStore.check_integrity(*, full: bool = True) -> IntegrityReport
```

Scan the metadata store for integrity issues.

**Parameters:**

`full`
When `True`, run a full deep scan. When `False`, run a fast surface-level check.

**Returns:** `IntegrityReport`

---

#### `MetadataStore.plan_repairs`

```python
MetadataStore.plan_repairs(report: IntegrityReport | None = None) -> RepairPlan
```

Convert an integrity report into a `RepairPlan` with operator-facing repair candidates. When `report` is `None`, `check_integrity()` is called first.

**Returns:** `RepairPlan`

---

#### `MetadataStore.preview_repairs`

```python
MetadataStore.preview_repairs(plan: RepairPlan | None = None) -> RepairPreview
```

Build a human-readable summary of what a `RepairPlan` would do. When `plan` is `None`, `plan_repairs()` is called first.

**Returns:** `RepairPreview`

---

#### `MetadataStore.build_run_snapshot`

```python
MetadataStore.build_run_snapshot(run_ref: str) -> RunSnapshot
```

Build a metadata-scoped `RunSnapshot` for one run. This is the lower-level metadata-only projection. For the full user-facing snapshot including record and artifact evidence, use `Contexta.get_run_snapshot`.

**Returns:** `contexta.store.metadata.RunSnapshot`

---

#### `MetadataStore.migrate`

```python
MetadataStore.migrate(*, target_version: str | None = None) -> MigrationResult
```

Apply pending schema migrations. When `target_version` is `None`, migrates to the latest schema version.

**Returns:** `MigrationResult`

**See also:** `MetadataStore.dry_run_migration`, `MetadataStore.plan_migration`

---

## `contexta.store.records`

### `RecordStore`

```python
class RecordStore(
    config: RecordStoreConfig | None = None,
)
```

Append-only record truth-plane store. Manages JSONL segment files for all capture record types.

---

### `export_jsonl`

```python
contexta.store.records.export_jsonl(
    store: RecordStore,
    destination: str | Path,
    scan_filter: ScanFilter | None = None,
    *,
    mode: ReplayMode = ReplayMode.STRICT,
) -> ReplayResult
```

Export replayable canonical records as JSONL to `destination`.

**Parameters:**

`store`
The `RecordStore` instance to export from.

`destination`
File path for the output JSONL file.

`scan_filter`
Optional `ScanFilter` to restrict which records are exported.

`mode`
Replay mode controlling error handling. `ReplayMode.STRICT` raises on any bad record. `ReplayMode.LENIENT` skips bad records and continues.

**Returns:** `ReplayResult`

---

### `check_integrity` (records)

```python
contexta.store.records.check_integrity(store: RecordStore) -> IntegrityReport
```

Scan record segments and manifest for integrity issues (truncation, hash mismatches, gaps).

**Returns:** `contexta.store.records.IntegrityReport`

---

## `contexta.store.artifacts`

### `ArtifactStore`

```python
class ArtifactStore(
    config: ArtifactStoreConfig | None = None,
)
```

Artifact truth-plane store. Manages content-addressed binary artifact storage with manifest tracking.

---

### `get_artifact`

```python
contexta.store.artifacts.get_artifact(
    store: ArtifactStore,
    artifact_ref: str,
) -> ArtifactHandle
```

Return an `ArtifactHandle` for the given artifact reference.

**Returns:** `ArtifactHandle`

---

### `read_artifact_bytes`

```python
contexta.store.artifacts.read_artifact_bytes(
    store: ArtifactStore,
    artifact_ref: str,
) -> bytes
```

Read the full body of an artifact into memory.

**Returns:** `bytes`

---

### `open_artifact`

```python
contexta.store.artifacts.open_artifact(
    store: ArtifactStore,
    artifact_ref: str,
    *,
    mode: str = "rb",
) -> BinaryIO
```

Open an artifact as a binary file-like object. The caller is responsible for closing it.

**Returns:** `BinaryIO`

---

### `iter_artifact_chunks`

```python
contexta.store.artifacts.iter_artifact_chunks(
    store: ArtifactStore,
    artifact_ref: str,
    *,
    chunk_size: int | None = None,
) -> Iterator[bytes]
```

Stream an artifact body in chunks. Useful for large artifacts that should not be fully loaded into memory.

**Parameters:**

`chunk_size`
Bytes per chunk. When `None`, the store's default chunk size is used.

**Returns:** `Iterator[bytes]`

---

### `artifact_exists`

```python
contexta.store.artifacts.artifact_exists(
    store: ArtifactStore,
    artifact_ref: str,
) -> bool
```

Return `True` if the artifact body is present in the store.

---

### `list_refs`

```python
contexta.store.artifacts.list_refs(store: ArtifactStore) -> list[str]
```

Return all artifact reference strings known to the store.

---

### `verify_artifact`

```python
contexta.store.artifacts.verify_artifact(
    store: ArtifactStore,
    artifact_ref: str,
    *,
    manifest: ArtifactManifest | None = None,
) -> VerificationReport
```

Verify the integrity of a single artifact by re-hashing its body against the stored manifest.

**Parameters:**

`manifest`
Pre-fetched manifest. When `None`, the manifest is loaded from the store.

**Returns:** `VerificationReport`

---

### `verify_all`

```python
contexta.store.artifacts.verify_all(store: ArtifactStore) -> SweepReport
```

Verify every artifact in the store. Returns a `SweepReport` with per-artifact `VerificationRecord` entries.

**Returns:** `SweepReport`

---

### `inspect_store`

```python
contexta.store.artifacts.inspect_store(store: ArtifactStore) -> StoreSummary
```

Return a high-level `StoreSummary` (artifact count, total size, format version).

**Returns:** `StoreSummary`

---

## `contexta.recovery`

### `plan_workspace_backup`

```python
contexta.recovery.plan_workspace_backup(
    config: UnifiedConfig,
    *,
    label: str | None = None,
    include_cache: bool = False,
    include_exports: bool = False,
) -> BackupPlan
```

Build a `BackupPlan` describing what would be backed up. Does not write anything.

**Parameters:**

`config`
Resolved `UnifiedConfig` for the workspace to back up.

`label`
Optional human-readable label attached to the backup manifest.

`include_cache`
When `True`, include cached intermediate files in the backup.

`include_exports`
When `True`, include previously exported artifact packages in the backup.

**Returns:** `BackupPlan`

---

### `create_workspace_backup`

```python
contexta.recovery.create_workspace_backup(
    config: UnifiedConfig,
    plan: BackupPlan,
) -> BackupResult
```

Execute a `BackupPlan` and write the backup archive to disk.

**Returns:** `BackupResult`

---

### `plan_restore`

```python
contexta.recovery.plan_restore(
    config: UnifiedConfig,
    backup_ref: str,
    *,
    target_workspace: Path | None = None,
    verify_only: bool = False,
) -> RestorePlan
```

Build a `RestorePlan` from a backup reference. Does not restore anything.

**Parameters:**

`backup_ref`
Path or reference string identifying the backup archive.

`target_workspace`
Restore destination. Defaults to the workspace specified in `config`.

`verify_only`
When `True`, the plan includes only verification steps with no destructive writes.

**Returns:** `RestorePlan`

---

### `restore_workspace`

```python
contexta.recovery.restore_workspace(
    config: UnifiedConfig,
    plan: RestorePlan,
) -> RestoreResult
```

Execute a `RestorePlan` and restore the workspace.

**Returns:** `RestoreResult`

---

### `replay_outbox`

```python
contexta.recovery.replay_outbox(
    config: UnifiedConfig,
    *,
    target: str | None = None,
    limit: int | None = None,
    acknowledge_successes: bool = True,
    dead_letter_after_failures: int | None = None,
    sinks: Sequence[Sink] | None = None,
) -> ReplayBatchResult
```

Replay pending outbox records into the configured sinks.

**Parameters:**

`target`
Restrict replay to records targeting this sink identifier. When `None`, all pending records are replayed.

`limit`
Maximum number of records to replay in this call.

`acknowledge_successes`
When `True`, successfully replayed records are removed from the outbox.

`dead_letter_after_failures`
Move a record to the dead-letter queue after this many consecutive failures. When `None`, failed records stay in the outbox indefinitely.

`sinks`
Override sinks to replay into. When `None`, sinks from `config` are used.

**Returns:** `ReplayBatchResult`

---

## `contexta.capture`

### `EventEmission`

```python
@dataclass(frozen=True, slots=True)
class EventEmission:
    key: str
    message: str
    level: str = "info"
    attributes: Mapping[str, Any] | None = None
    tags: Mapping[str, str] | None = None
```

**Parameters:**

`key`
Dot-token event key. Must match the canonical event-key pattern.

`message`
Non-blank event message.

`level`
Canonical event level. Valid values are the contract `EVENT_LEVELS`.

`attributes`
JSON-safe structured attributes. Stored as a normalized mapping.

`tags`
String-to-string tags. Stored as a normalized mapping.

**Returns:** `EventEmission`

**Notes:**

- invalid keys, blank strings, and non-JSON-safe attribute values raise `ValidationError`
- `to_dict()` returns a transport-friendly normalized mapping

---

### `MetricEmission`

```python
@dataclass(frozen=True, slots=True)
class MetricEmission:
    key: str
    value: int | float
    unit: str | None = None
    aggregation_scope: str = "step"
    tags: Mapping[str, str] | None = None
    summary_basis: str = "raw_observation"
```

**Parameters:**

`key`
Dot-token metric key.

`value`
Finite numeric metric value.

`unit`
Optional metric unit label.

`aggregation_scope`
Canonical aggregation scope. Valid values are the contract `METRIC_AGGREGATION_SCOPES`.

`tags`
String-to-string tags.

`summary_basis`
Lower-snake summary-basis token.

**Returns:** `MetricEmission`

**Notes:**

- non-finite numbers and boolean values are rejected
- `to_dict()` returns a transport-friendly normalized mapping

---

### `SpanEmission`

```python
@dataclass(frozen=True, slots=True)
class SpanEmission:
    name: str
    started_at: str | None = None
    ended_at: str | None = None
    status: str = "ok"
    span_kind: str = "operation"
    attributes: Mapping[str, Any] | None = None
    linked_refs: tuple[StableRef | str, ...] | None = None
    parent_span_id: str | None = None
```

**Parameters:**

`name`
Non-blank span name.

`started_at`
Optional ISO 8601 timestamp string.

`ended_at`
Optional ISO 8601 timestamp string. Must be greater than or equal to `started_at` when both are provided.

`status`
Canonical trace-span status. Valid values are the contract `TRACE_SPAN_STATUSES`.

`span_kind`
Canonical trace-span kind. Valid values are the contract `TRACE_SPAN_KINDS`.

`attributes`
JSON-safe span attributes.

`linked_refs`
Stable refs linked to this span. Values may be `StableRef` or parseable strings.

`parent_span_id`
Optional parent span identifier.

**Returns:** `SpanEmission`

**Notes:**

- timestamps are normalized through `normalize_timestamp`
- `to_dict()` returns a transport-friendly normalized mapping

---

### `ArtifactRegistrationEmission`

```python
@dataclass(frozen=True, slots=True)
class ArtifactRegistrationEmission:
    artifact_kind: str
    path: str
    artifact_ref: StableRef | str | None = None
    attributes: Mapping[str, Any] | None = None
    compute_hash: bool = True
    allow_missing: bool = False
```

**Parameters:**

`artifact_kind`
Lower-snake artifact kind token.

`path`
Non-blank filesystem path string.

`artifact_ref`
Optional explicit artifact reference. May be `StableRef`, parseable string, or `None`.

`attributes`
JSON-safe artifact attributes.

`compute_hash`
When `True`, compute a content hash during registration.

`allow_missing`
When `True`, missing paths are allowed through registration planning.

**Returns:** `ArtifactRegistrationEmission`

**Notes:**

- `to_dict()` returns a transport-friendly normalized mapping

---

### `Delivery`

```python
@dataclass(frozen=True, slots=True)
class Delivery:
    sink_name: str
    family: PayloadFamily | str
    status: DeliveryStatus | str
    detail: str = ""
    metadata: Mapping[str, Any] | None = None
```

**Parameters:**

`sink_name`
Non-blank sink identifier.

`family`
Payload family for the delivered item.

`status`
Per-sink delivery status.

`detail`
Optional free-text detail string.

`metadata`
Optional delivery metadata mapping.

**Returns:** `Delivery`

---

### `CaptureResult`

```python
@dataclass(frozen=True, slots=True)
class CaptureResult(OperationResult[Any]):
    family: PayloadFamily | str = PayloadFamily.RECORD
    deliveries: tuple[Delivery, ...] = ()
    warnings: tuple[str, ...] = ()
    degradation_reasons: tuple[str, ...] = ()
    payload: Any | None = None
    degradation_emitted: bool = False
    degradation_payload: Any | None = None
    recovered_to_outbox: bool = False
    replay_refs: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = None
```

**Parameters:**

`family`
Capture payload family.

`deliveries`
Per-sink delivery outcomes.

`warnings`
Warning strings appended to the result message stream.

`degradation_reasons`
Reason strings used to populate degradation notes.

`payload`
Primary payload for the result. Must match `value` when both are provided through the inherited base.

`degradation_emitted`
Whether a degradation payload was emitted.

`degradation_payload`
Optional degradation payload. Requires `degradation_emitted=True`.

`recovered_to_outbox`
Whether the failed capture was recovered into the replay outbox.

`replay_refs`
Replay reference strings associated with the outbox recovery.

`error_code`
Optional explicit error code.

`error_message`
Optional explicit error message.

**Returns:** `CaptureResult`

**Notes:**

- inherits status, messages, degradation notes, failure, metadata, `applied`, and `planned_only` from `OperationResult`
- `success`, `with_degradation`, and `failure_result` are classmethod constructors
- `to_dict()` returns a transport-friendly mapping

---

### `BatchCaptureResult`

```python
@dataclass(frozen=True, slots=True)
class BatchCaptureResult(BatchResult[CaptureResult]):
    family: PayloadFamily | str = PayloadFamily.RECORD
```

**Parameters:**

`family`
Shared payload family for every result in the batch.

**Returns:** `BatchCaptureResult`

**Notes:**

- `results` is a capture-specific alias for `items`
- `from_results()` and `aggregate()` derive canonical batch status from the contained `CaptureResult` values
- `to_dict()` returns a transport-friendly mapping

---

## `contexta.config` model classes

### `WorkspaceConfig`

```python
@dataclass(frozen=True, slots=True)
class WorkspaceConfig:
    root_path: Path = Path(".contexta")
    metadata_path: Path | None = None
    records_path: Path | None = None
    artifacts_path: Path | None = None
    reports_path: Path | None = None
    exports_path: Path | None = None
    cache_path: Path | None = None
    create_missing_dirs: bool = True
```

**Parameters:**

`root_path`
Workspace root path.

`metadata_path`
Metadata plane path. Defaults to `<root_path>/metadata`.

`records_path`
Record plane path. Defaults to `<root_path>/records`.

`artifacts_path`
Artifact plane path. Defaults to `<root_path>/artifacts`.

`reports_path`
Report output path. Defaults to `<root_path>/reports`.

`exports_path`
Export output path. Defaults to `<root_path>/exports`.

`cache_path`
Cache path. Defaults to `<root_path>/cache`.

`create_missing_dirs`
Whether workspace creation should create missing directories.

**Returns:** `WorkspaceConfig`

---

### `ContractConfig`

```python
@dataclass(frozen=True, slots=True)
class ContractConfig:
    schema_version: str = "1.0.0"
    validation_mode: Literal["strict", "lenient"] = "strict"
    compatibility_mode: Literal["strict", "lenient"] = "strict"
    deterministic_serialization: bool = True
```

**Returns:** `ContractConfig`

---

### `CaptureConfig`

```python
@dataclass(frozen=True, slots=True)
class CaptureConfig:
    producer_ref: str = "sdk.python.local"
    capture_environment_snapshot: bool = True
    capture_installed_packages: bool = True
    capture_code_revision: bool = True
    capture_config_snapshot: bool = True
    retry_attempts: int = 0
    retry_backoff_seconds: float = 0.0
    dispatch_failure_mode: Literal["raise", "outbox"] = "raise"
    write_degraded_marker_on_partial_failure: bool = True
```

**Returns:** `CaptureConfig`

---

### `MetadataStoreConfig`

```python
@dataclass(frozen=True, slots=True)
class MetadataStoreConfig:
    storage_adapter: str = "duckdb"
    database_path: Path | None = None
    auto_create: bool = True
    read_only: bool = False
    auto_migrate: bool = False
```

**Returns:** `MetadataStoreConfig`

---

### `RecordStoreConfig`

```python
@dataclass(frozen=True, slots=True)
class RecordStoreConfig:
    root_path: Path | None = None
    max_segment_bytes: int = 1_048_576
    durability_mode: Literal["flush", "fsync"] = "fsync"
    layout_mode: Literal["jsonl_segments"] = "jsonl_segments"
    layout_version: str = "1"
    enable_indexes: bool = True
    read_only: bool = False
```

**Returns:** `RecordStoreConfig`

---

### `ArtifactStoreConfig`

```python
@dataclass(frozen=True, slots=True)
class ArtifactStoreConfig:
    root_path: Path | None = None
    default_ingest_mode: Literal["copy", "move", "adopt"] = "copy"
    verification_mode: Literal["none", "stored", "manifest_if_available", "strict"] = "manifest_if_available"
    create_missing_dirs: bool = True
    layout_version: str = "v1"
    chunk_size_bytes: int = 1_048_576
    read_only: bool = False
```

**Returns:** `ArtifactStoreConfig`

---

### `ComparisonPolicy`

```python
@dataclass(frozen=True, slots=True)
class ComparisonPolicy:
    metric_selection: Literal["latest", "max", "min", "mean"] = "latest"
    include_unchanged_metrics: bool = False
    missing_stage_severity: Literal["info", "warning", "error"] = "warning"
```

**Returns:** `ComparisonPolicy`

---

### `DiagnosticsPolicy`

```python
@dataclass(frozen=True, slots=True)
class DiagnosticsPolicy:
    require_metrics_for_completed_stages: bool = True
    detect_degraded_records: bool = True
    expected_terminal_stage_names: tuple[str, ...] = ("evaluate", "package")
```

**Returns:** `DiagnosticsPolicy`

---

### `ReportPolicy`

```python
@dataclass(frozen=True, slots=True)
class ReportPolicy:
    include_completeness_notes: bool = True
    include_lineage_summary: bool = True
    include_evidence_summary: bool = True
```

**Returns:** `ReportPolicy`

---

### `SearchPolicy`

```python
@dataclass(frozen=True, slots=True)
class SearchPolicy:
    default_limit: int = 50
    text_match_fields: tuple[str, ...] = ("name", "tags", "status")
    case_sensitive: bool = False
```

**Returns:** `SearchPolicy`

---

### `TrendPolicy`

```python
@dataclass(frozen=True, slots=True)
class TrendPolicy:
    default_window_runs: int = 20
    metric_aggregation: Literal["latest", "max", "min", "mean"] = "latest"
```

**Returns:** `TrendPolicy`

---

### `AnomalyPolicy`

```python
@dataclass(frozen=True, slots=True)
class AnomalyPolicy:
    z_score_threshold: float = 2.5
    min_baseline_runs: int = 3
    monitored_metrics: tuple[str, ...] = ()
```

**Returns:** `AnomalyPolicy`

---

### `AlertPolicy`

```python
@dataclass(frozen=True, slots=True)
class AlertPolicy:
    stop_on_first_trigger: bool = False
    default_severity: Literal["info", "warning", "error"] = "warning"
```

**Returns:** `AlertPolicy`

---

### `InterpretationConfig`

```python
@dataclass(frozen=True, slots=True)
class InterpretationConfig:
    comparison: ComparisonPolicy = field(default_factory=ComparisonPolicy)
    diagnostics: DiagnosticsPolicy = field(default_factory=DiagnosticsPolicy)
    reports: ReportPolicy = field(default_factory=ReportPolicy)
    search: SearchPolicy = field(default_factory=SearchPolicy)
    trend: TrendPolicy = field(default_factory=TrendPolicy)
    anomaly: AnomalyPolicy = field(default_factory=AnomalyPolicy)
    alert: AlertPolicy = field(default_factory=AlertPolicy)
```

**Returns:** `InterpretationConfig`

---

### `RecoveryConfig`

```python
@dataclass(frozen=True, slots=True)
class RecoveryConfig:
    outbox_root: Path | None = None
    backup_root: Path | None = None
    restore_staging_root: Path | None = None
    replay_mode_default: Literal["strict", "tolerant"] = "tolerant"
    require_plan_before_apply: bool = True
    create_backup_before_restore: bool = True
```

**Returns:** `RecoveryConfig`

---

### `CLIConfig`

```python
@dataclass(frozen=True, slots=True)
class CLIConfig:
    default_output_format: Literal["text", "json"] = "text"
    verbosity: Literal["quiet", "normal", "debug", "forensic"] = "normal"
    color: bool = True
```

**Returns:** `CLIConfig`

---

### `HTTPConfig`

```python
@dataclass(frozen=True, slots=True)
class HTTPConfig:
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8765
    open_browser: bool = False
```

**Returns:** `HTTPConfig`

---

### `HTMLConfig`

```python
@dataclass(frozen=True, slots=True)
class HTMLConfig:
    enabled: bool = True
    inline_charts: bool = True
```

**Returns:** `HTMLConfig`

---

### `NotebookConfig`

```python
@dataclass(frozen=True, slots=True)
class NotebookConfig:
    enabled: bool = True
```

**Returns:** `NotebookConfig`

---

### `ExportSurfaceConfig`

```python
@dataclass(frozen=True, slots=True)
class ExportSurfaceConfig:
    csv_delimiter: str = ","
    html_inline_charts: bool = True
    include_completeness_notes: bool = True
```

**Returns:** `ExportSurfaceConfig`

---

### `SurfaceConfig`

```python
@dataclass(frozen=True, slots=True)
class SurfaceConfig:
    cli: CLIConfig = field(default_factory=CLIConfig)
    http: HTTPConfig = field(default_factory=HTTPConfig)
    html: HTMLConfig = field(default_factory=HTMLConfig)
    notebook: NotebookConfig = field(default_factory=NotebookConfig)
    export: ExportSurfaceConfig = field(default_factory=ExportSurfaceConfig)
```

**Returns:** `SurfaceConfig`

---

### `RetentionConfig`

```python
@dataclass(frozen=True, slots=True)
class RetentionConfig:
    cache_ttl_days: int | None = 7
    report_ttl_days: int | None = None
    export_ttl_days: int | None = None
    artifact_retention_mode: Literal["manual", "planned", "enforced"] = "manual"
    records_compaction_enabled: bool = False
```

**Returns:** `RetentionConfig`

---

### `SecurityConfig`

```python
@dataclass(frozen=True, slots=True)
class SecurityConfig:
    redaction_mode: Literal["safe_default", "strict", "off"] = "safe_default"
    environment_variable_allowlist: tuple[str, ...] = ()
    secret_key_patterns: tuple[str, ...] = ("token", "secret", "password", "passwd", "key")
    allow_unredacted_local_exports: bool = False
    encryption_provider: str | None = None
```

**Returns:** `SecurityConfig`

---

### `UnifiedConfig`

```python
@dataclass(frozen=True, slots=True)
class UnifiedConfig:
    config_version: str = "1"
    profile_name: ProfileName = "local"
    project_name: str = "default"
    workspace: WorkspaceConfig = field(default_factory=WorkspaceConfig)
    contract: ContractConfig = field(default_factory=ContractConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    metadata: MetadataStoreConfig = field(default_factory=MetadataStoreConfig)
    records: RecordStoreConfig = field(default_factory=RecordStoreConfig)
    artifacts: ArtifactStoreConfig = field(default_factory=ArtifactStoreConfig)
    interpretation: InterpretationConfig = field(default_factory=InterpretationConfig)
    recovery: RecoveryConfig = field(default_factory=RecoveryConfig)
    surfaces: SurfaceConfig = field(default_factory=SurfaceConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
```

**Parameters:**

`config_version`
Root config version string.

`profile_name`
Resolved built-in profile name.

`project_name`
Default project name.

`workspace`
Workspace and derived path configuration.

`contract`
Contract policy configuration.

`capture`
Capture/runtime configuration.

`metadata`
Metadata truth-plane configuration.

`records`
Record truth-plane configuration.

`artifacts`
Artifact truth-plane configuration.

`interpretation`
Interpretation-layer configuration.

`recovery`
Recovery configuration.

`surfaces`
Delivery-surface configuration.

`retention`
Retention configuration.

`security`
Security and redaction configuration.

**Returns:** `UnifiedConfig`

**Notes:**

- `__post_init__()` derives default metadata, record, artifact, and recovery paths from `workspace`

---

## `contexta.contract` additional validation functions

### `validate_project`

```python
contexta.contract.validate_project(
    project: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**Parameters:**

`project`
`Project` instance to validate.

`registry`
Optional extension registry used for extension validation.

**Returns:** `ValidationReport`

---

### `validate_stage_execution`

```python
contexta.contract.validate_stage_execution(
    stage: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**Parameters:**

`stage`
`StageExecution` instance to validate.

`registry`
Optional extension registry used for extension validation.

**Returns:** `ValidationReport`

---

### `validate_operation_context`

```python
contexta.contract.validate_operation_context(
    operation: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**Parameters:**

`operation`
`OperationContext` instance to validate.

`registry`
Optional extension registry used for extension validation.

**Returns:** `ValidationReport`

---

### `validate_environment_snapshot`

```python
contexta.contract.validate_environment_snapshot(
    snapshot: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**Parameters:**

`snapshot`
`EnvironmentSnapshot` instance to validate.

`registry`
Optional extension registry used for extension validation.

**Returns:** `ValidationReport`

---

### `validate_record_envelope`

```python
contexta.contract.validate_record_envelope(
    envelope: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**Parameters:**

`envelope`
`RecordEnvelope` instance to validate.

`registry`
Optional extension registry used for extension validation.

**Returns:** `ValidationReport`

---

### `validate_structured_event_record`

```python
contexta.contract.validate_structured_event_record(
    record: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**Parameters:**

`record`
`StructuredEventRecord` instance to validate.

`registry`
Optional extension registry used for envelope validation.

**Returns:** `ValidationReport`

---

### `validate_trace_span_record`

```python
contexta.contract.validate_trace_span_record(
    record: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**Parameters:**

`record`
`TraceSpanRecord` instance to validate.

`registry`
Optional extension registry used for envelope validation.

**Returns:** `ValidationReport`

---

### `validate_degraded_record`

```python
contexta.contract.validate_degraded_record(
    record: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**Parameters:**

`record`
`DegradedRecord` instance to validate.

`registry`
Optional extension registry used for envelope validation.

**Returns:** `ValidationReport`

---

### `validate_artifact_manifest`

```python
contexta.contract.validate_artifact_manifest(
    manifest: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**Parameters:**

`manifest`
`ArtifactManifest` instance to validate.

`registry`
Optional extension registry used for extension validation.

**Returns:** `ValidationReport`

**Notes:**

- emits warnings when `hash_value` or `size_bytes` is missing

---

### `validate_lineage_edge`

```python
contexta.contract.validate_lineage_edge(
    edge: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**Parameters:**

`edge`
`LineageEdge` instance to validate.

`registry`
Optional extension registry used for extension validation.

**Returns:** `ValidationReport`

**Notes:**

- emits warnings when `evidence_refs` is empty

---

### `validate_provenance_record`

```python
contexta.contract.validate_provenance_record(
    record: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**Parameters:**

`record`
`ProvenanceRecord` instance to validate.

`registry`
Optional extension registry used for extension validation.

**Returns:** `ValidationReport`

**Notes:**

- emits warnings when `policy_ref` or `evidence_bundle_ref` is missing

---

### `validate_extension_field_set`

```python
contexta.contract.validate_extension_field_set(
    ext: Any,
    *,
    target_model: str,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**Parameters:**

`ext`
`ExtensionFieldSet` instance to validate.

`target_model`
Target canonical model name for the extension namespace.

`registry`
Extension registry used to resolve the namespace and allowed target models.

**Returns:** `ValidationReport`
