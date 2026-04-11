# Contexta API 레퍼런스

이 페이지는 `Contexta`의 현재 공용 Python API 인터페이스에 대해 문서화합니다.

이 레퍼런스는 표준 공용 임포트 위치와 현재 저장소 상태를 기준으로 작성되었습니다.

## 이 레퍼런스의 범위

이 페이지에서 다루는 내용:

- `Contexta` 퍼사드(facade)
- 공용 `contexta.config` 함수 및 모델 클래스
- 공용 `contexta.contract` 직렬화 및 검증 함수
- 공용 `contexta.capture` 방출(emission) 및 결과 모델
- 공용 `contexta.interpretation` 서비스 클래스
- `contexta.*`를 통해 노출된 공용 스토어 및 복구 진입점

다루지 않는 내용:

- `contexta.api`, `contexta.runtime`, `contexta.common`, 또는 `contexta.surfaces` 하위의 내부 모듈
- 문서화되지 않은 딥 임포트(deep import) 경로
- 더 이상 사용되지 않는 레거시 shim 패키지 또는 마이그레이션 전용 프로토타입 아티팩트
- 현재 저장소에 존재하지 않는 가상의 API

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

모든 Contexta 작업의 기본 퍼사드입니다. 런타임 세션, 캡처 싱크(sink), 그리고 쿼리, 비교, 진단, 리니지, 추세, 알림, 리포트 워크플로를 위한 서비스 접근자(accessor)를 관리합니다.

**매개변수:**

`workspace`
Contexta 워크스페이스의 루트 디렉터리입니다. 현재 작업 디렉터리를 기준으로 해결됩니다.

`profile`
로드할 명명된 내장 프로필(`"local"`, `"test"` 등)입니다. `config`가 직접 제공되면 무시됩니다.

`config`
명시적인 설정 객체 또는 원시 매핑입니다. 제공될 경우, 설정 내부의 폴백 기본값인 경우를 제외하고 `workspace`와 `profile`은 무시됩니다.

`sinks`
세션에 연결할 캡처 싱크들입니다. `None`일 경우, 설정에서 싱크를 해결합니다.

**반환값:** `Contexta`

**참고:** `Contexta.open` — 대안적인 클래스 메서드 생성자입니다.

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

`Contexta(...)`를 위한 클래스 메서드 별칭입니다. 동작은 동일합니다.

---

### 속성 (Properties)

`Contexta.project_name` → `str`
설정에서 해결된 프로젝트 이름입니다.

`Contexta.session` → `RuntimeSession`
캡처 스코프(scope)를 지원하는 런타임 세션 객체입니다.

`Contexta.sinks` → `tuple[Sink, ...]`
구성된 캡처 싱크들입니다.

`Contexta.metadata_store` → `MetadataStore`
메타데이터 원본(Source of Truth) 스토어에 대한 직접 접근 권한입니다.

`Contexta.record_store` → `RecordStore`
레코드 원본(Source of Truth) 스토어에 대한 직접 접근 권한입니다.

`Contexta.artifact_store` → `ArtifactStore`
아티팩트 원본(Source of Truth) 스토어에 대한 직접 접근 권한입니다.

`Contexta.repository` → `CompositeStoreRepository`
모든 스토어에 걸친 복합 읽기 저장소(repository)입니다.

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

컨텍스트 매니저로 실행(run) 스코프를 엽니다. `with` 블록 내부의 모든 캡처 호출은 이 실행과 연관됩니다.

**매개변수:**

`name`
이 실행에 대한 사람이 읽기 좋은 이름입니다.

`run_id`
명시적 실행 ID입니다. `None`일 경우, 안정적인 ID가 자동으로 생성됩니다.

`tags`
실행 레코드에 연결된 키-값 문자열 태그입니다.

`metadata`
실행 레코드에 연결된 임의의 JSON 직렬화 가능한 메타데이터입니다.

`code_revision`
Git 커밋 SHA 또는 기타 코드 리비전 식별자입니다.

`config_snapshot`
이 실행에 사용된 설정의 스냅샷으로, 프로버넌스(provenance)로 첨부됩니다.

`dataset_ref`
이 실행의 주요 데이터셋을 식별하는 안정적인 참조 문자열입니다.

**예제:**

```python
with ctx.run("training", tags={"env": "prod"}) as run:
    ctx.metric("accuracy", 0.94)
```

---

### `Contexta.current_run`

```python
Contexta.current_run() -> RunScope | None
```

활성 상태의 `RunScope`를 반환하거나, 열린 실행 스코프가 없으면 `None`을 반환합니다.

---

### `Contexta.current_stage`

```python
Contexta.current_stage() -> StageScope | None
```

활성 상태의 `StageScope`를 반환하거나, 열린 스테이지 스코프가 없으면 `None`을 반환합니다.

---

### `Contexta.current_operation`

```python
Contexta.current_operation() -> OperationScope | None
```

활성 상태의 `OperationScope`를 반환하거나, 열린 작업(operation) 스코프가 없으면 `None`을 반환합니다.

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

현재 스코프에 단일 구조화된 이벤트를 방출합니다.

**매개변수:**

`key`
점으로 구분된 이벤트 키입니다(예: `"training.epoch_complete"`).

`message`
사람이 읽기 좋은 이벤트 메시지입니다.

`level`
심각도 레벨입니다. `"debug"`, `"info"`, `"warning"`, `"error"` 중 하나입니다.

`attributes`
이벤트에 첨부된 임의의 JSON 직렬화 가능한 구조화된 필드입니다.

`tags`
필터링 및 그룹화를 위한 키-값 문자열 태그입니다.

**반환값:** `CaptureResult`

---

### `Contexta.emit_events`

```python
Contexta.emit_events(
    emissions: Sequence[EventEmission | Mapping[str, Any]],
) -> BatchCaptureResult
```

여러 이벤트를 일괄 방출합니다. 각 요소는 `EventEmission` 인스턴스이거나 동일한 필드를 가진 원시 매핑일 수 있습니다.

**반환값:** `BatchCaptureResult`

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

현재 스코프에 단일 메트릭 관측치를 방출합니다.

**매개변수:**

`key`
점으로 구분된 메트릭 키입니다(예: `"train.loss"`).

`value`
숫자 또는 구조화된 메트릭 값입니다.

`unit`
선택적 단위 라벨입니다(예: `"seconds"`, `"bytes"`).

`aggregation_scope`
다운스트림 집계를 위한 세분성(granularity) 힌트입니다. `"step"`, `"stage"`, `"run"` 중 하나입니다.

`tags`
필터링 및 그룹화를 위한 키-값 문자열 태그입니다.

`summary_basis`
요약 계산을 위한 기준입니다. `"raw_observation"`, `"mean"`, `"max"`, `"min"`, `"last"` 중 하나입니다.

**반환값:** `CaptureResult`

---

### `Contexta.emit_metrics`

```python
Contexta.emit_metrics(
    emissions: Sequence[MetricEmission | Mapping[str, Any]],
) -> BatchCaptureResult
```

여러 메트릭을 일괄 방출합니다.

**반환값:** `BatchCaptureResult`

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

현재 스코프에 단일 트레이스 스팬(trace span)을 방출합니다.

**매개변수:**

`name`
사람이 읽기 좋은 스팬 이름입니다.

`started_at`
ISO 8601 타임스탬프 문자열입니다. 기본값은 이 호출 시간입니다.

`ended_at`
ISO 8601 타임스탬프 문자열입니다. 기본값은 이 호출 시간입니다.

`status`
스팬 상태입니다. `"ok"`, `"error"`, `"unset"` 중 하나입니다.

`span_kind`
이 스팬의 시맨틱 종류입니다. `"operation"`, `"stage"`, `"call"`, `"internal"` 중 하나입니다.

`attributes`
임의의 JSON 직렬화 가능한 구조화된 필드입니다.

`linked_refs`
이 스팬과 인과관계로 연결된 안정적인 참조 문자열들입니다.

`parent_span_id`
명시적 부모-자식 연결을 위한 부모 스팬 ID입니다.

**반환값:** `CaptureResult`

---

### `Contexta.emit_spans`

```python
Contexta.emit_spans(
    emissions: Sequence[SpanEmission | Mapping[str, Any]],
) -> BatchCaptureResult
```

여러 스팬을 일괄 방출합니다.

**반환값:** `BatchCaptureResult`

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

현재 스코프에 단일 아티팩트를 등록합니다.

**매개변수:**

`artifact_kind`
시맨틱 종류 라벨입니다(예: `"model"`, `"dataset"`, `"checkpoint"`).

`path`
아티팩트에 대한 파일 시스템 경로입니다. 아티팩트 스토어로 수집(ingest)됩니다.

`artifact_ref`
명시적인 안정적 참조 문자열입니다. `None`일 경우 자동으로 생성됩니다.

`attributes`
아티팩트 매니페스트에 첨부된 임의의 JSON 직렬화 가능한 메타데이터입니다.

`compute_hash`
`True`일 경우, 나중에 검증하기 위해 콘텐츠 해시를 계산하고 저장합니다.

`allow_missing`
`True`일 경우, `path`에 파일이 존재하지 않더라도 등록에 성공합니다.

**반환값:** `CaptureResult`

---

### `Contexta.register_artifacts`

```python
Contexta.register_artifacts(
    emissions: Sequence[ArtifactRegistrationEmission | Mapping[str, Any]],
) -> BatchCaptureResult
```

여러 아티팩트를 일괄 등록합니다.

**반환값:** `BatchCaptureResult`

---

### `Contexta.list_projects`

```python
Contexta.list_projects() -> tuple[str, ...]
```

메타데이터 스토어에 알려진 모든 프로젝트 이름을 반환합니다.

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

메타데이터 스토어에서 필터링 및 정렬된 실행 목록을 반환합니다.

**매개변수:**

`project_name`
이 프로젝트에 속한 실행으로 제한합니다. `None`일 경우 모든 프로젝트를 검색합니다.

`status`
실행 상태 문자열로 필터링합니다(예: `"completed"`, `"failed"`).

`tags`
정확한 태그 필터입니다. 제공된 모든 키-값 쌍을 가진 실행만 반환됩니다.

`metric_conditions`
저장된 메트릭 요약에 적용되는 `MetricCondition` 필터 시퀀스입니다.

`time_range`
주어진 `TimeRange` 내에 시작된 실행으로 제한합니다.

`limit`
반환할 실행의 최대 개수입니다.

`offset`
결과를 반환하기 전에 건너뛸 실행 개수입니다.

`sort_by`
정렬 기준 필드입니다. 일반적으로 `"started_at"` 또는 `"ended_at"`입니다.

`sort_desc`
`True`일 경우 최신순으로 반환합니다.

`query`
미리 작성된 `RunListQuery` 객체입니다. 제공될 경우 다른 모든 필터 인수는 무시됩니다.

**반환값:** 실행 요약 객체들의 `tuple`입니다.

---

### `Contexta.get_run_snapshot`

```python
Contexta.get_run_snapshot(run_id: str) -> RunSnapshot
```

레코드 및 아티팩트 증거를 포함하여 주어진 실행 ID에 대한 전체 `RunSnapshot`을 반환합니다.

**매개변수:**

`run_id`
실행의 안정적인 ID 문자열입니다.

**반환값:** `contexta.interpretation.RunSnapshot`

---

### `Contexta.get_provenance`

```python
Contexta.get_provenance(run_id: str) -> ProvenanceView
```

주어진 실행에 대한 `ProvenanceView`를 반환합니다.

---

### `Contexta.get_artifact_origin`

```python
Contexta.get_artifact_origin(artifact_ref: str) -> RunSnapshot | None
```

주어진 아티팩트를 생성한 실행의 `RunSnapshot`을 반환하거나, 모를 경우 `None`을 반환합니다.

---

### `Contexta.compare_runs`

```python
Contexta.compare_runs(left_run_id: str, right_run_id: str) -> RunComparison
```

두 실행을 나란히 비교합니다.

**반환값:** `RunComparison`

---

### `Contexta.compare_multiple_runs`

```python
Contexta.compare_multiple_runs(run_ids: Sequence[str]) -> MultiRunComparison
```

세 개 이상의 실행을 함께 비교합니다.

**반환값:** `MultiRunComparison`

---

### `Contexta.compare_report_documents`

```python
Contexta.compare_report_documents(left: ReportDocument, right: ReportDocument) -> ReportComparison
```

두 `ReportDocument` 객체 사이의 차이점(diff)을 생성합니다.

**반환값:** `ReportComparison`

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

`run_ids` 중에서 `metric_key` 값이 가장 좋은 실행 ID를 반환하거나, 조건에 맞는 실행이 없으면 `None`을 반환합니다.

**매개변수:**

`run_ids`
비교할 후보 실행 ID들입니다.

`metric_key`
순위를 매길 점으로 구분된 메트릭 키입니다.

`stage_name`
제공될 경우 메트릭 조회를 이 스테이지로 제한합니다.

`higher_is_better`
`True`일 경우 메트릭 값이 가장 높은 실행이 선택됩니다. `False`일 경우 가장 낮은 실행이 선택됩니다.

**반환값:** `str | None`

---

### `Contexta.diagnose_run`

```python
Contexta.diagnose_run(run_id: str) -> DiagnosticsResult
```

주어진 실행에 대해 진단 서비스를 실행하고 구조화된 조사 결과(structured findings)를 반환합니다.

**반환값:** `DiagnosticsResult`

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

`subject_ref`에서 시작하여 리니지 엣지(edge)를 따라 순회합니다.

**매개변수:**

`subject_ref`
시작점이 되는 아티팩트 또는 실행의 안정적인 참조 문자열입니다.

`direction`
순회 방향입니다. `"upstream"`, `"downstream"`, 또는 둘 다를 뜻하는 `None` 중 하나입니다.

`max_depth`
순회할 최대 엣지 깊이입니다. `None`은 무제한을 의미합니다.

**반환값:** `LineageTraversal`

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

실행들에 걸쳐 메트릭에 대한 시계열 추세 데이터를 반환합니다.

**반환값:** `MetricTrend`

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

단일 실행 내에서 메트릭에 대한 스텝(step) 수준의 시계열 데이터를 반환합니다.

**반환값:** `StepSeries`

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

실행들에 걸쳐 명명된 스테이지의 실제 시간(wall-clock) 소요 추세를 반환합니다.

**반환값:** `DurationTrend`

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

실행들에 걸쳐 주어진 아티팩트 종류의 크기 추세를 반환합니다.

**반환값:** `ArtifactSizeTrend`

---

### `Contexta.evaluate_alerts`

```python
Contexta.evaluate_alerts(
    run_id: str,
    rules: Sequence[AlertRule],
) -> tuple[AlertResult, ...]
```

단일 실행에 대해 알림 규칙을 평가합니다.

**반환값:** `tuple[AlertResult, ...]`

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

실행 집단(fleet)에 걸쳐 알림 규칙을 평가합니다.

**반환값:** `AlertReport`

---

### `Contexta.audit_reproducibility`

```python
Contexta.audit_reproducibility(run_id: str) -> ReproducibilityAudit
```

주어진 실행에 첨부된 재현성 증거를 감사(audit)합니다.

**반환값:** `ReproducibilityAudit`

---

### `Contexta.compare_environments`

```python
Contexta.compare_environments(left_run_id: str, right_run_id: str) -> EnvironmentDiff
```

두 실행의 환경 스냅샷 사이의 차이점(diff)을 생성합니다.

**반환값:** `EnvironmentDiff`

---

### `Contexta.build_snapshot_report`

```python
Contexta.build_snapshot_report(run_id: str) -> ReportDocument
```

단일 실행 스냅샷을 요약하는 `ReportDocument`를 빌드합니다.

**반환값:** `ReportDocument`

---

### `Contexta.build_run_report`

```python
Contexta.build_run_report(left_run_id: str, right_run_id: str) -> ReportDocument
```

두 실행의 비교를 위한 `ReportDocument`를 빌드합니다.

**반환값:** `ReportDocument`

---

### `Contexta.build_project_summary_report`

```python
Contexta.build_project_summary_report(project_name: str) -> ReportDocument
```

프로젝트의 모든 실행을 요약하는 `ReportDocument`를 빌드합니다.

**반환값:** `ReportDocument`

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

메트릭 추세 쿼리를 위한 `ReportDocument`를 빌드합니다.

**반환값:** `ReportDocument`

---

### `Contexta.build_alert_report`

```python
Contexta.build_alert_report(run_id: str, rules: Sequence[AlertRule]) -> ReportDocument
```

단일 실행에 대한 알림 평가 결과로 `ReportDocument`를 빌드합니다.

**반환값:** `ReportDocument`

---

### `Contexta.build_multi_run_report`

```python
Contexta.build_multi_run_report(run_ids: Sequence[str]) -> ReportDocument
```

다중 실행 비교를 위한 `ReportDocument`를 빌드합니다.

**반환값:** `ReportDocument`

---

## contexta.config

### load_config

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

프로필, 설정 파일, 환경 변수, 그리고 직접적인 패치(patch)로부터 `UnifiedConfig`를 해결합니다. 해결 순서는 다음과 같습니다: 프로필 → 설정 파일 → 환경 변수 재정의 → `config` 패치.

**매개변수:**

`profile`
기본으로 로드할 명명된 내장 프로필입니다.

`overlays`
기본 프로필 위에 적용할 추가적인 명명된 오버레이들입니다.

`config_file`
TOML/YAML 설정 파일의 경로입니다. 기본 프로필 다음에 적용됩니다.

`config`
직접적인 설정 객체 또는 매핑 패치입니다. 마지막에 적용되어 다른 모든 설정을 덮어씁니다.

`workspace`
워크스페이스 루트 경로 재정의입니다.

`project_name`
프로젝트 이름 약칭 재정의입니다.

`env`
사용자 정의 환경 변수 매핑입니다. `None`일 경우 기본값은 `os.environ`입니다.

`use_env`
`False`일 경우 환경 변수 해결을 완전히 건너뜁니다.

**반환값:** `UnifiedConfig`

---

### load_profile

```python
contexta.config.load_profile(
    name: ProfileName,
    *,
    overlays: Sequence[ProfileOverlayName] = (),
    workspace: str | Path | None = None,
    project_name: str | None = None,
) -> UnifiedConfig
```

선택적인 오버레이 및 약칭 재정의와 함께 내장 프로필을 로드합니다.

**매개변수:**

`name`
프로필 이름입니다. `PROFILE_NAMES`에 있는 값 중 하나입니다.

`overlays`
기본 프로필 위에 적용할 명명된 오버레이들입니다.

`workspace`
워크스페이스 루트 경로 약칭입니다.

`project_name`
프로젝트 이름 약칭입니다.

**반환값:** `UnifiedConfig`

---

### make_local_config

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

`local` 기본 프로필을 사용하여 검증된 설정을 빌드합니다. `load_config(profile="local", ...)`와 동일합니다.

**반환값:** `UnifiedConfig`

---

### make_test_config

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

`test` 기본 프로필을 사용하여 검증된 설정을 빌드합니다. 테스트 격리를 위해 기본적으로 환경 변수는 무시됩니다(`use_env=False`).

**반환값:** `UnifiedConfig`

---

## contexta.contract

### to_json

```python
contexta.contract.to_json(obj: Any) -> str
```

표준 계약 모델을 결정론적인 표준 JSON으로 직렬화합니다.

**매개변수:**

`obj`
표준 모델 인스턴스입니다 (예: `Run`, `MetricRecord`, `ArtifactManifest`).

**반환값:** `str` — 키가 정렬된 UTF-8 JSON 문자열입니다.

---

### to_payload

```python
contexta.contract.to_payload(obj: Any) -> Any
```

표준 모델을 JSON 친화적인 Python 구조(dict, list, 기본 타입)로 변환합니다. 문자열이 아닌 중간 단계의 dict가 필요할 때 사용합니다.

**반환값:** `dict | list | str | int | float | bool | None`

---

### validate_run

```python
contexta.contract.validate_run(
    run: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

표준 계약 규칙에 따라 `Run` 모델을 검증합니다.

**매개변수:**

`run`
검증할 `Run` 인스턴스입니다.

`registry`
확장 필드 검증을 위한 확장 레지스트리입니다. `None`일 경우 확장 필드는 검증되지 않습니다.

**반환값:** `ValidationReport`

---

## contexta.interpretation 서비스 클래스

### QueryService

```python
class QueryService:
    def __init__(self, repository: CompositeRepository) -> None
```

**매개변수:**

`repository`
프로젝트, 실행, 스테이지, 관계, 레코드, 아티팩트 및 프로버넌스 조회에 사용되는 복합 읽기 저장소(repository)입니다.

**반환값:** `QueryService`

---

#### QueryService.list_projects

```python
QueryService.list_projects() -> tuple[str, ...]
```

**반환값:** `tuple[str, ...]`

---

#### QueryService.list_runs

```python
QueryService.list_runs(
    project_name: str | None = None,
    *,
    query: RunListQuery | None = None,
) -> tuple[RunRecord, ...]
```

**매개변수:**

`project_name`
선택적인 프로젝트 이름 필터입니다.

`query`
메타데이터 필터, 메트릭 조건, 정렬 옵션, 오프셋 및 제한 사항을 포함하는 선택적인 `RunListQuery`입니다.

**반환값:** `tuple[RunRecord, ...]`

---

#### QueryService.get_run_snapshot

```python
QueryService.get_run_snapshot(run_id: str) -> RunSnapshot
```

**매개변수:**

`run_id`
실행 식별자입니다.

**반환값:** `RunSnapshot`

---

#### QueryService.get_artifact_origin

```python
QueryService.get_artifact_origin(artifact_ref: str) -> RunSnapshot | None
```

**매개변수:**

`artifact_ref`
아티팩트 참조 문자열입니다.

**반환값:** `RunSnapshot | None`

---

### CompareService

```python
class CompareService:
    def __init__(
        self,
        query_service: QueryService,
        *,
        config: ComparisonPolicy | None = None,
    ) -> None
```

**매개변수:**

`query_service`
실행 스냅샷을 로드하는 데 사용되는 쿼리 서비스입니다.

`config`
선택적인 비교 정책입니다.

**반환값:** `CompareService`

---

#### CompareService.compare_runs

```python
CompareService.compare_runs(left_run_id: str, right_run_id: str) -> RunComparison
```

**매개변수:**

`left_run_id`
왼쪽 실행 식별자입니다.

`right_run_id`
오른쪽 실행 식별자입니다.

**반환값:** `RunComparison`

---

#### CompareService.compare_multiple_runs

```python
CompareService.compare_multiple_runs(run_ids: Sequence[str]) -> MultiRunComparison
```

**매개변수:**

`run_ids`
비교할 실행 식별자들입니다. 최소한 두 개의 서로 다른 ID가 필요합니다.

**반환값:** `MultiRunComparison`

---

#### CompareService.select_best_run

```python
CompareService.select_best_run(
    run_ids: Sequence[str],
    metric_key: str,
    *,
    stage_name: str | None = None,
    higher_is_better: bool = True,
) -> str | None
```

**매개변수:**

`run_ids`
후보 실행 식별자들입니다.

`metric_key`
순위를 매기는 데 사용되는 메트릭 키입니다.

`stage_name`
선택적인 스테이지 이름 제한 사항입니다.

`higher_is_better`
더 큰 메트릭 값이 더 작은 값보다 높은 순위를 차지하는지 여부입니다.

**반환값:** `str | None`

---

#### CompareService.compare_report_documents

```python
CompareService.compare_report_documents(left: object, right: object) -> ReportComparison
```

**매개변수:**

`left`
왼쪽 리포트 유사 객체입니다.

`right`
오른쪽 리포트 유사 객체입니다.

**반환값:** `ReportComparison`

---

### DiagnosticsService

```python
class DiagnosticsService:
    def __init__(
        self,
        query_service: QueryService,
        *,
        config: DiagnosticsPolicy | None = None,
    ) -> None
```

**매개변수:**

`query_service`
실행 스냅샷을 로드하는 데 사용되는 쿼리 서비스입니다.

`config`
선택적인 진단 정책입니다.

**반환값:** `DiagnosticsService`

---

#### DiagnosticsService.diagnose_run

```python
DiagnosticsService.diagnose_run(run_id: str) -> DiagnosticsResult
```

**매개변수:**

`run_id`
실행 식별자입니다.

**반환값:** `DiagnosticsResult`

---

### LineageService

```python
class LineageService:
    def __init__(
        self,
        query_service: QueryService,
        *,
        config: LineagePolicy | None = None,
    ) -> None
```

**반환값:** `LineageService`

---

#### LineageService.traverse_lineage

```python
LineageService.traverse_lineage(
    subject_ref: str,
    *,
    direction: str | None = None,
    max_depth: int | None = None,
) -> LineageTraversal
```

**매개변수:**

`subject_ref`
루트 실행, 아티팩트, 스테이지, 작업 또는 관계 대상입니다.

`direction`
순회 방향입니다. 유효한 값은 "inbound", "outbound", 또는 "both"입니다.

`max_depth`
최대 순회 깊이입니다.

**반환값:** `LineageTraversal`

---

### TrendService

```python
class TrendService:
    def __init__(
        self,
        query_service: QueryService,
        *,
        config: TrendPolicy | None = None,
    ) -> None
```

**반환값:** `TrendService`

---

#### TrendService.get_metric_trend

```python
TrendService.get_metric_trend(
    metric_key: str,
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
    stage_name: str | None = None,
) -> MetricTrend
```

**매개변수:**

`metric_key`
여러 실행에 걸쳐 집계할 메트릭 키입니다.

`query`
선택적인 실행 집단 필터입니다.

`project_name`
선택적인 프로젝트 이름 필터입니다.

`stage_name`
선택적인 스테이지 이름 제한 사항입니다.

**반환값:** `MetricTrend`

---

#### TrendService.get_step_series

```python
TrendService.get_step_series(
    run_id: str,
    metric_key: str,
    *,
    stage_id: str | None = None,
) -> StepSeries
```

**매개변수:**

`run_id`
실행 식별자입니다.

`metric_key`
실행 내에서 읽을 메트릭 키입니다.

`stage_id`
선택적인 정확한 스테이지 식별자입니다.

**반환값:** `StepSeries`

---

#### TrendService.get_stage_duration_trend

```python
TrendService.get_stage_duration_trend(
    stage_name: str,
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
) -> DurationTrend
```

**매개변수:**

`stage_name`
여러 실행에 걸쳐 집계할 스테이지 이름입니다.

`query`
선택적인 실행 집단 필터입니다.

`project_name`
선택적인 프로젝트 이름 필터입니다.

**반환값:** `DurationTrend`

---

#### TrendService.get_artifact_size_trend

```python
TrendService.get_artifact_size_trend(
    artifact_kind: str,
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
) -> ArtifactSizeTrend
```

**매개변수:**

`artifact_kind`
여러 실행에 걸쳐 집계할 아티팩트 종류입니다.

`query`
선택적인 실행 집단 필터입니다.

`project_name`
선택적인 프로젝트 이름 필터입니다.

**반환값:** `ArtifactSizeTrend`

---

### AlertService

```python
class AlertService:
    def __init__(
        self,
        query_service: QueryService,
        *,
        metric_aggregation: str = "latest",
    ) -> None
```

**반환값:** `AlertService`

---

#### AlertService.evaluate_alerts

```python
AlertService.evaluate_alerts(
    run_id: str,
    rules: tuple[AlertRule, ...] | list[AlertRule],
) -> tuple[AlertResult, ...]
```

**매개변수:**

`run_id`
실행 식별자입니다.

`rules`
실행 스냅샷에 대해 평가할 알림 규칙들입니다.

**반환값:** `tuple[AlertResult, ...]`

---

#### AlertService.evaluate_alerts_fleet

```python
AlertService.evaluate_alerts_fleet(
    rules: tuple[AlertRule, ...] | list[AlertRule],
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
) -> AlertReport
```

**매개변수:**

`rules`
선택된 실행 집단에 걸쳐 평가할 알림 규칙들입니다.

`query`
선택적인 실행 집단 필터입니다.

`project_name`
선택적인 프로젝트 이름 필터입니다.

**반환값:** `AlertReport`

---

### ProvenanceService

```python
class ProvenanceService:
    def __init__(self, query_service: QueryService) -> None
```

**반환값:** `ProvenanceService`

---

#### ProvenanceService.audit_reproducibility

```python
ProvenanceService.audit_reproducibility(run_id: str) -> ReproducibilityAudit
```

**매개변수:**

`run_id`
실행 식별자입니다.

**반환값:** `ReproducibilityAudit`

---

#### ProvenanceService.compare_environments

```python
ProvenanceService.compare_environments(
    left_run_id: str,
    right_run_id: str,
) -> EnvironmentDiff
```

**매개변수:**

`left_run_id`
왼쪽 실행 식별자입니다.

`right_run_id`
오른쪽 실행 식별자입니다.

**반환값:** `EnvironmentDiff`

---

### AggregationService

```python
class AggregationService:
    def __init__(
        self,
        query_service: QueryService,
        *,
        metric_aggregation: str = "latest",
    ) -> None
```

**반환값:** `AggregationService`

---

#### AggregationService.aggregate_metric

```python
AggregationService.aggregate_metric(
    metric_key: str,
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
    stage_name: str | None = None,
) -> MetricAggregate
```

**매개변수:**

`metric_key`
집계할 메트릭 키입니다.

`query`
선택적인 실행 집단 필터입니다.

`project_name`
선택적인 프로젝트 이름 필터입니다.

`stage_name`
선택적인 스테이지 이름 제한 사항입니다.

**반환값:** `MetricAggregate`

---

#### AggregationService.aggregate_by_stage

```python
AggregationService.aggregate_by_stage(
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
) -> RunSummaryTable
```

**매개변수:**

`query`
선택적인 실행 집단 필터입니다.

`project_name`
선택적인 프로젝트 이름 필터입니다.

**반환값:** `RunSummaryTable`

---

#### AggregationService.run_status_distribution

```python
AggregationService.run_status_distribution(
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
) -> RunStatusDistribution
```

**매개변수:**

`query`
선택적인 실행 집단 필터입니다.

`project_name`
선택적인 프로젝트 이름 필터입니다.

**반환값:** `RunStatusDistribution`

---

### AnomalyService

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

**반환값:** `AnomalyService`

---

#### AnomalyService.compute_baseline

```python
AnomalyService.compute_baseline(
    metric_key: str,
    *,
    query: RunListQuery | None = None,
    project_name: str | None = None,
    stage_name: str | None = None,
) -> MetricBaseline
```

**매개변수:**

`metric_key`
기준(baseline)을 구축하는 데 사용되는 메트릭 키입니다.

`query`
선택적인 기준 실행 집단 필터입니다.

`project_name`
선택적인 프로젝트 이름 필터입니다.

`stage_name`
선택적인 스테이지 이름 제한 사항입니다.

**반환값:** `MetricBaseline`

---

#### AnomalyService.detect_anomalies

```python
AnomalyService.detect_anomalies(
    run_id: str,
    *,
    baseline: MetricBaseline,
    stage_name: str | None = None,
) -> tuple[AnomalyResult, ...]
```

**매개변수:**

`run_id`
실행 식별자입니다.

`baseline`
미리 계산된 메트릭 기준입니다.

`stage_name`
선택적인 스테이지 이름 제한 사항입니다.

**반환값:** `tuple[AnomalyResult, ...]`

---

#### AnomalyService.detect_anomalies_in_run

```python
AnomalyService.detect_anomalies_in_run(
    run_id: str,
    *,
    baseline_query: RunListQuery | None = None,
    metric_keys: tuple[str, ...] | None = None,
    stage_name: str | None = None,
) -> tuple[AnomalyResult, ...]
```

**매개변수:**

`run_id`
실행 식별자입니다.

`baseline_query`
기준 실행 집단을 선택하는 데 사용되는 선택적인 쿼리입니다.

`metric_keys`
선택적인 명시적 메트릭 키 목록입니다.

`stage_name`
선택적인 스테이지 이름 제한 사항입니다.

**반환값:** `tuple[AnomalyResult, ...]`

---

### ReportBuilder

```python
class ReportBuilder:
```

**반환값:** `ReportBuilder`

---

#### ReportBuilder.build_snapshot_report

```python
ReportBuilder.build_snapshot_report(
    snapshot: RunSnapshot,
    diagnostics: DiagnosticsResult,
) -> ReportDocument
```

**매개변수:**

`snapshot`
기본 리포트 소스로 사용되는 실행 스냅샷입니다.

`diagnostics`
리포트에 병합되는 진단 결과입니다.

**반환값:** `ReportDocument`

---

#### ReportBuilder.build_run_report

```python
ReportBuilder.build_run_report(
    comparison: RunComparison,
    diagnostics: DiagnosticsResult,
) -> ReportDocument
```

**매개변수:**

`comparison`
기본 리포트 소스로 사용되는 실행 비교 결과입니다.

`diagnostics`
리포트에 병합되는 진단 결과입니다.

**반환값:** `ReportDocument`

---

#### ReportBuilder.build_project_summary_report

```python
ReportBuilder.build_project_summary_report(
    project_name: str,
    *,
    runs: tuple[RunRecord, ...] = (),
    notes: tuple[CompletenessNote, ...] = (),
) -> ReportDocument
```

**매개변수:**

`project_name`
리포트 제목에 표시될 프로젝트 이름입니다.

`runs`
요약에 포함될 실행 레코드들입니다.

`notes`
리포트에 렌더링될 완전성 메모(completeness notes)들입니다.

**반환값:** `ReportDocument`

---

#### ReportBuilder.build_trend_report

```python
ReportBuilder.build_trend_report(trend: MetricTrend) -> ReportDocument
```

**매개변수:**

`trend`
리포트 소스로 사용되는 추세 결과입니다.

**반환값:** `ReportDocument`

---

#### ReportBuilder.build_alert_report

```python
ReportBuilder.build_alert_report(
    results: list[AlertResult] | tuple[AlertResult, ...],
) -> ReportDocument
```

**매개변수:**

`results`
리포트에 포함될 알림 결과들입니다.

**반환값:** `ReportDocument`

---

#### ReportBuilder.build_multi_run_report

```python
ReportBuilder.build_multi_run_report(
    comparison: MultiRunComparison,
) -> ReportDocument
```

**매개변수:**

`comparison`
리포트 소스로 사용되는 다중 실행 비교 결과입니다.

**반환값:** `ReportDocument`

---

### validate_metric_record

```python
contexta.contract.validate_metric_record(
    record: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

`MetricRecord` 모델을 검증합니다.

**반환값:** `ValidationReport`

---

### 역직렬화(Deserialization) 함수들

모든 역직렬화 함수는 다음 패턴을 따릅니다:

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

# ... 모든 계약 모델 타입에 대해 유사한 함수들이 존재함
```

`data`
원시 dict(`json.loads` 등에서 얻은 값) 또는 이미 구축된 모델 인스턴스입니다.

`registry`
확장 필드를 해결하는 데 사용되는 확장 레지스트리입니다. `None`일 경우 확장 필드는 검증 없이 통과됩니다.

---

## contexta.store.metadata

### MetadataStore

```python
class MetadataStore(
    config: MetadataStoreConfig | None = None,
)
```

표준 메타데이터 원본(Source of Truth) 스토어입니다. 로컬 DuckDB 데이터베이스에서 프로젝트, 실행, 스테이지 및 환경 레코드를 관리합니다.

컨텍스트 매니저로 사용할 수 있습니다:

```python
with MetadataStore(config) as store:
    report = store.check_integrity()
```

**속성:**

`MetadataStore.duckdb` — DuckDB 프레임 어댑터입니다.

`MetadataStore.pandas` — Pandas 프레임 어댑터입니다.

`MetadataStore.polars` — Polars 프레임 어댑터입니다.

---

#### MetadataStore.check_integrity

```python
MetadataStore.check_integrity(*, full: bool = True) -> IntegrityReport
```

메타데이터 스토어의 무결성 이슈를 스캔합니다.

**매개변수:**

`full`
`True`일 경우 전체 정밀 스캔을 실행합니다. `False`일 경우 빠른 표면 스캔을 실행합니다.

**반환값:** `IntegrityReport`

---

#### MetadataStore.plan_repairs

```python
MetadataStore.plan_repairs(report: IntegrityReport | None = None) -> RepairPlan
```

무결성 리포트를 운영자용 복구 후보를 포함하는 `RepairPlan`으로 변환합니다. `report`가 `None`일 경우 `check_integrity()`가 먼저 호출됩니다.

**반환값:** `RepairPlan`

---

#### MetadataStore.preview_repairs

```python
MetadataStore.preview_repairs(plan: RepairPlan | None = None) -> RepairPreview
```

`RepairPlan`이 수행할 작업에 대한 사람이 읽기 좋은 요약을 빌드합니다. `plan`이 `None`일 경우 `plan_repairs()`가 먼저 호출됩니다.

**반환값:** `RepairPreview`

---

#### MetadataStore.build_run_snapshot

```python
MetadataStore.build_run_snapshot(run_ref: str) -> RunSnapshot
```

하나의 실행에 대해 메가데이터 범위의 `RunSnapshot`을 빌드합니다. 이것은 하위 수준의 메타데이터 전용 프로젝션입니다. 레코드 및 아티팩트 증거를 포함하는 전체 사용자용 스냅샷을 보려면 `Contexta.get_run_snapshot`을 사용하세요.

**반환값:** `contexta.store.metadata.RunSnapshot`

---

#### MetadataStore.migrate

```python
MetadataStore.migrate(*, target_version: str | None = None) -> MigrationResult
```

대기 중인 스키마 마이그레이션을 적용합니다. `target_version`이 `None`일 경우 최신 스키마 버전으로 마이그레이션합니다.

**반환값:** `MigrationResult`

**참고:** `MetadataStore.dry_run_migration`, `MetadataStore.plan_migration`

---

## contexta.store.records

### RecordStore

```python
class RecordStore(
    config: RecordStoreConfig | None = None,
)
```

추가 전용(append-only) 레코드 원본(Source of Truth) 스토어입니다. 모든 캡처 레코드 타입에 대해 JSONL 세그먼트 파일을 관리합니다.

---

### export_jsonl

```python
contexta.store.records.export_jsonl(
    store: RecordStore,
    destination: str | Path,
    scan_filter: ScanFilter | None = None,
    *,
    mode: ReplayMode = ReplayMode.STRICT,
) -> ReplayResult
```

재생 가능한 표준 레코드를 `destination`에 JSONL로 내보냅니다.

**매개변수:**

`store`
내보낼 소스 `RecordStore` 인스턴스입니다.

`destination`
출력 JSONL 파일의 경로입니다.

`scan_filter`
내보낼 레코드를 제한하는 선택적인 `ScanFilter`입니다.

`mode`
에러 처리를 제어하는 재생 모드입니다. `ReplayMode.STRICT`는 잘못된 레코드 발견 시 예외를 발생시킵니다. `ReplayMode.LENIENT`는 잘못된 레코드를 건너뛰고 계속 진행합니다.

**반환값:** `ReplayResult`

---

### check_integrity (records)

```python
contexta.store.records.check_integrity(store: RecordStore) -> IntegrityReport
```

레코드 세그먼트와 매니페스트에서 무결성 이슈(잘림, 해시 불일치, 간격 등)를 스캔합니다.

**반환값:** `contexta.store.records.IntegrityReport`

---

## contexta.store.artifacts

### ArtifactStore

```python
class ArtifactStore(
    config: ArtifactStoreConfig | None = None,
)
```

아티팩트 원본(Source of Truth) 스토어입니다. 매니페스트 추적을 통해 콘텐츠 주소 지정 방식(content-addressed)의 바이너리 아티팩트 저장을 관리합니다.

---

### get_artifact

```python
contexta.store.artifacts.get_artifact(
    store: ArtifactStore,
    artifact_ref: str,
) -> ArtifactHandle
```

주어진 아티팩트 참조에 대한 `ArtifactHandle`을 반환합니다.

**반환값:** `ArtifactHandle`

---

### read_artifact_bytes

```python
contexta.store.artifacts.read_artifact_bytes(
    store: ArtifactStore,
    artifact_ref: str,
) -> bytes
```

아티팩트의 전체 본문을 메모리로 읽어옵니다.

**반환값:** `bytes`

---

### open_artifact

```python
contexta.store.artifacts.open_artifact(
    store: ArtifactStore,
    artifact_ref: str,
    *,
    mode: str = "rb",
) -> BinaryIO
```

아티팩트를 바이너리 파일 유사 객체로 엽니다. 호출자가 이를 닫아야 할 책임이 있습니다.

**반환값:** `BinaryIO`

---

### iter_artifact_chunks

```python
contexta.store.artifacts.iter_artifact_chunks(
    store: ArtifactStore,
    artifact_ref: str,
    *,
    chunk_size: int | None = None,
) -> Iterator[bytes]
```

아티팩트 본문을 청크 단위로 스트리밍합니다. 메모리에 완전히 로드하지 않아야 하는 대용량 아티팩트에 유용합니다.

**매개변수:**

`chunk_size`
청크당 바이트 수입니다. `None`일 경우 스토어의 기본 청크 크기가 사용됩니다.

**반환값:** `Iterator[bytes]`

---

### artifact_exists

```python
contexta.store.artifacts.artifact_exists(
    store: ArtifactStore,
    artifact_ref: str,
) -> bool
```

아티팩트 본문이 스토어에 존재하면 `True`를 반환합니다.

---

### list_refs

```python
contexta.store.artifacts.list_refs(store: ArtifactStore) -> list[str]
```

스토어에 알려진 모든 아티팩트 참조 문자열을 반환합니다.

---

### verify_artifact

```python
contexta.store.artifacts.verify_artifact(
    store: ArtifactStore,
    artifact_ref: str,
    *,
    manifest: ArtifactManifest | None = None,
) -> VerificationReport
```

저장된 매니페스트에 대해 아티팩트 본문의 해시를 다시 계산하여 단일 아티팩트의 무결성을 검증합니다.

**매개변수:**

`manifest`
미리 가져온 매니페스트입니다. `None`일 경우 스토어에서 매니페스트를 로드합니다.

**반환값:** `VerificationReport`

---

### verify_all

```python
contexta.store.artifacts.verify_all(store: ArtifactStore) -> SweepReport
```

스토어의 모든 아티팩트를 검증합니다. 아티팩트당 `VerificationRecord` 항목을 포함하는 `SweepReport`를 반환합니다.

**반환값:** `SweepReport`

---

### inspect_store

```python
contexta.store.artifacts.inspect_store(store: ArtifactStore) -> StoreSummary
```

상위 수준의 `StoreSummary`(아티팩트 개수, 전체 크기, 포맷 버전)를 반환합니다.

**반환값:** `StoreSummary`

---

## contexta.recovery

### plan_workspace_backup

```python
contexta.recovery.plan_workspace_backup(
    config: UnifiedConfig,
    *,
    label: str | None = None,
    include_cache: bool = False,
    include_exports: bool = False,
) -> BackupPlan
```

무엇을 백업할지 설명하는 `BackupPlan`을 빌드합니다. 아무것도 실제로 쓰지 않습니다.

**매개변수:**

`config`
백업할 워크스페이스에 대해 해결된 `UnifiedConfig`입니다.

`label`
백업 매니페스트에 첨부되는 선택적인 사람이 읽기 좋은 라벨입니다.

`include_cache`
`True`일 경우 백업에 캐시된 중간 파일을 포함합니다.

`include_exports`
`True`일 경우 이전에 내보낸 아티팩트 패키지를 백업에 포함합니다.

**반환값:** `BackupPlan`

---

### create_workspace_backup

```python
contexta.recovery.create_workspace_backup(
    config: UnifiedConfig,
    plan: BackupPlan,
) -> BackupResult
```

`BackupPlan`을 실행하고 백업 아카이브를 디스크에 씁니다.

**반환값:** `BackupResult`

---

### plan_restore

```python
contexta.recovery.plan_restore(
    config: UnifiedConfig,
    backup_ref: str,
    *,
    target_workspace: Path | None = None,
    verify_only: bool = False,
) -> RestorePlan
```

백업 참조로부터 `RestorePlan`을 빌드합니다. 아무것도 실제로 복구하지 않습니다.

**매개변수:**

`backup_ref`
백업 아카이브를 식별하는 경로 또는 참조 문자열입니다.

`target_workspace`
복구 대상 위치입니다. 기본값은 `config`에 지정된 워크스페이스입니다.

`verify_only`
`True`일 경우 계획에 파괴적인 쓰기 없이 검증 단계만 포함됩니다.

**반환값:** `RestorePlan`

---

### restore_workspace

```python
contexta.recovery.restore_workspace(
    config: UnifiedConfig,
    plan: RestorePlan,
) -> RestoreResult
```

`RestorePlan`을 실행하고 워크스페이스를 복구합니다.

**반환값:** `RestoreResult`

---

### replay_outbox

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

대기 중인 Outbox 메시지를 구성된 싱크들로 재처리(Replay)합니다.

**매개변수:**

`target`
재생할 레코드를 이 싱크 식별자로 제한합니다. `None`일 경우 대기 중인 모든 레코드가 재생됩니다.

`limit`
이 호출에서 재생할 레코드의 최대 개수입니다.

`acknowledge_successes`
`True`일 경우 성공적으로 처리된 메시지는 Outbox에서 제거됩니다.

`dead_letter_after_failures`
연속된 실패 횟수가 이 값을 넘으면 레코드를 데드 레터(dead-letter) 큐로 이동합니다. `None`일 경우 실패한 메시지는 Outbox에 무기한 유지됩니다.

`sinks`
재생할 대상 싱크들을 직접 지정합니다. `None`일 경우 `config`에 있는 싱크들이 사용됩니다.

**반환값:** `ReplayBatchResult`

---

## contexta.capture

### EventEmission

```python
@dataclass(frozen=True, slots=True)
class EventEmission:
    key: str
    message: str
    level: str = "info"
    attributes: Mapping[str, Any] | None = None
    tags: Mapping[str, str] | None = None
```

**매개변수:**

`key`
점으로 구분된 이벤트 키입니다. 표준 이벤트 키 패턴과 일치해야 합니다.

`message`
비어 있지 않은 이벤트 메시지입니다.

`level`
표준 이벤트 레벨입니다. 계약에 정의된 `EVENT_LEVELS` 값이 사용됩니다.

`attributes`
JSON 직렬화 가능한 구조화된 속성들입니다.

`tags`
문자열 대 문자열 태그 매핑입니다.

**반환값:** `EventEmission`

**참고:**

- 잘못된 키, 비어 있는 문자열, JSON 직렬화가 불가능한 속성 값은 `ValidationError`를 발생시킵니다.
- `to_dict()`는 전송에 적합한 정규화된 매핑을 반환합니다.

---

### MetricEmission

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

**매개변수:**

`key`
점으로 구분된 메트릭 키입니다.

`value`
유한한(numeric) 숫자 값입니다.

`unit`
선택적인 메트릭 단위 라벨입니다.

`aggregation_scope`
표준 집계 범위입니다. 계약에 정의된 `METRIC_AGGREGATION_SCOPES` 값이 사용됩니다.

`tags`
문자열 대 문자열 태그 매핑입니다.

`summary_basis`
스네이크 케이스(lower-snake) 요약 기준 토큰입니다.

**반환값:** `MetricEmission`

**참고:**

- 유한하지 않은 숫자(예: inf, nan) 및 불리언(bool) 값은 거부됩니다.
- `to_dict()`는 전송에 적합한 정규화된 매핑을 반환합니다.

---

### SpanEmission

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

**매개변수:**

`name`
비어 있지 않은 스팬 이름입니다.

`started_at`
선택적인 ISO 8601 타임스탬프 문자열입니다.

`ended_at`
선택적인 ISO 8601 타임스탬프 문자열입니다. 둘 다 제공될 경우 `started_at`보다 크거나 같아야 합니다.

`status`
표준 트레이스 스팬 상태입니다. 계약에 정의된 `TRACE_SPAN_STATUSES` 값이 사용됩니다.

`span_kind`
표준 트레이스 스팬 종류입니다. 계약에 정의된 `TRACE_SPAN_KINDS` 값이 사용됩니다.

`attributes`
JSON 직렬화 가능한 스팬 속성들입니다.

`linked_refs`
이 스팬과 연결된 안정적인 참조들입니다.

`parent_span_id`
선택적인 부모 스팬 식별자입니다.

**반환값:** `SpanEmission`

**참고:**

- 타임스탬프는 `normalize_timestamp`를 통해 정규화됩니다.
- `to_dict()`는 전송에 적합한 정규화된 매핑을 반환합니다.

---

### ArtifactRegistrationEmission

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

**매개변수:**

`artifact_kind`
스네이크 케이스 아티팩트 종류 토큰입니다.

`path`
비어 있지 않은 파일 시스템 경로 문자열입니다.

`artifact_ref`
선택적인 명시적 아티팩트 참조입니다.

`attributes`
JSON 직렬화 가능한 아티팩트 속성들입니다.

`compute_hash`
`True`일 경우 등록 중에 콘텐츠 해시를 계산합니다.

`allow_missing`
`True`일 경우 등록 계획 단계에서 누락된 경로를 허용합니다.

**반환값:** `ArtifactRegistrationEmission`

---

### Delivery

```python
@dataclass(frozen=True, slots=True)
class Delivery:
    sink_name: str
    family: PayloadFamily | str
    status: DeliveryStatus | str
    detail: str = ""
    metadata: Mapping[str, Any] | None = None
```

**매개변수:**

`sink_name`
비어 있지 않은 싱크 식별자입니다.

`family`
전송된 항목의 페이로드 패밀리(family)입니다.

`status`
싱크별 전송 상태입니다.

`detail`
선택적인 자유 형식의 상세 문자열입니다.

`metadata`
선택적인 전송 메타데이터 매핑입니다.

**반환값:** `Delivery`

---

### CaptureResult

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

**매개변수:**

`family`
캡처 페이로드 패밀리입니다.

`deliveries`
싱크별 전송 결과들입니다.

`warnings`
결과 메시지 스트림에 추가된 경고 문자열들입니다.

`degradation_reasons`
기능 저하(degradation) 노트를 채우는 데 사용되는 원인 문자열들입니다.

`payload`
결과의 기본 페이로드입니다.

`degradation_emitted`
기능 저하 페이로드가 방출되었는지 여부입니다.

`degradation_payload`
선택적인 기능 저하 페이로드입니다. `degradation_emitted=True`가 필요합니다.

`recovered_to_outbox`
실패한 캡처가 Outbox 재처리 공간으로 복구되었는지 여부입니다.

`replay_refs`
Outbox 복구와 연관된 재생 참조 문자열들입니다.

`error_code`
선택적인 명시적 에러 코드입니다.

`error_message`
선택적인 명시적 에러 메시지입니다.

**반환값:** `CaptureResult`

**참고:**

- `OperationResult`로부터 상태, 메시지, 기능 저하 노트, 실패 여부, 메타데이터 등을 상속받습니다.
- `success`, `with_degradation`, `failure_result`는 클래스 메서드 생성자입니다.
- `to_dict()`는 전송에 적합한 매핑을 반환합니다.

---

### BatchCaptureResult

```python
@dataclass(frozen=True, slots=True)
class BatchCaptureResult(BatchResult[CaptureResult]):
    family: PayloadFamily | str = PayloadFamily.RECORD
```

**매개변수:**

`family`
배치 내 각 결과에 공유되는 페이로드 패밀리입니다.

**반환값:** `BatchCaptureResult`

**참고:**

- `results`는 `items`의 캡처 전용 별칭입니다.
- `from_results()`와 `aggregate()`는 보관된 `CaptureResult` 값들로부터 표준 배치 상태를 도출합니다.
- `to_dict()`는 전송에 적합한 매핑을 반환합니다.

---

## contexta.config 모델 클래스

### WorkspaceConfig

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

**매개변수:**

`root_path`
워크스페이스 루트 경로입니다.

`metadata_path`
메타데이터 플레인 경로입니다. 기본값은 `<root_path>/metadata`입니다.

`records_path`
레코드 플레인 경로입니다. 기본값은 `<root_path>/records`입니다.

`artifacts_path`
아티팩트 플레인 경로입니다. 기본값은 `<root_path>/artifacts`입니다.

`reports_path`
리포트 출력 경로입니다. 기본값은 `<root_path>/reports`입니다.

`exports_path`
내보내기 출력 경로입니다. 기본값은 `<root_path>/exports`입니다.

`cache_path`
캐시 경로입니다. 기본값은 `<root_path>/cache`입니다.

`create_missing_dirs`
워크스페이스 생성 시 누락된 디렉터리를 생성할지 여부입니다.

**반환값:** `WorkspaceConfig`

---

### ContractConfig

```python
@dataclass(frozen=True, slots=True)
class ContractConfig:
    schema_version: str = "1.0.0"
    validation_mode: Literal["strict", "lenient"] = "strict"
    compatibility_mode: Literal["strict", "lenient"] = "strict"
    deterministic_serialization: bool = True
```

**반환값:** `ContractConfig`

---

### CaptureConfig

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

**반환값:** `CaptureConfig`

---

### MetadataStoreConfig

```python
@dataclass(frozen=True, slots=True)
class MetadataStoreConfig:
    storage_adapter: str = "duckdb"
    database_path: Path | None = None
    auto_create: bool = True
    read_only: bool = False
    auto_migrate: bool = False
```

**반환값:** `MetadataStoreConfig`

---

### RecordStoreConfig

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

**반환값:** `RecordStoreConfig`

---

### ArtifactStoreConfig

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

**반환값:** `ArtifactStoreConfig`

---

### ComparisonPolicy

```python
@dataclass(frozen=True, slots=True)
class ComparisonPolicy:
    metric_selection: Literal["latest", "max", "min", "mean"] = "latest"
    include_unchanged_metrics: bool = False
    missing_stage_severity: Literal["info", "warning", "error"] = "warning"
```

**반환값:** `ComparisonPolicy`

---

### DiagnosticsPolicy

```python
@dataclass(frozen=True, slots=True)
class DiagnosticsPolicy:
    require_metrics_for_completed_stages: bool = True
    detect_degraded_records: bool = True
    expected_terminal_stage_names: tuple[str, ...] = ("evaluate", "package")
```

**반환값:** `DiagnosticsPolicy`

---

### ReportPolicy

```python
@dataclass(frozen=True, slots=True)
class ReportPolicy:
    include_completeness_notes: bool = True
    include_lineage_summary: bool = True
    include_evidence_summary: bool = True
```

**반환값:** `ReportPolicy`

---

### SearchPolicy

```python
@dataclass(frozen=True, slots=True)
class SearchPolicy:
    default_limit: int = 50
    text_match_fields: tuple[str, ...] = ("name", "tags", "status")
    case_sensitive: bool = False
```

**반환값:** `SearchPolicy`

---

### TrendPolicy

```python
@dataclass(frozen=True, slots=True)
class TrendPolicy:
    default_window_runs: int = 20
    metric_aggregation: Literal["latest", "max", "min", "mean"] = "latest"
```

**반환값:** `TrendPolicy`

---

### AnomalyPolicy

```python
@dataclass(frozen=True, slots=True)
class AnomalyPolicy:
    z_score_threshold: float = 2.5
    min_baseline_runs: int = 3
    monitored_metrics: tuple[str, ...] = ()
```

**반환값:** `AnomalyPolicy`

---

### AlertPolicy

```python
@dataclass(frozen=True, slots=True)
class AlertPolicy:
    stop_on_first_trigger: bool = False
    default_severity: Literal["info", "warning", "error"] = "warning"
```

**반환값:** `AlertPolicy`

---

### InterpretationConfig

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

**반환값:** `InterpretationConfig`

---

### RecoveryConfig

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

**반환값:** `RecoveryConfig`

---

### CLIConfig

```python
@dataclass(frozen=True, slots=True)
class CLIConfig:
    default_output_format: Literal["text", "json"] = "text"
    verbosity: Literal["quiet", "normal", "debug", "forensic"] = "normal"
    color: bool = True
```

**반환값:** `CLIConfig`

---

### HTTPConfig

```python
@dataclass(frozen=True, slots=True)
class HTTPConfig:
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8765
    open_browser: bool = False
```

**반환값:** `HTTPConfig`

---

### HTMLConfig

```python
@dataclass(frozen=True, slots=True)
class HTMLConfig:
    enabled: bool = True
    inline_charts: bool = True
```

**반환값:** `HTMLConfig`

---

### NotebookConfig

```python
@dataclass(frozen=True, slots=True)
class NotebookConfig:
    enabled: bool = True
```

**반환값:** `NotebookConfig`

---

### ExportSurfaceConfig

```python
@dataclass(frozen=True, slots=True)
class ExportSurfaceConfig:
    csv_delimiter: str = ","
    html_inline_charts: bool = True
    include_completeness_notes: bool = True
```

**반환값:** `ExportSurfaceConfig`

---

### SurfaceConfig

```python
@dataclass(frozen=True, slots=True)
class SurfaceConfig:
    cli: CLIConfig = field(default_factory=CLIConfig)
    http: HTTPConfig = field(default_factory=HTTPConfig)
    html: HTMLConfig = field(default_factory=HTMLConfig)
    notebook: NotebookConfig = field(default_factory=NotebookConfig)
    export: ExportSurfaceConfig = field(default_factory=ExportSurfaceConfig)
```

**반환값:** `SurfaceConfig`

---

### RetentionConfig

```python
@dataclass(frozen=True, slots=True)
class RetentionConfig:
    cache_ttl_days: int | None = 7
    report_ttl_days: int | None = None
    export_ttl_days: int | None = None
    artifact_retention_mode: Literal["manual", "planned", "enforced"] = "manual"
    records_compaction_enabled: bool = False
```

**반환값:** `RetentionConfig`

---

### SecurityConfig

```python
@dataclass(frozen=True, slots=True)
class SecurityConfig:
    redaction_mode: Literal["safe_default", "strict", "off"] = "safe_default"
    environment_variable_allowlist: tuple[str, ...] = ()
    secret_key_patterns: tuple[str, ...] = ("token", "secret", "password", "passwd", "key")
    allow_unredacted_local_exports: bool = False
    encryption_provider: str | None = None
```

**반환값:** `SecurityConfig`

---

### UnifiedConfig

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

**매개변수:**

`config_version`
루트 설정 버전 문자열입니다.

`profile_name`
해결된 내장 프로필 이름입니다.

`project_name`
기본 프로젝트 이름입니다.

`workspace`
워크스페이스 및 파생 경로 설정들입니다.

`contract`
계약 정책 설정들입니다.

`capture`
캡처 및 런타임 설정들입니다.

`metadata`
메타데이터 원본(Source of Truth) 스토어 설정들입니다.

`records`
레코드 원본(Source of Truth) 스토어 설정들입니다.

`artifacts`
아티팩트 원본(Source of Truth) 스토어 설정들입니다.

`interpretation`
해석 레이어(Interpretation-layer) 설정들입니다.

`recovery`
복구 설정들입니다.

`surfaces`
출력 지점(Delivery-surface) 설정들입니다.

`retention`
보존(Retention) 정책 설정들입니다.

`security`
보안 및 마스킹(redaction) 설정들입니다.

**반환값:** `UnifiedConfig`

**참고:**

- `__post_init__()`는 `workspace`로부터 기본 메타데이터, 레코드, 아티팩트 및 복구 경로를 도출합니다.

---

## contexta.contract 추가 검증 함수들

### validate_project

```python
contexta.contract.validate_project(
    project: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**매개변수:**

`project`
검증할 `Project` 인스턴스입니다.

`registry`
확장 필드 검증을 위한 레지스트리입니다.

**반환값:** `ValidationReport`

---

### validate_stage_execution

```python
contexta.contract.validate_stage_execution(
    stage: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**매개변수:**

`stage`
검증할 `StageExecution` 인스턴스입니다.

**반환값:** `ValidationReport`

---

### validate_operation_context

```python
contexta.contract.validate_operation_context(
    operation: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**매개변수:**

`operation`
검증할 `OperationContext` 인스턴스입니다.

**반환값:** `ValidationReport`

---

### validate_environment_snapshot

```python
contexta.contract.validate_environment_snapshot(
    snapshot: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**반환값:** `ValidationReport`

---

### validate_record_envelope

```python
contexta.contract.validate_record_envelope(
    envelope: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**반환값:** `ValidationReport`

---

### validate_structured_event_record

```python
contexta.contract.validate_structured_event_record(
    record: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**반환값:** `ValidationReport`

---

### validate_trace_span_record

```python
contexta.contract.validate_trace_span_record(
    record: Any,
    *,
    registry: ExtensionRegistry | None = None,
) -> ValidationReport
```

**반환값:** `ValidationReport`

---

### `validate_trace_span_record`

```python
def validate_trace_span_record(obj: Any) -> TraceSpanRecord
```

객체가 유효한 `TraceSpanRecord` 모델인지 검증합니다.

### `validate_degraded_record`

```python
def validate_degraded_record(obj: Any) -> DegradedRecord
```

객체가 유효한 `DegradedRecord` 모델인지 검증합니다.

### `validate_artifact_manifest`

```python
def validate_artifact_manifest(obj: Any) -> ArtifactManifest
```

객체가 유효한 `ArtifactManifest` 구조를 가지고 있는지 검증합니다.

### `validate_lineage_edge`

```python
def validate_lineage_edge(obj: Any) -> LineageEdge
```

객체가 유효한 `LineageEdge` 연결 구조인지 검증합니다.

### `validate_provenance_record`

```python
def validate_provenance_record(obj: Any) -> ProvenanceRecord
```

객체가 유효한 `ProvenanceRecord` 모델인지 검증합니다.

### `validate_extension_field_set`

```python
def validate_extension_field_set(obj: Any) -> ExtensionFieldSet
```

객체가 유효한 확정 필드 세트(`ExtensionFieldSet`)인지 검증합니다.
