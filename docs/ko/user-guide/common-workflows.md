# 일반적인 Contexta 워크플로

이 가이드는 워크스페이스에 이미 표준 데이터가 포함된 후 대부분의 사용자가 관심을 갖는 일상적인 작업에 초점을 맞춥니다.

가장 안전한 기본 원칙은 다음과 같습니다:

- `Contexta`에서 시작하세요.
- 하나의 워크스페이스에 바인딩하세요.
- 우선 퍼사드(facade) 메서드를 사용하세요.
- 더 많은 제어가 필요할 때만 직접 스토어(store) 또는 복구(recovery) API로 이동하세요.

아직 작동하는 워크스페이스를 만들지 않았다면 [시작하기](./getting-started.md)를 먼저 완료하세요.

## 워크스페이스 열기

대부분의 워크플로는 하나의 퍼사드를 통해 하나의 워크스페이스를 여는 것으로 시작합니다:

```python
from pathlib import Path

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig

ctx = Contexta(
    config=UnifiedConfig(
        project_name="guide-proj",
        workspace=WorkspaceConfig(root_path=Path(".contexta")),
    )
)
```

논리적 프로젝트 또는 실험군(experiment family)당 하나의 워크스페이스를 사용하세요. 그렇게 하면 실행 참조(run refs), 리포트 및 복구 작업을 더 쉽게 파악할 수 있습니다.

## 단일 실행(Run) 조사

표준 실행 참조(canonical run ref)를 이미 알고 있다면, 가장 빠른 읽기 경로는 실행 스냅샷(run snapshot)입니다:

```python
snapshot = ctx.get_run_snapshot("run:guide-proj.demo-run")

print(snapshot.run.run_id)
print(snapshot.run.status)
print(len(snapshot.stages))
print(len(snapshot.records))
print(len(snapshot.artifacts))
```

다음과 같은 질문에 답하고 싶을 때 이 워크플로를 사용하세요:

- 이 실행에서 무슨 일이 일어났는가?
- 어떤 스테이지들이 포함되었는가?
- 워크스페이스에 이미 얼마나 많은 증거 데이터(evidence)가 존재하는가?

## 두 실행 비교

두 개 이상의 실행 결과를 조사해야 할 때 실행 비교는 그 다음으로 가장 흔한 워크플로입니다:

```python
comparison = ctx.compare_runs(
    "run:guide-proj.demo-run",
    "run:guide-proj.demo-run-v2",
)

print(comparison.summary)
print(len(comparison.stage_comparisons))
```

여러 실행 후보를 비교하여 메트릭 기준 최적의 실행 하나를 선택하고 싶다면:

```python
best = ctx.select_best_run(
    [
        "run:guide-proj.demo-run",
        "run:guide-proj.demo-run-v2",
    ],
    metric_key="accuracy",
    higher_is_better=True,
)

print(best)
```

다음 사항들을 조사하고 싶을 때 비교 기능을 사용하세요:

- 메트릭의 변화
- 스테이지 레벨의 차이점
- 리포트 레벨의 차이점
- 특정 메트릭에 대한 최적 실행 선택

## 리포트 빌드

데이터가 표준 형식으로 갖춰지면 리포트 생성 또한 동일한 퍼사드에서 수행됩니다:

```python
snapshot_report = ctx.build_snapshot_report("run:guide-proj.demo-run")
compare_report = ctx.build_run_report(
    "run:guide-proj.demo-run",
    "run:guide-proj.demo-run-v2",
)
project_report = ctx.build_project_summary_report("guide-proj")
```

생성된 리포트는 후속 작업에 적합한 형식으로 구체화할 수 있습니다:

```python
markdown_text = snapshot_report.to_markdown()
html_text = snapshot_report.to_html()
json_payload = snapshot_report.to_json()
```

다음과 같은 용도로 출력이 필요할 때 리포트 생성을 사용하세요:

- 검토(Review)
- 공유
- 아카이브
- 나중에 HTML로 렌더링하거나 다른 내보내기 워크플로로 연결

## 진단(Diagnostics) 조사

시스템이 불완전하거나 의심스러운 상태를 직접 지적해주기를 원할 때 진단 기능을 사용합니다:

```python
diagnostics = ctx.diagnose_run("run:guide-proj.demo-run")

for issue in diagnostics.issues:
    print(issue.severity, issue.code, issue.summary)
```

다음과 같은 질문에 더 빠르게 답을 얻고 싶을 때 진단 기능을 사용하세요:

- 무엇이 불완전해 보이는가?
- 무엇이 일관되지 않아 보이는가?
- 어떤 이슈를 가장 먼저 조사해야 하는가?

## 리니지(Lineage) 추적

리니지는 단일 실행을 넘어 엔티티 간의 관계를 파악해야 할 때 도움이 됩니다:

```python
traversal = ctx.traverse_lineage(
    "artifact:guide-proj.demo-run.model",
    direction="outbound",
    max_depth=3,
)

print(len(traversal.edges))
print(len(traversal.visited_refs))
```

다음과 같은 질문을 하고 싶을 때 리니지를 사용하세요:

- 이 아티팩트는 어디서 왔는가?
- 이 결과에 의존하는 것은 무엇인가?
- 이 대상의 상위(upstream) 또는 하위(downstream)에는 무엇이 있는가?

## 메트릭 추세 분석

단일 비교가 아닌 실행 간의 변동에 대한 의문이 있다면 추세 쿼리(trend query)를 사용하세요:

```python
trend = ctx.get_metric_trend(
    "accuracy",
    project_name="guide-proj",
)

print(trend.metric_key)
print(len(trend.points))
```

추세 워크플로는 다음과 같은 경우에 유용합니다:

- 여러 실행에 걸친 메트릭 드리프트(drift) 확인
- 시간에 따른 프로젝트 수준의 진행 상황 확인
- 더 깊은 비교가 필요한 가치 있는 지점 파악

## 런타임 캡처(Runtime Capture) 미리보기

런타임 캡처 인터페이스는 이미 사용 가능하지만, 현재 프로토타입에서는 가장 보수적인 읽기/쿼리 온보딩 경로보다는 미래 지향적인 쓰기 경로로 이해해야 합니다.

```python
with ctx.run("training-run") as run:
    run.event("dataset.loaded", message="dataset prepared")
    run.metric("accuracy", 0.93, unit="ratio")

    with run.stage("train") as stage:
        stage.metric("loss", 0.42)
```

다음과 같은 경우에 런타임 캡처를 사용하세요:

- 애플리케이션 코드 내의 실시간 인스트루먼테이션
- 스코프(scope)를 인식하는 이벤트 및 메트릭 방출
- 생명주기 및 캡처 동작을 위한 단일 제품 인터페이스

쓰기에서 쿼리/리포트로 이어지는 현재 검증된 가장 짧은 경로를 확인하려면 [시작하기](./getting-started.md)의 표준 데이터 튜토리얼을 계속 사용하세요.

## 다른 기능이 필요한 경우

다음이 목표라면 현재의 퍼사드(facade)를 유지하세요:

- 단일 실행 조사
- 두 실행 비교
- 리포트 빌드
- 문제 진단
- 리니지 추적

다음이 필요하다면 고급 가이드(advanced guide)로 이동하세요:

- 명시적인 설정 해결(config resolution)
- 저장소(store) 직접 접근
- 백업 또는 복구 계획

## 다음 단계

다음 문서로 이어집니다:

- [고급 사용법](./advanced.md)
- [테스트 가이드](./testing.md)
