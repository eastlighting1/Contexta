# Contexta FAQ

## `contexta`를 임포트해야 하나요?

네. `contexta`는 이 저장소에서 지원되는 공식 Python 임포트 루트입니다.

## 이 저장소에서는 어떤 명칭을 사용해야 하나요?

제품 이름은 `Contexta`, Python 패키지 및 CLI는 `contexta`, 환경 변수는 `CONTEXTA_*`, 표준 워크스페이스 루트는 `.contexta/`를 사용하세요.

## 표준 워크스페이스 루트(Canonical workspace root)는 무엇인가요?

표준 워크스페이스 루트는 `.contexta/`입니다.

## Contexta는 로컬 우선(local-first) 방식인가요?

네. 문서화된 제품 방향은 메타데이터, 레코드, 아티팩트, 리포트 및 복구 상태를 소유하는 표준 워크스페이스를 기반으로 한 로컬 우선 관측성(local-first observability)입니다.

## 가장 빠르게 시작할 수 있는 방법은 무엇인가요?

검증된 퀵스타트 예제를 사용하세요:

- [퀵스타트 예제](../../examples/quickstart/README.md)

이 경로는 회귀 테스트를 통해 검증되었으며, 현재 워크스페이스 생성, 표준 쓰기, 쿼리 및 리포트 생성을 입증합니다.

## 런타임 캡처(runtime capture) API가 이미 존재하나요?

네. 런타임 스코프 API는 현재 활성화되어 있으며 문서화되어 있습니다. 다만 쿼리/리포트를 위한 가장 안정적인 온보딩 경로는 캡처 전용 튜토리얼보다는 검증된 퀵스타트 예제입니다.

## HTTP/UI 화면이 호스팅되는 서비스인가요?

아니요. 현재 HTTP/UI 화면은 동일한 표준 제품 시맨틱을 기반으로 한 내장형 로컬 전용 전달 어댑터입니다.

참고:

- [HTTP 레퍼런스](./reference/http-reference.md)

## `contexta.recovery`는 언제 사용해야 하나요?

`contexta.recovery`는 백업, 복구 계획 및 재생(replay)과 같은 운영자 중심의 워크플로에 사용하세요.

참고:

- [운영 가이드](./operations.md)
- [복구 예제](../../examples/recovery/README.md)

## `contexta.api`나 `contexta.runtime` 같은 내부 네임스페이스를 의존해도 되나요?

아니요. 공공 문서는 이러한 내부 네임스페이스를 임포트 지점으로 사용하는 것을 의도적으로 피하고 있습니다. `contexta`, `contexta.config`, `contexta.contract`, `contexta.capture`, `contexta.interpretation`, `contexta.recovery` 및 3개의 스토어(store) 패키지와 같이 문서화된 공용 인터페이스를 사용하세요.

## 예제가 계속 작동하는지 어떻게 알 수 있나요?

테스트 가이드에 있는 가장 작은 실행 단위의 테스트 스위트를 사용하세요. 예:

- 퀵스타트 예제: `uv run pytest tests/e2e/test_quickstart_examples.py -q`
- 복구 예제: `uv run pytest tests/e2e/test_recovery_examples.py -q`

참고:

- [테스트 가이드](./user-guide/testing.md)

## 왜 로컬 스크립트에서 여전히 `PYTHONPATH=src`가 필요한가요?

소스 트리 스크립트의 편의성 기능이 아직 프로토타입 단계이기 때문입니다. 저장소 테스트 실행은 프로젝트 설정을 통해 `src/`를 가져오지만, 개별 로컬 예제 실행은 여전히 `PYTHONPATH=src`를 사용하는 것이 현재로서 가장 안전한 경로입니다.

## 다음 단계로 무엇을 확인해야 하나요?

- 제품 온보딩: [사용자 가이드](./user-guide/index.md)
- 정확한 인터페이스 사양: [API 레퍼런스](./reference/api-reference.md), [CLI 레퍼런스](./reference/cli-reference.md), [HTTP 레퍼런스](./reference/http-reference.md)
- 기여하기: [CONTRIBUTING.md](../../CONTRIBUTING.md)
