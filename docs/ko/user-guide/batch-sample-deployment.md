# 배치(Batch), 샘플(Sample), 배포(Deployment) 추적

이 페이지에서는 Contexta의 세 가지 추가 실행 컨텍스트 타입을 설명합니다:
Batch, Sample, Deployment.

이 타입들은 반복 데이터 처리, 항목별 관찰, 모델 배포 추적이 필요한 워크플로우를
위해 기본 Run → Stage 계층 구조를 확장합니다.

## 배치 (Batch)

배치 실행은 스테이지 내의 하나의 독립적인 데이터 처리 단위를 나타냅니다.

주요 사용 사례:

- 학습 루프의 한 에포크(epoch)
- 스트리밍 파이프라인의 한 청크(chunk)
- 배치 임포트 워크플로우의 한 파일

배치 실행은 스테이지에 종속됩니다:

```
Run → Stage → Batch
```

### Ref 형식

```
batch:{프로젝트}.{런}.{스테이지}.{배치_이름}
```

예시: `batch:my-proj.run-01.train.epoch-0`

### 상태 값

`open` | `completed` | `failed` | `cancelled`

`completed`와 `failed`는 `ended_at`이 필요합니다.

### 배치 로깅

```python
from contexta.contract import BatchExecution

batch = BatchExecution(
    batch_execution_ref="batch:my-proj.run-01.train.epoch-0",
    run_ref="run:my-proj.run-01",
    stage_execution_ref="stage:my-proj.run-01.train",
    batch_name="epoch-0",
    status="completed",
    started_at="2025-01-01T00:01:00Z",
    ended_at="2025-01-01T00:02:00Z",
    order_index=0,
)
ctx.metadata_store.batches.put_batch_execution(batch)
```

### 배치 쿼리

```python
batches = ctx.list_batches("run:my-proj.run-01")
for b in batches:
    print(b.name, b.status, b.started_at)
```

---

## 샘플 (Sample)

샘플 관찰은 스테이지 또는 배치 처리 중 발견된 하나의 항목을 기록합니다.

주요 사용 사례:

- 검증 과정에서의 한 입력 행
- 데이터셋 스캔에서의 한 이미지
- 추론 배치에서의 한 예측값

샘플은 스테이지에 종속되며, Ref는 부모 스테이지 이름과 샘플 이름을
네 번째 컴포넌트로 인코딩해야 합니다:

### Ref 형식

```
sample:{프로젝트}.{런}.{스테이지}.{샘플_이름}
```

예시: `sample:my-proj.run-01.train.s-0001`

참고: 4-컴포넌트 제약으로 인해 샘플 이름에 점(.)을 포함할 수 없습니다.

### 샘플 로깅

```python
from contexta.contract import SampleObservation

sample = SampleObservation(
    sample_observation_ref="sample:my-proj.run-01.train.s-0001",
    run_ref="run:my-proj.run-01",
    stage_execution_ref="stage:my-proj.run-01.train",
    sample_name="s-0001",
    observed_at="2025-01-01T00:01:30Z",
)
ctx.metadata_store.samples.put_sample_observation(sample)
```

### 샘플 쿼리

```python
samples = ctx.list_samples("run:my-proj.run-01")
for s in samples:
    print(s.name, s.observed_at)
```

---

## 배포 (Deployment)

배포 실행은 모델 또는 아티팩트가 환경에 배포된 인스턴스를 추적합니다.

주요 사용 사례:

- 서빙 엔드포인트에 푸시된 모델
- 스테이징으로 승격된 체크포인트
- 모델 레지스트리에 등록된 학습된 아티팩트

배포는 프로젝트에 범위가 지정되며, 배포된 아티팩트를 생성한 런과
선택적으로 연결할 수 있습니다:

```
Project → Deployment (→ Run, 선택사항)
```

### Ref 형식

```
deployment:{프로젝트}.{배포_이름}
```

예시: `deployment:my-proj.model-v1`

### 배포 로깅

```python
from contexta.contract import DeploymentExecution

deploy = DeploymentExecution(
    deployment_execution_ref="deployment:my-proj.model-v1",
    project_ref="project:my-proj",
    deployment_name="model-v1",
    status="completed",
    started_at="2025-01-01T00:09:00Z",
    ended_at="2025-01-01T00:10:00Z",
    run_ref="run:my-proj.run-01",   # 생성한 런과의 선택적 연결
)
ctx.metadata_store.deployments.put_deployment_execution(deploy)
```

### 배포 쿼리

```python
deployments = ctx.list_deployments("my-proj")
for d in deployments:
    print(d.name, d.status, d.run_id)
```

---

## 스냅샷 리포트에서의 표현

`ctx.build_snapshot_report(run_ref)`를 호출하면, 데이터가 있을 경우
리포트에 **Batches**, **Deployments**, **Samples** 섹션이 자동으로 포함됩니다.

```python
report = ctx.build_snapshot_report("run:my-proj.run-01")
for section in report.sections:
    print(section.title)
# → Run Summary, Stages, Artifacts, Batches, Deployments, Samples, Diagnostics, ...
```

---

## 진단 (Diagnostics)

`DiagnosticsService`는 배치와 배포의 상태를 자동으로 검사합니다:

| 조건 | 심각도 | 이슈 키 |
|---|---|---|
| `BatchExecution.status == "failed"` | `error` | `failed_batch` |
| `BatchExecution`이 비종료 상태 | `warning` | `incomplete_batch` |
| `DeploymentExecution.status == "failed"` | `error` | `failed_deployment` |

이 이슈들은 스냅샷 리포트의 Diagnostics 섹션에 표시됩니다.

---

## 예제

완전한 실행 가능 예제는
[`examples/batch_sample/batch_sample_demo.py`](../../../examples/batch_sample/batch_sample_demo.py)를
참고하세요.
