# Contexta 문서

이곳은 `Contexta`의 공식 문서 허브입니다.

`Contexta`는 로컬 우선(local-first) ML 관측성(observability) 워크플로를 위한 표준 제품 인터페이스입니다. 이 문서 세트는 신규 사용자가 빠르게 시작하고, 고급 사용자가 안정적인 인터페이스 경계를 찾으며, 운영자가 공공 가이드와 내부 구현 노트를 혼동하지 않고 복구 작업을 수행할 수 있도록 구성되었습니다.

## 여기서 시작하세요

### Contexta가 처음이라면

다음 문서부터 시작하세요:

1. [README](../../README.md)
2. [사용자 가이드](./user-guide/index.md)

README는 가장 빠른 실행 경로를 제공합니다. 사용자 가이드는 제품 인터페이스가 어떻게 구성되어 있는지와 다음 단계로 무엇을 해야 하는지 설명합니다.

### 정확한 인터페이스 사양이 필요하다면

다음 문서부터 시작하세요:

1. [API 레퍼런스](./reference/api-reference.md)
2. [CLI 레퍼런스](./reference/cli-reference.md)
3. [HTTP 레퍼런스](./reference/http-reference.md)

API, CLI 및 HTTP 레퍼런스를 현재 바로 확인할 수 있습니다.

## 문서 구조

### `README.md`

README는 다음 용도로 사용하세요:

- 제품 개요
- 설치 방법
- 가장 짧은 검증된 퀵스타트
- 상위 수준의 인터페이스 맵

### 사용자 가이드 (User Guide)

사용자 가이드는 제품에 대한 작업 중심의 경로를 제공합니다:

- 개요
- [주요 기능](./user-guide/key-features.md)
- [도구 및 인터페이스](./user-guide/tools-and-surfaces.md)
- [핵심 개념](./user-guide/core-concepts.md)
- [시작하기](./user-guide/getting-started.md)
- [일반적인 워크플로](./user-guide/common-workflows.md)
- [고급 사용법](./user-guide/advanced.md)
- [테스트](./user-guide/testing.md)

진입점:

- [사용자 가이드 인덱스](./user-guide/index.md)

### 레퍼런스 (Reference)

레퍼런스 계층은 다음과 같은 안정적인 공공 계약(contracts)을 담고 있습니다:

- Python API
- CLI
- 내장 HTTP / UI

해당 페이지는 다음과 같습니다:

- [API 레퍼런스](./reference/api-reference.md)
- [CLI 레퍼런스](./reference/cli-reference.md)
- [HTTP 레퍼런스](./reference/http-reference.md)

### 운영 (Operations)

운영 계층은 다음 내용을 다룹니다:

- 백업
- 복구
- 재생(Replay)
- 보존 및 안전한 내보내기

- [운영 가이드](./operations.md)

### FAQ

FAQ는 온보딩 및 운영 과정에서 자주 발생하는 질문들에 대한 짧은 답변을 모아두었습니다.

- [FAQ](./faq.md)

### 기여 (Contribution)

기여 가이드는 다음 파일에 유지됩니다:

- [CONTRIBUTING.md](../../CONTRIBUTING.md)

이 가이드는 로컬 설정, 테스트, 공공/내부 경계 규칙 및 기여 워크플로를 다룹니다.

### 예제 (Examples)

예제는 별도의 일회성 샘플이 아니라 문서 인터페이스의 일부입니다.

현재 예제 그룹:

- [퀵스타트 예제](../../examples/quickstart/README.md)
- [복구 예제](../../examples/recovery/README.md)

## 읽기 경로

### 신규 사용자 경로

1. [README](../../README.md)
2. [사용자 가이드](./user-guide/index.md)
3. [시작하기](./user-guide/getting-started.md)
4. [일반적인 워크플로](./user-guide/common-workflows.md)

### 운영자 경로

1. [README 제품 인터페이스 섹션](../../README.md#product-surface)
2. [도구 및 인터페이스](./user-guide/tools-and-surfaces.md)
3. [고급 사용법](./user-guide/advanced.md)
4. [테스트 가이드](./user-guide/testing.md)
5. [운영 가이드](./operations.md)
6. [복구 예제](../../examples/recovery/README.md)

### 기여자 경로

1. [README](../../README.md)
2. [시작하기](./user-guide/getting-started.md)
3. [테스트 가이드](./user-guide/testing.md)
4. [CONTRIBUTING.md](../../CONTRIBUTING.md)

## 공공 문서에서 사용되는 명명 규칙

공공 문서에서는 표준 제품명을 우선적으로 사용합니다:

- 제품: `Contexta`
- Python 임포트: `contexta`
- CLI 대상: `contexta`
- 환경 변수 접두사: `CONTEXTA_*`
- 워크스페이스 루트: `.contexta/`

## 현재 상태

공공 문서 세트는 점진적으로 채워지고 있습니다. 현재 단계에서:

- README는 주요 퀵스타트 문서입니다.
- 이 허브는 공공 문서의 구조를 정의합니다.
- 사용자 가이드 인덱스는 안내된 읽기 경로를 정의합니다.
- 핵심 및 고급 사용자 가이드 페이지가 존재합니다.
- API 레퍼런스가 존재합니다.
- CLI 레퍼런스가 존재합니다.
- HTTP 레퍼런스가 존재합니다.
- 퀵스타트 예제 세트가 존재합니다.
- 복구 예제 세트가 존재합니다.
- 운영, FAQ 및 기여 페이지가 존재합니다.

이 페이지는 `docs/`의 나머지 부분이 채워진 후에도 최상위 탐색 지점으로 유지되어야 합니다.
