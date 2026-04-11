# Contexta 시작하기

이 가이드는 설치부터 첫 번째 ML 실행 로깅까지의 과정을 안내합니다.

## 시작하기 전에

필수 사양:

- Python `>=3.14`
- `.contexta/` 폴더를 생성할 수 있는 로컬 파일 시스템

클라우드 계정, API 키, 별도 인프라 설치가 필요하지 않습니다.

## 1단계: 설치

```bash
pip install contexta
```

또는 `uv` 사용 시:

```bash
uv add contexta
```

ML 프레임워크 extras는 필요한 것만 설치하세요:

```bash
pip install "contexta[sklearn]"       # scikit-learn
pip install "contexta[torch]"         # PyTorch
pip install "contexta[transformers]"  # HuggingFace Transformers
```

### 소스에서 개발 설치 (기여자용)

Contexta에 기여하거나 소스 트리에서 예제를 실행하려면:

```bash
git clone https://github.com/eastlighting1/Contexta.git
cd Contexta
uv sync --dev
```

## 2단계: 퀵스타트 예제 실행

가장 빠른 엔드 투 엔드 예제는 `contexta`와 `scikit-learn`만 있으면 됩니다:

```bash
pip install "contexta[sklearn]"
python examples/quickstart/qs01_sklearn_tabular.py
```

이 스크립트는 다음을 수행합니다:

1. UCI Wine 데이터셋을 로드하여 train / test 세트로 분리합니다.
2. SVM 베이스라인과 Random Forest를 훈련하면서 5-fold CV 메트릭과 평가 메트릭을 각 실행이 완료될 때 로컬 `.contexta/` 워크스페이스에 기록합니다.
3. `compare_runs`로 두 실행을 비교하고, `select_best_run`으로 최적 모델을 선택하여 배포로 등록합니다.
4. 최적 실행에 대해 `diagnose_run`과 `build_snapshot_report`를 실행합니다.

스크립트 실행 후 워크스페이스는 `examples/quickstart/.contexta/wine-quality-clf/`에 생성됩니다.

## 3단계: 핵심 개념 이해하기

Contexta는 옵저버빌리티 데이터를 세 가지 진실 평면(truth planes)으로 구성합니다:

| 평면 | 저장 내용 |
|------|-----------|
| Metadata | 프로젝트, 실행, 스테이지, 환경, 배포, 샘플 |
| Records | MetricRecord, StructuredEventRecord, DegradedRecord 등 |
| Artifacts | 모델 파일, 데이터셋 스냅샷, 바이너리 블롭 |

모든 항목은 **표준 참조(canonical ref)** 문자열로 식별됩니다:

```
project:{name}
run:{project}.{run}
stage:{project}.{run}.{stage}
record:{project}.{run}.{id}
environment:{project}.{run}.{snap}
deployment:{project}.{deploy}
```

## 4단계: 첫 번째 실행 작성

```python
from datetime import datetime, timezone
from pathlib import Path
from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig
from contexta.contract import (
    Project, Run, StageExecution,
    MetricPayload, MetricRecord, RecordEnvelope,
)

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

ctx = Contexta(config=UnifiedConfig(
    project_name="my-project",
    workspace=WorkspaceConfig(root_path=Path(".contexta")),
))
store = ctx.metadata_store

# 프로젝트와 실행 등록
store.projects.put_project(
    Project(project_ref="project:my-project", name="my-project", created_at=now())
)
run_start = now()
store.runs.put_run(
    Run(run_ref="run:my-project.run-01", project_ref="project:my-project",
        name="run-01", status="open", started_at=run_start, ended_at=None)
)

# 스테이지 등록
store.stages.put_stage_execution(
    StageExecution(stage_execution_ref="stage:my-project.run-01.train",
                   run_ref="run:my-project.run-01", stage_name="train",
                   status="completed", started_at=run_start, ended_at=now(), order_index=0)
)

# 메트릭 기록
ts = now()
ctx.record_store.append(MetricRecord(
    envelope=RecordEnvelope(
        record_ref="record:my-project.run-01.r00001", record_type="metric",
        recorded_at=ts, observed_at=ts, producer_ref="getting-started",
        run_ref="run:my-project.run-01",
        stage_execution_ref="stage:my-project.run-01.train",
        completeness_marker="complete", degradation_marker="none",
    ),
    payload=MetricPayload(metric_key="accuracy", value=0.95, value_type="float64"),
))

# 실행 완료 처리
store.runs.put_run(
    Run(run_ref="run:my-project.run-01", project_ref="project:my-project",
        name="run-01", status="completed", started_at=run_start, ended_at=now())
)

store.close()
```

## 5단계: 쿼리 및 리포트

```python
snapshot = ctx.get_run_snapshot("run:my-project.run-01")
for rec in snapshot.records:
    print(rec.key, rec.value)

report = ctx.build_snapshot_report("run:my-project.run-01")
print(report.title)
for section in report.sections:
    print(" -", section.title)
```

## 자주 묻는 질문

### PYTHONPATH를 설정해야 하나요?

아니요. `pip install contexta` 또는 `uv add contexta`를 하면 패키지가 Python 경로에 정상적으로 추가됩니다. `PYTHONPATH=src`는 설치 없이 저장소 소스 트리에서 직접 스크립트를 실행할 때만 필요합니다.

### 클라우드 계정이나 API 키가 필요한가요?

아니요. Contexta는 완전히 로컬에서 동작합니다. `.contexta/` 워크스페이스는 파일 시스템의 디렉터리입니다.

### 표준 참조(canonical ref) 형식이란 무엇인가요?

전체 참조 문법은 [핵심 개념](./core-concepts.md)에서 확인하세요.

## 다음 단계

- [주요 기능](./key-features.md)
- [도구 및 인터페이스](./tools-and-surfaces.md)
- [핵심 개념](./core-concepts.md)
- [일반적인 워크플로우](./common-workflows.md)
- [케이스 스터디](./case-studies.md)
- [`examples/quickstart/`](../../../examples/quickstart/README.md)
- [`examples/case_studies/`](../../../examples/case_studies/README.md)
