# Contexta 도구 및 인터페이스 (Tools And Surfaces)

이 페이지는 `Contexta` 제품 인터페이스가 어떻게 구성되어 있으며 신규 사용자가 어디서부터 시작해야 하는지 설명합니다.

가장 중요한 규칙은 간단합니다:

- `Contexta`에서 시작하세요.
- 더 많은 제어가 필요할 때만 하위 네임스페이스로 이동하세요.

## 여기서 시작하세요

제품을 처음 접한다면 여기서 시작하세요:

```python
from contexta import Contexta
```

루트 퍼사드(facade)가 기본 공용 진입점입니다.

## 인터페이스 카테고리 (Surface Categories)

`Contexta` 문서에서는 세 가지 라벨을 사용합니다:

- `Stable` (안정)
  - 권장되는 공용 계약(contract)
- `Advanced` (고급)
  - 공용이지만 주로 운영자나 파워 유저 워크플로를 위한 공간
- `Internal` (내부)
  - 구현 세부 사항이며 공용 임포트 대상이 아님

## 공용 인터페이스 맵 (Public Surface Map)

| 인터페이스 | 상태 | 용도 | 여기서 시작할까요? |
| --- | --- | --- | --- |
| `Contexta` | Stable | 핵심 제품 흐름을 위한 통합 퍼사드 | 예 |
| `contexta.config` | Stable | 설정 모델, 프로필, 환경 변수 재정의 | 가끔 |
| `contexta.contract` | Stable | 표준 모델, 검증, 직렬화 | 대개 아니오 |
| `contexta.capture` | Stable | 런타임 스코프, 방출, 캡처 헬퍼 | 가끔 |
| `contexta.store.metadata` | Stable | 메타데이터 트루스 플레인 접근 | 대개 아니오 |
| `contexta.store.records` | Stable | 레코드 트루스 플레인, 스캔/재생/내보내기 | 대개 아니오 |
| `contexta.store.artifacts` | Stable | 아티팩트 트루스 플레인, 검증/가져오기/내보내기 | 대개 아니오 |
| `contexta.interpretation` | Stable | 쿼리, 비교, 진단, 리니지, 리포트 | 가끔 |
| `contexta.recovery` | Advanced | 재생, 백업, 복구 | 아니오 |
| CLI | Stable | 명령줄 조사 및 운영자 작업 | 예, 쉘 워크플로를 선호하는 경우 |
| 내장 HTTP / UI | Stable | 읽기/조사를 위한 로컬 전용 전달 인터페이스 | 아니오, 브라우저 접근이 특별히 필요한 경우 제외 |

## 인터페이스 세부 사항

### `Contexta`

다음의 경우에 `Contexta`를 사용하세요:

- 주요 Python 진입점이 필요할 때
- 설정과 워크스페이스 바인딩을 소유하는 단일 객체가 필요할 때
- 쿼리, 비교, 진단, 리니지 및 리포트 흐름에 접근할 단일 위치가 필요할 때

거의 모든 사용자에게 권장되는 시작 지점입니다.

### `contexta.config`

다음의 경우에 `contexta.config`를 사용하세요:

- 명시적인 `UnifiedConfig` 제어가 필요할 때
- 프로필 선택이 필요할 때
- 환경 변수 재정의를 처리해야 할 때
- 직접적인 설정 모델이 필요할 때

기본 퍼사드 생성 방식이 충분하지 않을 때 여기서 시작하세요.

### `contexta.contract`

다음 항목들을 직접 다룰 때 `contexta.contract`를 사용하세요:

- 표준 모델 (Canonical models)
- `StableRef`
- 검증 (Validation)
- 직렬화 (Serialization)

이 인터페이스는 안정적이지만, 대부분의 신규 사용자에게 최우선으로 필요한 것은 아닙니다.

### `contexta.capture`

다음에 대해 더 직접적인 제어가 필요할 때 `contexta.capture`를 사용하세요:

- 런타임 스코프
- 캡처 방출 (emissions)
- 캡처 결과 타입
- 싱크(sink) 관련 캡처 동작

퍼사드 레벨의 캡처 경로가 충분히 구체적이지 않을 때 사용합니다.

### `contexta.store.metadata`

다음에 직접 접근해야 할 때 사용하세요:

- 프로젝트 (Projects)
- 실행 (Runs)
- 스테이지 (Stages)
- 관계 (Relations)
- 프로버넌스 (Provenance)
- 메타데이터 마이그레이션 또는 무결성 헬퍼

안정적인 공용 인터페이스이지만 고급 기능에 해당합니다.

### `contexta.store.records`

다음의 경우에 사용하세요:

- 레코드 추가
- 스캔
- 재생 (Replay)
- 내보내기 (Export)
- 레코드 플레인에서의 무결성 및 복구 작업

운영자 및 고급 데이터 경로 워크플로에서 가장 중요하게 사용됩니다.

### `contexta.store.artifacts`

다음의 경우에 사용하세요:

- 아티팩트 수집 (ingest)
- 아티팩트 검증
- 아티팩트 가져오기/내보내기
- 보존 계획 (retention planning)
- 격리(quarantine) 및 복구 흐름

아티팩트 플레인의 공용 홈입니다.

### `contexta.interpretation`

표준 저장 데이터에 대한 읽기 중심 분석을 원할 때 사용하세요:

- 쿼리
- 비교
- 진단
- 리니지
- 리포트

루트 퍼사드 다음으로 두 번째로 중요한 안정적인 인터페이스인 경우가 많습니다.

### `contexta.recovery`

운영자 워크플로를 위해 사용하세요:

- 재생 (replay)
- 백업 (backup)
- 복구 (restore)

공용 인터페이스이지만 의도적으로 `Advanced`로 문서화되어 있습니다.

### `contexta.adapters`

외부 시스템과의 선택적 통합에 사용하세요.

내장 경량 어댑터 (외부 의존성 없음):

- `contexta.adapters.export` — CSV 내보내기 헬퍼
- `contexta.adapters.html` — HTML 렌더링 헬퍼
- `contexta.adapters.notebook` — 노트북 표시 인터페이스

벤더 게이팅 어댑터 (의존성 없으면 `DependencyError` 발생):

- `contexta.adapters.otel` — OpenTelemetry 브릿지 (`[otel]` extra)
- `contexta.adapters.mlflow` — MLflow Tracking 브릿지 (`[mlflow]` extra)

`StdoutSink`는 extra 없이 `contexta.capture.sinks`에서 사용 가능합니다.

자세한 내용은 [어댑터](./adapters.md)를 참고하세요.

### `ctx.notebook`

Jupyter 또는 IPython 환경에서 작업할 때 `ctx.notebook`을 사용하세요.

이 프로퍼티는 `show_run()`, `compare_runs()`, `show_metric_trend()`,
DataFrame 변환 헬퍼를 제공합니다. IPython 없이도 동작하며 — 표시 호출은
우아하게 저하(graceful degradation)됩니다.

자세한 내용은 [노트북 인터페이스](./notebook.md)를 참고하세요.

## CLI 및 HTTP/UI

### CLI

표준 CLI 대상은 `contexta`입니다.

다음의 경우에 CLI를 사용하세요:

- 쉘 중심의 워크플로
- 실행 결과 조사
- 비교
- 리포트 생성
- 운영자 작업

CLI는 공용 인터페이스의 일부이지만, 프로토타입 전환 기간 동안 명명 및 패키징 정렬이 계속 진행 중입니다.

### 내장 HTTP / UI

다음의 경우에 내장 HTTP/UI를 사용하세요:

- 로컬 브라우저 기반의 조사
- 읽기 흐름을 위한 JSON 전송
- 동일한 제품 시맨틱을 기반으로 한 로컬 전용 전달 인터페이스

중요한 경계:

- 별도의 SaaS 플랫폼이 아닙니다.
- 주요 쓰기 인터페이스가 아닙니다.
- 로컬 전달 어댑터로 이해해야 합니다.

## 직접 사용해서는 안 되는 내부 네임스페이스

다음 네임스페이스는 공용 임포트 대상이 아닙니다:

- `contexta.api`
- `contexta.runtime`
- `contexta.common`
- `contexta.surfaces`

저장소 내에 실제 구현 모듈로 존재할 수 있지만, 신규 사용자가 기반으로 삼아야 할 계약(contract)은 아닙니다.

## 어떤 인터페이스를 선택해야 하나요?

### 그냥 바로 시작하고 싶어요

다음을 사용하세요:

- `Contexta`
- README 퀵스타트

### 명시적인 설정 제어가 필요해요

다음을 사용하세요:

- `Contexta`
- `contexta.config`

### 표준 모델을 직접 다루어야 해요

다음을 사용하세요:

- `contexta.contract`

### 조사 및 리포팅 기능이 필요해요

다음을 사용하세요:

- `Contexta`
- `contexta.interpretation`

### 복구 기능이 필요해요

다음을 사용하세요:

- `contexta.recovery`

### 쉘 환경을 선호해요

다음을 사용하세요:

- CLI

## 다음 읽을거리

다음 문서로 이어집니다:

- [핵심 개념](./core-concepts.md)
- [시작하기](./getting-started.md)
