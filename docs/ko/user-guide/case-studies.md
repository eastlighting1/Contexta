# 케이스 스터디

Contexta가 수작업 프로세스를 어떻게 대체하는지 보여주는 12가지 실제 시나리오입니다. 스프레드시트 수작업, Slack 체크리스트, 추정 기반 감사 답변 대신 소수의 API 호출로 해결하는 방법을 다룹니다.

각 시나리오에는 실행 가능한 예제 코드가 `examples/case_studies/`에 포함되어 있습니다.

---

## 왜 Contexta인가요?

### 이 도구가 만들어진 배경

ML 팀에는 이미 실험 추적 도구(MLflow, W&B), 오케스트레이터(Airflow, Prefect), 모니터링 플랫폼(Grafana, Datadog)이 있습니다. 그런데 왜 또 다른 도구가 필요할까요?

기존 도구들이 월요일 아침 9시에 받는 다음 질문에 대답하지 못하기 때문입니다:

> "CTR이 어젯밤에 18% 떨어졌어. 어떤 학습 실행이 배포됐지? 어떤 데이터셋을 사용했어? 안전하게 롤백할 수 있어? 어떤 버전으로?"

실험 추적 도구는 메트릭을 기록하지만, 프로덕션 배포를 정확한 실행·스테이지·데이터셋과 연결하지 않습니다. 오케스트레이터는 작업의 성공/실패 여부를 알지만, 종료 코드가 0이어도 출력이 미묘하게 잘못된 *이유*는 기록하지 않습니다. 모니터링 플랫폼은 임계값 초과 시 알림을 발송하지만, 어떤 학습 실행이 드리프트를 유발했는지는 알 수 없습니다.

Contexta는 이 공백을 채웁니다. 학습 이력, 런타임 동작, 프로덕션 배포를 하나의 질의 가능한 그래프로 연결하는 증거를 기록하는 것이 Contexta의 역할입니다. 이전에는 이틀이 걸리던 질문이 세 번의 API 호출로 해결됩니다.

### Contexta가 다르게 하는 것

| 문제 | 일반적인 접근 | Contexta |
|------|-------------|---------|
| 실험 비교 | 수작업 스프레드시트 또는 MLflow UI | `compare_runs`, `select_best_run`, `build_multi_run_report` |
| 배포 추적성 | 파일명 규칙 또는 릴리스 노트 | `DeploymentExecution`으로 run → deployment 연결; `traverse_lineage` |
| 알림 없는 파이프라인/작업 실패 | 대시보드 임계값 알림 | `DegradedRecord` + `diagnose_run` — 종료 코드 0이어도 감지 |
| 환경 재현성 | `requirements.txt` (종종 오래됨) | 실행 시점에 기록되는 `EnvironmentSnapshot`; `audit_reproducibility` |
| 컴플라이언스 증거 | 2일간 수작업 탐색 | `get_run_snapshot`, `build_snapshot_report` — 수 초 |
| 배포 게이트 | Slack 체크리스트 | 프로그래밍 방식: 진단 + 필수 메트릭 + 회귀 검사 |
| 샘플별 평가 | 집계 메트릭만 가능 | `SampleObservation` + 샘플별 `MetricRecord` |
| 스테이지별 분해 | 종단 간 메트릭만 가능 | 파이프라인 각 스테이지에 스코프된 `MetricRecord` |

### 설계 원칙

- **추가 인프라 불필요.** Contexta는 코드 옆에 로컬로 모든 것을 저장합니다. 호스팅 백엔드도, 별도로 운영해야 할 서비스도 없습니다.
- **비침해적인 도입 지향 (기존 코드 수정을 강제하지 않음).** 이미 만들어진 실행(run)과 스테이지에 레코드를 붙이는 방식입니다. Contexta의 추상화에 맞게 학습 코드를 재구성할 필요가 없습니다.
- **요약이 아닌 증거.** 리포트의 모든 숫자는 타임스탬프, 프로듀서, run 참조가 있는 특정 `RecordEnvelope`까지 추적 가능합니다.
- **프로그래밍 우선.** 리포트, 비교, 게이트는 모두 Python 객체입니다 — 스크립트화, 테스트, CI 연동이 가능합니다. GUI가 필요하지 않습니다.

---

## 그룹 1 — 실험 추적

### 케이스 01: Sara의 여기저기 흩어진(파편화된) HPO 실험

**페르소나:** Sara, ML 엔지니어  
**예제:** `examples/case_studies/case01_scattered_experiments.py`

#### 상황

Sara는 주말 동안 8개의 하이퍼파라미터 탐색 실험을 수행합니다. 각 실험은 `lr0001_bs32_aug_20250318_v3_FINAL.csv` 같은 이름의 CSV나 JSON 파일을 생성합니다. 월요일에 테크 리드가 "어떤 실험이 제일 좋았어요?"라고 묻습니다. Sara는 각 파일을 열고 정확도 수치를 추출하고 수동으로 순위를 매기는 20분간의 스프레드시트 작업 없이는 대답할 수 없습니다.

#### Contexta 없이

- 결과가 엔지니어가 임의로 지은 이름의 파일에 흩어져 있음
- 공통 스키마 없음 → 파일 간 비교에 커스텀 파싱 코드 필요
- 순위 API 없음 → "최고" 실행은 엔지니어의 메모에만 존재
- 2주 후에는 CSV 파일이 노트북에서 삭제되어 있을 수 있음

#### Contexta 사용 시

```python
# 8개 실행 모두 생성 시점에 인덱싱됨
best_ref = ctx.select_best_run(run_refs, "accuracy", stage_name="train")
report   = ctx.build_multi_run_report(run_refs)
```

모든 실행은 완료되는 순간 메트릭과 함께 등록됩니다. `select_best_run`이 스프린트 리뷰 질문에 한 번의 호출로 답합니다. `build_multi_run_report`는 수작업 없이 구조화된 비교를 생성합니다.

**주요 API:** `select_best_run`, `build_multi_run_report`, `compare_runs`

---

### 케이스 02: James의 알림 없는(Silent) 성능 저하

**페르소나:** James, ML 엔지니어  
**예제:** `examples/case_studies/case02_performance_regression.py`

#### 상황

James가 라이브러리를 업그레이드하고 재학습합니다. 정확도가 0.91에서 0.87로 떨어집니다. 의존성 변경이 원인으로 의심되지만 확인할 방법이 없습니다 — 이전 학습의 환경이 기록되지 않았기 때문입니다. `requirements.txt`는 3주 전에 커밋된 것으로, 실제 설치된 패키지를 반영하지 않을 수 있습니다.

#### Contexta 없이

- `requirements.txt`는 특정 시점의 스냅샷이지, 학습 시점의 기록이 아님
- 어느 커밋과 비교해야 하는지 알아야 두 파일을 diff할 수 있음
- 파일이 커밋되지 않았다면 이전 환경 정보는 영영 사라짐
- 어떤 패키지가 회귀를 유발했는지 추측하려면 반복적인 수작업 테스트 필요

#### Contexta 사용 시

```python
env_diff = ctx.compare_environments(old_run_ref, new_run_ref)
# env_diff.python_version_changed → True
# env_diff.changed_packages → [torch: 2.0.0 → 2.1.0, numpy: 1.24.0 → 1.26.0]

audit = ctx.audit_reproducibility(old_run_ref)
# audit.python_version, audit.package_count, audit.reproducibility_status
```

`EnvironmentSnapshot`은 실행 생성 시점에 기록됩니다 — 파일이 아닌, run에 연결된 구조화된 레코드로. `compare_environments`는 두 실행 간의 패키지와 Python 버전의 정확한 diff를 제공합니다.

**주요 API:** `EnvironmentSnapshot`, `compare_environments`, `audit_reproducibility`

---

## 그룹 2 — 프로덕션 모니터링

### 케이스 03: Nina의 알림 없는(Silent) 파이프라인 실패

**페르소나:** Nina, MLE / 데이터 엔지니어  
**예제:** `examples/case_studies/case03_silent_pipeline_failure.py`

#### 상황

5단계 야간 파이프라인(ingest → validate → featurize → train → evaluate)이 3일 동안 모든 스테이지에서 `status=completed`로 실행됩니다. 1일차에 스키마 마이그레이션으로 인해 `validate` 스테이지가 예외를 발생시키는 대신 빈 DataFrame을 다운스트림에 전달했습니다. train 스테이지는 0개 행으로 학습을 완료했고(기본 가중치 반환), evaluate 스테이지는 끔찍한 메트릭을 보고했지만 아무도 3일간 알아채지 못했습니다. 3일차에는 3일치 불량 체크포인트가 프로덕션 승격 대기열에 쌓여 있었습니다.

#### Contexta 없이

- 종료 코드 0 + `status=completed`가 오케스트레이터에게 주어진 유일한 신호
- 오케스트레이터는 "올바르게 완료"와 "빈 입력으로 완료"를 구분할 수 없음
- 대시보드 알림은 아무도 임계값 설정을 안 한 상태
- 3일 후 디버깅하려면 이미 롤링된 로그에서 상황을 재구성해야 함

#### Contexta 사용 시

```python
# validate 스테이지가 빈 출력 감지 시 DegradedRecord 발행
DegradedRecord(
    envelope=RecordEnvelope(..., degradation_marker="partial_failure"),
    payload=DegradedPayload(
        category="verification", severity="error",
        summary="output-dataframe-empty-after-join",
    )
)

# 1일차 — 즉시 감지
diag = ctx.diagnose_run(run_ref)
errors = [i for i in diag.issues if i.severity == "error"]
# → 1 error: degraded_record in validate stage
```

`DegradedRecord`는 스테이지가 종료 코드 0으로 끝나도 살아남는 일급 레코드 타입입니다. `diagnose_run`이 체크포인트 승격 전 1일차에 이를 표면화합니다.

**주요 API:** `DegradedRecord`, `diagnose_run`

---

### 케이스 04: Carlos의 배포 추적성 문제

**페르소나:** Carlos, ML 엔지니어  
**예제:** `examples/case_studies/case04_deployment_traceability.py`

#### 상황

Carlos가 금요일 오후에 모델을 배포합니다. 월요일 아침, 프로덕트 매니저가 CTR이 18% 하락했다고 연락합니다. Carlos의 배포 메모에는 `model_20250401.pkl`이라고만 적혀 있습니다. 네 가지 질문에 답할 수 없습니다:

1. 어떤 학습 실행이 이 체크포인트를 생성했나?
2. 학습 시점의 메트릭은 무엇이었나?
3. 어떤 데이터셋 버전이 사용됐나?
4. 롤백하면 정확히 어디로 돌아가는 것인가?

#### Contexta 없이

- 파일명은 run 참조가 아닙니다. 메트릭, 데이터셋, 환경과 연결되지 않습니다.
- "롤백"은 이전 `.pkl` 파일로 교체하는 것이며, 그게 맞는 파일인지 불확실합니다.
- 프로덕트 매니저에게 답변하려면 git log, Slack 검색, 노트북 탐색에 30분이 걸립니다.

#### Contexta 사용 시

```python
# 1단계: 모든 배포와 연결된 실행 조회
deployments = ctx.list_deployments(PROJECT_NAME)

# 2단계: 배포된 실행의 스냅샷 조회
snap = ctx.get_run_snapshot(run_c_ref)
# snap.run.name, snap.stages, snap.records (메트릭 + 데이터셋 이벤트)

# 3단계: 배포로부터 리니지 탐색
lineage = ctx.traverse_lineage(friday_deploy_ref)

# 4단계: 배포 실행 vs 안전한 기준선 비교
comparison = ctx.compare_runs(run_c_ref, run_b_ref)
```

`DeploymentExecution`은 배포를 배포된 정확한 실행과 영구적으로 연결합니다. 세 번의 API 호출이 30분간의 수작업을 대체합니다.

**주요 API:** `DeploymentExecution`, `list_deployments`, `get_run_snapshot`, `traverse_lineage`, `compare_runs`

---

## 그룹 3 — MLOps 및 배포

### 케이스 05: 자동화된 배포 게이트

**페르소나:** MLOps 엔지니어 / 현장 엔지니어  
**예제:** `examples/case_studies/case05_deployment_gate.py`

#### 상황

팀은 Slack 체크리스트로 모델을 배포합니다: "메트릭 확인했나요? 이전 버전과 비교했나요? 데이터를 검증했나요?" 한 분기 동안 세 번의 실패:

- **3월:** 잘못된 스테이지의 평가 메트릭으로 배포
- **4월:** 데이터셋 v2025-03-31로 run-c 배포 (CTR 하락 유발 — 케이스 04)
- **5월:** 실행에 메트릭이 전혀 없음 (evaluate 스테이지가 건너뛰어짐)

#### Contexta 없이

Slack 체크리스트는 사람이 올바른 항목을 기억하고 확인하는 것에 의존합니다. 3월 실패는 메트릭이 어떤 스테이지에서 왔는지 아무도 확인하지 않아서 통과됐습니다. 5월 실패는 체크박스에 "메트릭 ✓"라고 표시됐지만 evaluate 스테이지가 건너뛰어진 것을 아무도 눈치채지 못해서 통과됐습니다. 수작업 프로세스는 과거 실패 패턴을 기억하지 못합니다.

#### Contexta 사용 시

```python
def pre_deployment_gate(ctx, candidate_run_id, previous_deploy_run_id):
    # 검사 1: 오류 수준 진단 없음
    diag   = ctx.diagnose_run(candidate_run_id)
    errors = [i for i in diag.issues if i.severity == "error"]

    # 검사 2: 모든 필수 메트릭 존재
    snap     = ctx.get_run_snapshot(candidate_run_id)
    obs_keys = {o.key for o in snap.records if o.record_type == "metric"}
    missing  = [m for m in REQUIRED_METRICS if m not in obs_keys]

    # 검사 3: 이전 배포 대비 회귀 없음
    comp = ctx.compare_runs(previous_deploy_run_id, candidate_run_id)
    ...
```

| 시나리오 | 수작업 게이트 | 프로그래밍 게이트 |
|---------|------------|----------------|
| 잘못된 스테이지 메트릭 | 통과 (사람이 놓침) | 실패 (evaluate 스테이지에 메트릭 없음) |
| 데이터셋 버전 불일치 | 통과 (아무도 확인 안 함) | 실패 (DegradedRecord 존재) |
| evaluate 스테이지 건너뜀 | 통과 (체크박스 표시됨) | 실패 (필수 메트릭 없음) |

**주요 API:** `diagnose_run`, `get_run_snapshot`, `compare_runs`

---

### 케이스 06: Elena의 컴플라이언스 감사 추적

**페르소나:** 솔루션 아키텍트 / 컴플라이언스  
**예제:** `examples/case_studies/case06_compliance_audit.py`

#### 상황

Elena의 팀은 규제 대상 보험 클라이언트에게 AI 솔루션을 납품합니다. 클라이언트의 규제 기관이 프로덕션 모델을 감사하며 다섯 가지 질문을 합니다:

1. 프로덕션 모델 학습에 어떤 데이터셋 버전을 사용했나요?
2. 학습 시점의 평가 메트릭은 무엇이었나요 (추정치가 아닌 정확한 수치)?
3. 학습 시점의 Python 및 라이브러리 환경은 어땠나요?
4. 이 모델은 이전 버전과 어떻게 다른가요?
5. 배포는 누가 승인했나요?

팀은 Git 로그, 개인 Jupyter 노트북, Slack 스레드, 공유 드라이브를 이틀 동안 탐색했습니다. 일부 정보는 검색이 아닌 추정으로 작성됐습니다. 감사관은 거부했습니다: *"문서화된 증거를 제출하세요."*

#### Contexta 없이

- 데이터셋 버전: 노트북 셀이나 Slack 메시지에 기록됨. 둘 다 감사 가능하지 않습니다.
- 평가 메트릭: 스크립트의 stdout에 출력됐으나 스크롤 오프되거나 터미널이 닫혔을 수 있음.
- 환경: `requirements.txt`가 "오래됐을 수 있음".
- 모델 비교: "개선됐다고 생각함" — 구조화된 diff 없음.
- 답변에 이틀이 걸리고 일부는 추정치. 규제 기관은 추정치를 거부합니다.

#### Contexta 사용 시

```python
# Q1: 데이터셋 버전
snapshot      = ctx.get_run_snapshot(curr_run_ref)
dataset_event = next(e for e in snapshot.records if e.key == "training.dataset-registered")

# Q2: 원본 평가 메트릭
eval_records = [o for o in snapshot.records if o.record_type == "metric"]

# Q3: 학습 환경
audit = ctx.audit_reproducibility(curr_run_ref)
# audit.python_version, audit.platform, audit.package_count

# Q4: 이전 버전과 비교
env_diff = ctx.compare_environments(prev_run_ref, curr_run_ref)
comp     = ctx.compare_runs(prev_run_ref, curr_run_ref)

# Q5: 공식 감사 문서
report = ctx.build_snapshot_report(curr_run_ref)
```

모든 답변은 학습 시점에 기록된 레코드로 뒷받침됩니다 — 재구성이 아닙니다. 감사 패키지가 5초 이내에 조립됩니다.

**주요 API:** `EnvironmentSnapshot`, `get_run_snapshot`, `audit_reproducibility`, `compare_environments`, `compare_runs`, `build_snapshot_report`

---

## 그룹 4 — 데이터 엔지니어링

### 케이스 07: David의 알림 없는(Silent) 배치 작업 실패

**페르소나:** David, 데이터 엔지니어  
**예제:** `examples/case_studies/case07_batch_job_monitoring.py`

#### 상황

야간 ETL 잡이 ML 모델을 위한 피처를 가공합니다. 7일 중 5번째 밤에 잡이 종료 코드 0으로 완료됐지만, 업스트림 벤더가 API 응답 스키마를 변경해 피처 컬럼 하나를 조용히 잘라냈습니다. 벤더의 새 스키마가 조인이 의존하는 필드를 삭제했고 — 조인은 성공했지만 NULL을 반환했으며, 숫자 피처 컬럼이 조용히 0으로 채워졌습니다. 다운스트림 모델이 재학습됐고 정확도가 0.934에서 0.871로 하락했으며, 배치 잡이 "성공"했기 때문에 알림이 발생하지 않았습니다.

#### Contexta 없이

- 종료 코드 0이 스케줄러의 유일한 상태 신호
- 배치 잡 `status=completed`는 "올바른 출력"과 "0으로 채워진 컬럼"을 구분하지 않음
- 어느 밤이 정확도 하락을 유발했는지 모른 채 이틀간 디버깅
- 로그가 롤링됐을 수 있어 정확한 실패 재현을 위해 파이프라인 재실행 필요

#### Contexta 사용 시

```python
# 5번째 밤 피처 엔지니어링 스테이지가 DegradedRecord 발행
DegradedRecord(
    payload=DegradedPayload(
        category="verification", severity="warning",
        summary="null-rate-exceeded-threshold",
        details={"column": "purchase_intent_score", "null_rate": 0.98},
    )
)

# 즉시 감지
diag   = ctx.diagnose_run(night5_run_ref)
issues = [i for i in diag.issues if i.code == "degraded_record"]
# → 1 warning: null-rate-exceeded-threshold in feature-engineering stage
```

`BatchExecution` 레코드가 각 밤의 잡을 해당 실행, 스테이지, 레코드와 연결합니다. 주간 요약 테이블이 어느 밤에 저하가 있었는지 보여줍니다 — 재실행 없이.

**주요 API:** `BatchExecution`, `DegradedRecord`, `diagnose_run`

---

### 케이스 08: 업스트림 데이터 오염 윈도우

**페르소나:** MLE + 데이터 엔지니어 팀  
**예제:** `examples/case_studies/case08_upstream_contamination.py`

#### 상황

벤더가 3주 전 API 응답 스키마를 변경했습니다. 이 변경으로 `purchase_intent_score`가 `[0.0, 1.0]`에서 `[0.0, 0.1]`로 조용히 클램핑됐습니다 — 필드명은 동일해서 스키마 검증이 통과됐습니다. 오염 윈도우(4월 1일~21일) 동안 4개의 학습 실행이 있었습니다. 각 실행은 "정상"으로 보였습니다 — 메트릭이 약간 낮았지만 팀은 자연적 분산으로 생각했습니다. 오늘(4월 28일) 데이터 엔지니어가 다른 이슈를 디버깅하다 클램핑을 발견했습니다.

#### Contexta 없이

- 어떤 실행이 어떤 데이터 품질 이벤트와 겹치는지 기록 없음
- 영향받은 실행 식별에는 학습 날짜와 오염 윈도우를 여러 시스템에서 수동으로 대조해야 함
- 윈도우 중 "최고" 실행이 프로덕션에 승격됐을 수 있으며, 이를 프로그래밍 방식으로 격리할 방법 없음

#### Contexta 사용 시

```python
# 오염 실행에 학습 시점에 태그 부착
StructuredEventRecord(payload=StructuredEventPayload(
    event_key="data.contamination-window",
    message="4월 1일-21일 벤더 API 오염 윈도우 중 학습",
))

# 트리아지: 식별, 비교, 선택
contaminated_refs = [r for r in run_refs if was_in_window(r)]
comparison = ctx.compare_runs(clean_baseline_ref, latest_contaminated_ref)

# 오염 실행 중 "가장 좋아 보인" 것은 무엇인가 (신뢰하면 안 됨)?
false_best = ctx.select_best_run(contaminated_refs, "auc", higher_is_better=True)
```

이벤트 레코드가 학습 시점에 오염 윈도우를 태깅합니다. `compare_runs`는 오염된 실행이 깨끗한 기준선에서 얼마나 벗어났는지 보여줍니다. `select_best_run`은 승격됐을 실행을 식별하고 격리 대상임을 확인합니다.

**주요 API:** `StructuredEventRecord`, `compare_runs`, `select_best_run`

---

## 그룹 5 — AI 및 LLM 엔지니어링

### 케이스 09: Mia의 프롬프트별 평가

**페르소나:** Mia, AI 엔지니어  
**예제:** `examples/case_studies/case09_llm_per_prompt_evaluation.py`

#### 상황

Mia가 고객 지원 챗봇의 RAG 파이프라인을 평가합니다. 네 가지 카테고리(계정 질문, 결제 분쟁, 제품 문의, 에스컬레이션 시나리오)에 걸쳐 20개의 테스트 프롬프트를 실행하고 관련성, 충실도, 답변 길이를 점수로 매깁니다. 7번, 12번, 17번 프롬프트는 에스컬레이션 시나리오로, 리트리버가 관련 문서를 전혀 찾지 못해 관련성 점수가 거의 0에 가깝습니다.

문제: 집계 관련성이 0.79입니다. 품질 게이트를 통과합니다. 3개의 깨진 프롬프트가 집계에 묻힙니다. 해당 프롬프트가 프로덕션에 도달하면 챗봇이 에스컬레이션을 원하는 화난 고객에게 엉뚱한 답변을 반환합니다.

#### Contexta 없이

- 집계 메트릭만 사용 가능: `mean_relevance = 0.79`
- 어떤 특정 프롬프트가 깨졌는지 감지하려면 원시 평가 출력(JSON 파일 또는 데이터프레임)을 분석하는 커스텀 코드를 작성해야 함
- 평가 스위트가 커질수록 커스텀 분석 코드도 커지며, 유지보수가 거의 안 됨

#### Contexta 사용 시

```python
# 각 프롬프트가 SampleObservation; 메트릭은 샘플별로 기록
for i, prompt in enumerate(PROMPTS):
    sample_ref = f"sample:{PROJECT}.run01.evaluate.prompt-{i+1:02d}"
    store.samples.put_sample_observation(SampleObservation(
        sample_observation_ref=sample_ref, ...
    ))
    record_store.append(MetricRecord(..., payload=MetricPayload(
        metric_key="relevance", value=scores[i]["relevance"]
    )))

# 분석: 실패 프롬프트 찾기
snapshot = ctx.get_run_snapshot(run_ref)
for rec in snapshot.records:
    if rec.record_type == "metric" and rec.key == "relevance" and rec.value < 0.3:
        print(f"FAIL: {rec.stage_id} / {rec.sample_id}")
```

샘플별 `MetricRecord`는 집계가 아닌 전체 분포를 질의 가능하게 합니다. 3개의 실패 프롬프트는 단순한 필터로 찾을 수 있습니다 — 커스텀 분석 코드 없이.

**주요 API:** `SampleObservation`, `MetricRecord` (샘플별), `get_run_snapshot`

---

### 케이스 10: RAG 파이프라인 스테이지별 분해

**페르소나:** AI 엔지니어  
**예제:** `examples/case_studies/case10_rag_pipeline_decomposition.py`

#### 상황

4단계 RAG 파이프라인(retrieve → rerank → generate → evaluate)이 프로덕션에 있습니다. 종단 간 `answer_quality`가 기준선 배포의 0.87에서 최신 버전의 0.64로 하락했습니다. 어떤 스테이지가 원인인지 아무도 모릅니다. 팀의 가설:

- retrieve 스테이지가 정밀도가 낮은 문서를 반환하고 있을 수 있음
- rerank 모델이 새 쿼리 유형에서 저하됐을 수 있음
- generation 모델이 드리프트됐을 수 있음
- 측정 노이즈일 수 있음

스테이지별 메트릭 없이는 각 가설 검증을 위해 별도의 조사 실행이 필요합니다.

#### Contexta 없이

- 종단 간 메트릭: `answer_quality = 0.64`. 사용 가능한 숫자가 이것뿐입니다.
- 각 가설 검증을 위해 스테이지를 계측하고, 파이프라인을 재실행하고, 가설별 수치가 변했는지 확인해야 함
- 4개 가설 = 4번의 조사 사이클 = 며칠의 작업

#### Contexta 사용 시

```python
# 학습 시 스테이지별 메트릭 기록
# retrieve 스테이지:  retrieval-precision
# rerank 스테이지:    rerank-ndcg
# generate 스테이지:  generation-fluency
# evaluate 스테이지:  answer-quality

comparison = ctx.compare_runs(v1_ref, v2_ref)
for sc in comparison.stage_comparisons:
    for d in sc.metric_deltas:
        print(f"{sc.stage_name}/{d.metric_key}: {d.left_value:.3f} → {d.right_value:.3f}")

# 출력:
# retrieve/retrieval-precision: 0.810 → 0.620   ← 근본 원인
# rerank/rerank-ndcg:           0.870 → 0.790   ← 연쇄 영향
# generate/generation-fluency:  0.880 → 0.760   ← 연쇄 영향
# evaluate/answer-quality:      0.870 → 0.640   ← 최종 결과
```

스테이지 스코프 `MetricRecord`가 하나의 `compare_runs` 호출로 근본 원인 스테이지를 드러냅니다. 연쇄 저하 패턴(retrieve → 모든 하위 스테이지)이 즉시 명확해집니다.

**주요 API:** 스테이지 스코프 `MetricRecord`, `compare_runs`, `diagnose_run`

---

## 그룹 6 — 팀 운영 및 납품

### 케이스 11: Alex의 온보딩 요약

**페르소나:** Alex, 팀 리드  
**예제:** `examples/case_studies/case11_project_history_onboarding.py`

#### 상황

신규 ML 엔지니어 Jamie가 팀에 합류합니다. 이탈률 예측 모델은 4개월간 운영됐습니다: 6개의 학습 실행, 2번의 배포, 여러 번의 재학습에 걸쳐 성능이 추적됩니다. Jamie는 첫날에 5가지 질문에 대한 답이 필요합니다:

1. 학습 실행이 몇 개나 있고 이름은?
2. 시간에 따른 정확도 변화는?
3. 어떤 실행이 프로덕션에 배포됐나?
4. 객관적으로 가장 좋은 실행은?
5. 모든 실행에 걸친 구조화된 비교 리포트는?

도구 없이는 Alex가 Git 로그, Confluence 페이지, 오래된 Slack 스레드를 검색하며 반나절을 소비해야 하는데, 이 문서는 2주 후에 바로 구식이 됩니다.

#### Contexta 없이

- 프로젝트 이력이 Git, Confluence, Slack, 개별 노트북에 흩어져 있음
- 직접 작성한 문서는 스냅샷 — 새 실행이 생성될 때 자동으로 업데이트되지 않음
- "가장 좋은 실행은?"에 답하려면 각 노트북을 열어 최종 메트릭을 찾아 수동 순위 매기기 필요

#### Contexta 사용 시

```python
all_runs    = ctx.list_runs(PROJECT_NAME)
deployments = ctx.list_deployments(PROJECT_NAME)
best_ref    = ctx.select_best_run(run_refs, "accuracy", higher_is_better=True)
report      = ctx.build_multi_run_report(run_refs)
```

요약은 온디맨드로 재생성됩니다. 등록된 모든 실행의 현재 상태를 반영합니다 — 수동 유지보수 불필요. `build_multi_run_report`는 HTML 렌더링이나 CSV 내보내기가 가능한 구조화된 섹션 리포트를 생성합니다.

**주요 API:** `list_runs`, `list_deployments`, `select_best_run`, `build_multi_run_report`

---

### 케이스 12: Tom의 납품 품질 인증서

**페르소나:** Tom, 현장 배포 엔지니어 (FDE)  
**예제:** `examples/case_studies/case12_delivery_quality_certificate.py`

#### 상황

Tom이 FinanceBank Corp에 학습된 모델을 납품합니다. 클라이언트의 조달팀은 AI 모델을 수락하기 전에 공식 "모델 품질 인증서"를 요구합니다:

1. 사용된 학습 데이터 버전
2. 평가 메트릭 (추정치가 아닌 정확한 수치)
3. 학습 환경 (Python 버전, 주요 패키지)
4. 합의된 품질 임계값에 대한 항목별 PASS/FAIL
5. 전체 PASS 또는 FAIL 결정

도구 없이 Tom은 학습 로그, `requirements.txt`, 노트북 출력에서 인증서를 수동으로 조립합니다 — 납품당 3~4시간 작업에 검토 사이클까지 더하면 1~2일 지연이 발생합니다.

#### Contexta 없이

| 단계 | 수작업 | 시간 |
|------|-------|------|
| 메트릭 | 학습 로그 열기, Word 문서에 수동 복사 | 30분 |
| 환경 | `requirements.txt` 확인 (오래됐을 수 있음), Python 버전 붙여넣기 | 20분 |
| 데이터셋 버전 | 기억이나 Slack 검색으로 | 15분 |
| 임계값 검사 | Word에서 수동 비교 | 20분 |
| 클라이언트 검토 사이클 | "AUC 수치가 맞지 않음" | +1일 |

#### Contexta 사용 시

```python
# 모든 증거가 학습 시점에 기록됨
snapshot = ctx.get_run_snapshot(run_ref)
audit    = ctx.audit_reproducibility(run_ref)

# 임계값 검사
THRESHOLDS = {"accuracy": 0.90, "auc": 0.93, "f1": 0.88, ...}
for metric, threshold in THRESHOLDS.items():
    value  = next(r.value for r in snapshot.records if r.key == metric)
    status = "PASS" if value >= threshold else "FAIL"
    print(f"  {metric:<12} {value:.4f}  (>= {threshold})  [{status}]")

# 공식 문서
report = ctx.build_snapshot_report(run_ref)
```

인증서가 12초 이내에 조립됩니다. 모든 수치는 기록된 `MetricRecord`로 뒷받침됩니다 — 기억에서 추정한 값이 아닙니다. 수치가 재현 가능하기 때문에 클라이언트 검토 사이클이 줄어듭니다.

**주요 API:** `EnvironmentSnapshot`, `StructuredEventRecord`, `get_run_snapshot`, `audit_reproducibility`, `build_snapshot_report`

---

## 예제 실행하기

각 스크립트는 외부 서비스 없이 독립 실행됩니다:

```bash
uv run python examples/case_studies/case01_scattered_experiments.py
uv run python examples/case_studies/case06_compliance_audit.py
# ... 등
```

전체 12개를 한번에 실행:

```bash
for f in examples/case_studies/case*.py; do
    echo "=== $f ==="
    uv run python "$f"
    echo
done
```

## 참고 문서

- [시작하기](./getting-started.md) — 5분 안에 첫 실행
- [핵심 개념](./core-concepts.md) — Run, Stage, Record, Deployment 모델
- [도구 및 인터페이스](./tools-and-surfaces.md) — 어떤 API를 언제 사용할지
- [어댑터](./adapters.md) — OpenTelemetry 및 MLflow 브릿지
