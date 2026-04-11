# Contexta 사용자 가이드 (User Guide)

사용자 가이드는 `Contexta`를 다루는 작업 중심의 경로를 제공합니다.

제품 인터페이스가 어떻게 구성되어 있는지, 어떤 도구부터 시작해야 하는지, 그리고 첫 번째 로컬 워크스페이스에서 더 고급 쿼리, 리포팅 및 복구 워크플로로 어떻게 이동하는지 이해하고 싶을 때 이 가이드를 사용하세요.

## 이 가이드의 대상

이 가이드는 다음 사용자를 위한 것입니다:

- `README.md`에서 시작하는 신규 사용자
- 안정적인 하위 네임스페이스를 직접 다루려는 고급 사용자
- 복구 기능이 어디에 속하는지 이해해야 하는 운영자

가장 빠른 실행 경로만을 원한다면 [README 퀵스타트](../../../README.md#quickstart)를 먼저 확인하세요.

## 권장 읽기 경로

### 신규 사용자

1. [README](../../../README.md)
2. [주요 기능](./key-features.md)
3. [도구 및 인터페이스](./tools-and-surfaces.md)
4. [핵심 개념](./core-concepts.md)
5. [시작하기](./getting-started.md)
6. [퀵스타트 예제](../../../examples/quickstart/README.md)
7. [일반적인 워크플로](./common-workflows.md)

### 고급 Python 사용자

1. [README 제품 인터페이스 섹션](../../../README.md#product-surface)
2. [도구 및 인터페이스](./tools-and-surfaces.md)
3. [고급 사용법](./advanced.md)
4. [API 레퍼런스](../reference/api-reference.md)

### 운영자

1. [README 제품 인터페이스 섹션](../../../README.md#product-surface)
2. [고급 사용법](./advanced.md)
3. [테스트 가이드](./testing.md)
4. [복구 예제](../../../examples/recovery/README.md)
5. [운영 가이드](../operations.md)

## 가이드 로드맵

사용자 가이드는 다음과 같은 섹션으로 구성되어 있습니다.

| 섹션 | 용도 | 상태 |
| --- | --- | --- |
| [`key-features.md`](./key-features.md) | `Contexta`가 단일 제품으로서 제공하는 가치 설명 | 사용 가능 |
| [`tools-and-surfaces.md`](./tools-and-surfaces.md) | 공용 인터페이스 맵과 각 도구의 사용 시점 안내 | 사용 가능 |
| [`core-concepts.md`](./core-concepts.md) | 실행, 스테이지, 레코드, 아티팩트, 리니지, 리포트 및 완전성 정의 | 사용 가능 |
| [`getting-started.md`](./getting-started.md) | README 퀵스타트를 더 상세한 온보딩 튜토리얼로 확장 | 사용 가능 |
| [`common-workflows.md`](./common-workflows.md) | 가장 빈번한 일상적 사용 흐름 안내 | 사용 가능 |
| [`advanced.md`](./advanced.md) | 직접적인 설정, 스토어, 해석 및 복구 사용법 안내 | 사용 가능 |
| [`testing.md`](./testing.md) | 테스트 철학과 예제 및 워크플로 검증 방법 설명 | 사용 가능 |
| [`batch-sample-deployment.md`](./batch-sample-deployment.md) | 배치, 샘플, 배포 추적 — 로깅, 쿼리, 진단 | 사용 가능 |
| [`adapters.md`](./adapters.md) | 선택적 싱크 어댑터 — StdoutSink, OTelSink, MLflowSink | 사용 가능 |
| [`notebook.md`](./notebook.md) | 노트북 인터페이스 — `ctx.notebook`, 인라인 표시, DataFrame 변환 | 사용 가능 |
| [`case-studies.md`](./case-studies.md) | 12가지 실제 시나리오 — 왜 Contexta인지, Without vs With, 케이스별 주요 API | 사용 가능 |

## 가이드에서 다루는 내용

### 주요 기능 (Key Features)

이 섹션에서는 사용자에게 보이는 결과 측면에서 제품을 설명합니다:

- 통합된 제품 인터페이스
- 로컬 우선(local-first) 워크스페이스
- 표준화된 저장소 (Canonical storage)
- 쿼리, 비교, 진단, 리니지 및 리포트
- 복구 지원

### 도구 및 인터페이스 (Tools And Surfaces)

이 섹션에서는 제품이 다음과 같이 어떻게 나뉘는지 보여줍니다:

- `Contexta`
- `contexta.config`
- `contexta.contract`
- `contexta.capture`
- `contexta.store.metadata`
- `contexta.store.records`
- `contexta.store.artifacts`
- `contexta.interpretation`
- `contexta.recovery`
- CLI
- 내장 HTTP / UI

각 도구나 인터페이스는 다음 기준에 따라 설명됩니다:

- 정의
- 사용 시점
- 권장되는 시작 지점 여부
- `Stable`(안정) 또는 `Advanced`(고급) 여부

### 시작하기 (Getting Started)

시작하기 경로는 README를 더 완전한 온보딩 흐름으로 확장합니다:

1. 설치
2. 워크스페이스 생성
3. 최소한의 표준 데이터 작성
4. 실행 결과 쿼리
5. 리포트 빌드
6. 워크스페이스에 포함된 내용 이해하기

### 일반적인 워크플로 (Common Workflows)

이 섹션은 모듈 구조보다는 일반적인 사용자 목표에 초점을 맞춥니다:

- 실행 생성 및 조사
- 두 실행 비교
- 리포트 빌드
- 진단 결과 조사
- 리니지 추적

### 고급 사용법 (Advanced Usage)

이 섹션에서는 필요할 때 퍼사드(facade)를 넘어가는 방법을 설명합니다:

- 명시적인 설정 제어
- 직접적인 저장소(store) 사용
- 해석(interpretation) 수준의 서비스
- 복구 워크플로

### 테스트 (Testing)

이 섹션에서는 제품의 검증 방식에 대해 설명합니다:

- 테스트 스위트의 커버리지 범위
- 예제 검증 방식
- Python, CLI 및 HTTP 간의 시맨틱 동등성(semantic parity)의 의미

## 공용 명명 규칙

사용자 가이드에서는 표준 제품명을 우선적으로 사용합니다:

- 제품: `Contexta`
- Python 임포트: `contexta`
- CLI 대상: `contexta`
- 환경 변수 접두사: `CONTEXTA_*`
- 워크스페이스 루트: `.contexta/`

## 지금 읽어야 할 내용

핵심 및 고급 사용자 가이드 페이지들이 현재 사용 가능합니다. 다음 진입점들을 확인하세요:

- [README](../../../README.md)
- [README 퀵스타트](../../../README.md#quickstart)
- [README 제품 인터페이스 섹션](../../../README.md#product-surface)
- [주요 기능](./key-features.md)
- [도구 및 인터페이스](./tools-and-surfaces.md)
- [핵심 개념](./core-concepts.md)
- [시작하기](./getting-started.md)
- [퀵스타트 예제](../../../examples/quickstart/README.md)
- [일반적인 워크플로](./common-workflows.md)
- [고급 사용법](./advanced.md)
- [테스트 가이드](./testing.md)
- [복구 예제](../../../examples/recovery/README.md)
- [배치, 샘플 & 배포](./batch-sample-deployment.md)
- [어댑터](./adapters.md)
- [노트북 인터페이스](./notebook.md)
- [배치 & 샘플 예제](../../../examples/batch_sample/README.md)
- [어댑터 예제](../../../examples/adapters/README.md)
- [케이스 스터디](./case-studies.md)
- [케이스 스터디 예제](../../../examples/case_studies/README.md)
- [API 레퍼런스](../reference/api-reference.md)
- [CLI 레퍼런스](../reference/cli-reference.md)
- [HTTP 레퍼런스](../reference/http-reference.md)
- [운영 가이드](../operations.md)
- [FAQ](../faq.md)
- [CONTRIBUTING.md](../../../CONTRIBUTING.md)

이 페이지는 레퍼런스, 운영, FAQ 및 기여 문서가 추가됨에 따라 전체 사용자 가이드를 위한 안정적인 진입점으로 유지될 것입니다.
