"""Public Contexta facade implementation."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any, Mapping, Sequence

from ..capture import (
    ArtifactRegistrationEmission,
    BatchCaptureResult,
    CaptureDispatcher,
    CaptureResult,
    EventEmission,
    MetricEmission,
    Sink,
    SpanEmission,
)
from ..config import UnifiedConfig, load_config
from ..interpretation import (
    AlertRule,
    AlertService,
    BatchRecord,
    CompareService,
    DeploymentRecord,
    DiagnosticsService,
    LineageService,
    MetricCondition,
    MultiRunComparison,
    ProvenanceService,
    QueryService,
    ReportBuilder,
    ReportComparison,
    ReportDocument,
    RunComparison,
    RunListQuery,
    RunSnapshot,
    SampleRecord,
    TimeRange,
    TrendService,
)
from ..runtime import RuntimeSession
from ..store.artifacts import ArtifactStore, VaultConfig
from ..store.metadata import MetadataStore, MetadataStoreConfig
from ..store.records import RecordStore, StoreConfig
from ..interpretation.repositories import CompositeStoreRepository


def _detect_version() -> str:
    for distribution_name in ("contexta",):
        try:
            return version(distribution_name)
        except PackageNotFoundError:
            continue
    return "0.1.0"


class Contexta:
    """Public facade bound to resolved config and a runtime session."""

    __slots__ = (
        "workspace",
        "profile",
        "config",
        "_dispatcher",
        "_session",
        "_metadata_store",
        "_record_store",
        "_artifact_store",
        "_repository",
        "_query_service",
        "_compare_service",
        "_diagnostics_service",
        "_lineage_service",
        "_trend_service",
        "_alert_service",
        "_provenance_service",
        "_report_builder",
        "_notebook",
    )

    def __init__(
        self,
        *,
        workspace: str = ".contexta",
        profile: str | None = None,
        config: UnifiedConfig | Mapping[str, object] | None = None,
        sinks: Sequence[Sink] | None = None,
    ) -> None:
        if isinstance(config, UnifiedConfig):
            resolved = config
        else:
            resolved = load_config(profile=profile, workspace=workspace, config=config)
        self.workspace = str(resolved.workspace.root_path)
        self.profile = resolved.profile_name
        self.config = resolved
        self._dispatcher = CaptureDispatcher.with_default_local_sink(config=resolved, sinks=sinks)
        self._session = RuntimeSession(config=resolved, dispatcher=self._dispatcher)
        self._metadata_store = None
        self._record_store = None
        self._artifact_store = None
        self._repository = None
        self._query_service = None
        self._compare_service = None
        self._diagnostics_service = None
        self._lineage_service = None
        self._trend_service = None
        self._alert_service = None
        self._provenance_service = None
        self._report_builder = None
        self._notebook = None

    @classmethod
    def open(
        cls,
        *,
        workspace: str = ".contexta",
        profile: str | None = None,
        config: UnifiedConfig | Mapping[str, object] | None = None,
        sinks: Sequence[Sink] | None = None,
    ) -> "Contexta":
        return cls(workspace=workspace, profile=profile, config=config, sinks=sinks)

    @property
    def project_name(self) -> str:
        return self.config.project_name

    @property
    def session(self) -> RuntimeSession:
        return self._session

    @property
    def sinks(self) -> tuple[Sink, ...]:
        return self._dispatcher.sinks

    def run(
        self,
        name: str,
        *,
        run_id: str | None = None,
        tags: Mapping[str, str] | None = None,
        metadata: Mapping[str, Any] | None = None,
        code_revision: str | None = None,
        config_snapshot: Mapping[str, Any] | None = None,
        dataset_ref: str | None = None,
    ) -> Any:
        return self._session.start_run(
            name,
            run_id=run_id,
            tags=tags,
            metadata=metadata,
            code_revision=code_revision,
            config_snapshot=config_snapshot,
            dataset_ref=dataset_ref,
        )

    def current_run(self) -> Any:
        return self._session.current_run()

    def current_stage(self) -> Any:
        return self._session.current_stage()

    def current_deployment(self) -> Any:
        return self._session.current_deployment()

    def current_operation(self) -> Any:
        return self._session.current_operation()

    def current_sample(self) -> Any:
        return self._session.current_sample()

    def deployment(
        self,
        name: str,
        *,
        deployment_ref: str | None = None,
        run_ref: str | None = None,
        artifact_ref: str | None = None,
        environment_snapshot_ref: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        return self._session.start_deployment(
            name,
            deployment_ref=deployment_ref,
            run_ref=run_ref,
            artifact_ref=artifact_ref,
            environment_snapshot_ref=environment_snapshot_ref,
            metadata=metadata,
        )

    def event(
        self,
        key: str,
        *,
        message: str,
        level: str = "info",
        attributes: Mapping[str, Any] | None = None,
        tags: Mapping[str, str] | None = None,
    ) -> CaptureResult:
        return self._session.event(key, message=message, level=level, attributes=attributes, tags=tags)

    def emit_events(self, emissions: Sequence[EventEmission | Mapping[str, Any]]) -> BatchCaptureResult:
        return self._session.emit_events(emissions)

    def metric(
        self,
        key: str,
        value: Any,
        *,
        unit: str | None = None,
        aggregation_scope: str = "step",
        tags: Mapping[str, str] | None = None,
        summary_basis: str = "raw_observation",
    ) -> CaptureResult:
        return self._session.metric(
            key,
            value,
            unit=unit,
            aggregation_scope=aggregation_scope,
            tags=tags,
            summary_basis=summary_basis,
        )

    def emit_metrics(self, emissions: Sequence[MetricEmission | Mapping[str, Any]]) -> BatchCaptureResult:
        return self._session.emit_metrics(emissions)

    def span(
        self,
        name: str,
        *,
        started_at: str | None = None,
        ended_at: str | None = None,
        status: str = "ok",
        span_kind: str = "operation",
        attributes: Mapping[str, Any] | None = None,
        linked_refs: Sequence[str] | None = None,
        parent_span_id: str | None = None,
    ) -> CaptureResult:
        return self._session.span(
            name,
            started_at=started_at,
            ended_at=ended_at,
            status=status,
            span_kind=span_kind,
            attributes=attributes,
            linked_refs=linked_refs,
            parent_span_id=parent_span_id,
        )

    def emit_spans(self, emissions: Sequence[SpanEmission | Mapping[str, Any]]) -> BatchCaptureResult:
        return self._session.emit_spans(emissions)

    def register_artifact(
        self,
        artifact_kind: str,
        path: str,
        *,
        artifact_ref: str | None = None,
        attributes: Mapping[str, Any] | None = None,
        compute_hash: bool = True,
        allow_missing: bool = False,
    ) -> CaptureResult:
        return self._session.register_artifact(
            artifact_kind,
            path,
            artifact_ref=artifact_ref,
            attributes=attributes,
            compute_hash=compute_hash,
            allow_missing=allow_missing,
        )

    def register_artifacts(
        self,
        emissions: Sequence[ArtifactRegistrationEmission | Mapping[str, Any]],
    ) -> BatchCaptureResult:
        return self._session.register_artifacts(emissions)

    @property
    def metadata_store(self) -> MetadataStore:
        if self._metadata_store is None:
            self._metadata_store = MetadataStore(
                MetadataStoreConfig.from_unified_config(self.config)
            )
        return self._metadata_store

    @property
    def record_store(self) -> RecordStore:
        if self._record_store is None:
            self._record_store = RecordStore(StoreConfig.from_unified_config(self.config))
        return self._record_store

    @property
    def artifact_store(self) -> ArtifactStore:
        if self._artifact_store is None:
            self._artifact_store = ArtifactStore(VaultConfig.from_unified_config(self.config))
        return self._artifact_store

    @property
    def repository(self) -> CompositeStoreRepository:
        if self._repository is None:
            self._repository = CompositeStoreRepository(
                metadata_store=self.metadata_store,
                record_store=self.record_store,
                artifact_store=self.artifact_store,
            )
        return self._repository

    @property
    def query_service(self) -> QueryService:
        if self._query_service is None:
            self._query_service = QueryService(self.repository)
        return self._query_service

    @property
    def compare_service(self) -> CompareService:
        if self._compare_service is None:
            self._compare_service = CompareService(
                self.query_service,
                config=self.config.interpretation.comparison,
            )
        return self._compare_service

    @property
    def diagnostics_service(self) -> DiagnosticsService:
        if self._diagnostics_service is None:
            self._diagnostics_service = DiagnosticsService(
                self.query_service,
                config=self.config.interpretation.diagnostics,
            )
        return self._diagnostics_service

    @property
    def lineage_service(self) -> LineageService:
        if self._lineage_service is None:
            self._lineage_service = LineageService(self.query_service)
        return self._lineage_service

    @property
    def trend_service(self) -> TrendService:
        if self._trend_service is None:
            self._trend_service = TrendService(
                self.query_service,
                config=self.config.interpretation.trend,
            )
        return self._trend_service

    @property
    def alert_service(self) -> AlertService:
        if self._alert_service is None:
            self._alert_service = AlertService(
                self.query_service,
                metric_aggregation=self.config.interpretation.trend.metric_aggregation,
            )
        return self._alert_service

    @property
    def provenance_service(self) -> ProvenanceService:
        if self._provenance_service is None:
            self._provenance_service = ProvenanceService(self.query_service)
        return self._provenance_service

    @property
    def report_builder(self) -> ReportBuilder:
        if self._report_builder is None:
            self._report_builder = ReportBuilder()
        return self._report_builder

    @property
    def notebook(self) -> Any:
        if self._notebook is None:
            from ..surfaces.notebook.surface import NotebookSurface
            self._notebook = NotebookSurface(self)
        return self._notebook

    def list_projects(self) -> tuple[str, ...]:
        return self.query_service.list_projects()

    def list_runs(
        self,
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
    ) -> tuple[Any, ...]:
        effective_query = query
        if effective_query is None and (
            status is not None
            or tags is not None
            or metric_conditions
            or time_range is not None
            or limit is not None
            or offset != 0
            or sort_by != "started_at"
            or sort_desc is not True
        ):
            effective_query = RunListQuery(
                project_name=project_name,
                status=status,
                tags=None if tags is None else dict(tags),
                metric_conditions=tuple(metric_conditions),
                time_range=time_range,
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_desc=sort_desc,
            )
            project_name = None
        return self.query_service.list_runs(project_name, query=effective_query)

    def list_deployments(
        self,
        project_name: str | None = None,
        run_id: str | None = None,
    ) -> tuple[DeploymentRecord, ...]:
        return self.query_service.list_deployments(project_name, run_id)

    def list_batches(
        self,
        run_id: str,
        stage_id: str | None = None,
    ) -> tuple[BatchRecord, ...]:
        return self.query_service.list_batches(run_id, stage_id)

    def list_samples(
        self,
        run_id: str,
        stage_id: str | None = None,
        batch_id: str | None = None,
    ) -> tuple[SampleRecord, ...]:
        return self.query_service.list_samples(run_id, stage_id, batch_id)

    def get_run_snapshot(self, run_id: str) -> RunSnapshot:
        return self.query_service.get_run_snapshot(run_id)

    def get_provenance(self, run_id: str) -> Any:
        return self.get_run_snapshot(run_id).provenance

    def get_artifact_origin(self, artifact_ref: str) -> RunSnapshot | None:
        return self.query_service.get_artifact_origin(artifact_ref)

    def compare_runs(self, left_run_id: str, right_run_id: str) -> RunComparison:
        return self.compare_service.compare_runs(left_run_id, right_run_id)

    def compare_multiple_runs(self, run_ids: Sequence[str]) -> MultiRunComparison:
        return self.compare_service.compare_multiple_runs(run_ids)

    def compare_report_documents(self, left: object, right: object) -> ReportComparison:
        return self.compare_service.compare_report_documents(left, right)

    def select_best_run(
        self,
        run_ids: Sequence[str],
        metric_key: str,
        *,
        stage_name: str | None = None,
        higher_is_better: bool = True,
    ) -> str | None:
        return self.compare_service.select_best_run(
            run_ids,
            metric_key,
            stage_name=stage_name,
            higher_is_better=higher_is_better,
        )

    def diagnose_run(self, run_id: str) -> Any:
        return self.diagnostics_service.diagnose_run(run_id)

    def traverse_lineage(
        self,
        subject_ref: str,
        *,
        direction: str | None = None,
        max_depth: int | None = None,
    ) -> Any:
        return self.lineage_service.traverse_lineage(
            subject_ref,
            direction=direction,
            max_depth=max_depth,
        )

    def get_metric_trend(
        self,
        metric_key: str,
        *,
        project_name: str | None = None,
        stage_name: str | None = None,
        query: RunListQuery | None = None,
    ) -> Any:
        return self.trend_service.get_metric_trend(
            metric_key,
            project_name=project_name,
            stage_name=stage_name,
            query=query,
        )

    def get_step_series(
        self,
        run_id: str,
        metric_key: str,
        *,
        stage_id: str | None = None,
        stage_name: str | None = None,
    ) -> Any:
        effective_stage_id = stage_id
        if effective_stage_id is None and stage_name is not None:
            snapshot = self.get_run_snapshot(run_id)
            matched = next((stage for stage in snapshot.stages if stage.name == stage_name), None)
            effective_stage_id = None if matched is None else matched.stage_id
        return self.trend_service.get_step_series(run_id, metric_key, stage_id=effective_stage_id)

    def get_stage_duration_trend(
        self,
        stage_name: str,
        *,
        project_name: str | None = None,
        query: RunListQuery | None = None,
    ) -> Any:
        return self.trend_service.get_stage_duration_trend(
            stage_name,
            project_name=project_name,
            query=query,
        )

    def get_artifact_size_trend(
        self,
        artifact_kind: str,
        *,
        project_name: str | None = None,
        query: RunListQuery | None = None,
    ) -> Any:
        return self.trend_service.get_artifact_size_trend(
            artifact_kind,
            project_name=project_name,
            query=query,
        )

    def evaluate_alerts(
        self,
        run_id: str,
        rules: Sequence[AlertRule],
    ) -> tuple[Any, ...]:
        return self.alert_service.evaluate_alerts(run_id, list(rules))

    def evaluate_alerts_fleet(
        self,
        rules: Sequence[AlertRule],
        *,
        project_name: str | None = None,
        query: RunListQuery | None = None,
    ) -> Any:
        return self.alert_service.evaluate_alerts_fleet(list(rules), project_name=project_name, query=query)

    def audit_reproducibility(self, run_id: str) -> Any:
        return self.provenance_service.audit_reproducibility(run_id)

    def compare_environments(self, left_run_id: str, right_run_id: str) -> Any:
        return self.provenance_service.compare_environments(left_run_id, right_run_id)

    def build_snapshot_report(self, run_id: str) -> ReportDocument:
        snapshot = self.get_run_snapshot(run_id)
        diagnostics = self.diagnose_run(run_id)
        return self.report_builder.build_snapshot_report(snapshot, diagnostics)

    def build_run_report(self, left_run_id: str, right_run_id: str) -> ReportDocument:
        comparison = self.compare_runs(left_run_id, right_run_id)
        diagnostics = self.diagnose_run(left_run_id)
        return self.report_builder.build_run_report(comparison, diagnostics)

    def build_project_summary_report(self, project_name: str) -> ReportDocument:
        runs = self.list_runs(project_name)
        notes = ()
        if not runs:
            from ..interpretation import CompletenessNote

            notes = (CompletenessNote(severity="info", summary="project_runs_empty", details={"project_name": project_name}),)
        return self.report_builder.build_project_summary_report(project_name, runs=tuple(runs), notes=notes)

    def build_trend_report(
        self,
        metric_key: str,
        *,
        project_name: str | None = None,
        stage_name: str | None = None,
        query: RunListQuery | None = None,
    ) -> ReportDocument:
        trend = self.get_metric_trend(
            metric_key,
            project_name=project_name,
            stage_name=stage_name,
            query=query,
        )
        return self.report_builder.build_trend_report(trend)

    def build_alert_report(self, run_id: str, rules: Sequence[AlertRule]) -> ReportDocument:
        results = self.evaluate_alerts(run_id, rules)
        return self.report_builder.build_alert_report(results)

    def build_multi_run_report(self, run_ids: Sequence[str]) -> ReportDocument:
        comparison = self.compare_multiple_runs(run_ids)
        return self.report_builder.build_multi_run_report(comparison)


__version__ = _detect_version()


__all__ = ["Contexta", "__version__"]
