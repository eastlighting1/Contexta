# Contexta 시작하기

이 가이드는 README의 퀵스타트 내용을 더 상세한 온보딩 경로로 확장한 것입니다.

현재 프로토타입 단계에서 가장 신뢰할 수 있는 엔드 투 엔드(end-to-end) 경로는 다음과 같습니다:

1. 프로젝트 설치
2. 표준 워크스페이스(canonical workspace) 생성
3. 검증된 퀵스타트 예제 실행
4. 퍼사드(facade)를 통해 해당 워크스페이스 쿼리
5. 리포트 빌드

이 방식은 튜토리얼을 현재 검증된 프로토타입 동작과 일치하게 유지해 줍니다.

## 시작하기 전에

필수 사양:

- Python `>=3.14`
- 이 저장소의 로컬 체크아웃
- `.contexta/` 폴더를 생성할 수 있는 로컬 파일 시스템

## 1단계: 프로젝트 설치

현재 프로토타입 체크아웃 상태에서 신뢰할 수 있는 로컬 개발 경로는 다음과 같습니다:

```powershell
uv sync --dev
$env:PYTHONPATH = "src"
```

이렇게 하면 패키징 정렬 작업이 진행되는 동안 로컬 가이드 예제에서 소스 트리를 임포트할 수 있습니다.

환경 변수를 영구적으로 설정하지 않고 세션 로컬 방식으로 실행하고 싶다면 다음을 사용하세요:

```powershell
$env:PYTHONPATH = "src"
uv run python your_script.py
```

만약 `pip`를 사용한 편집 가능한 설치(editable installation)를 선호한다면, 이를 가장 보수적인 프로토타입 경로라기보다는 미래 지향적인 패키징 작업으로 취급하세요:

```powershell
python -m pip install -e .
```

패키징 및 콘솔 스크립트 정렬 작업이 완료되면, 이 가이드는 다시 더 간단한 설치 과정으로 축소될 수 있습니다.

## 2단계: 목표 이해하기

이 튜토리얼은 모든 기능을 한꺼번에 보여주려는 것이 아닙니다.

이 튜토리얼의 목표는 다음 네 가지를 증명하는 것입니다:

- 표준 임포트 경로가 작동함
- `.contexta/` 워크스페이스가 생성될 수 있음
- 표준 데이터를 쓸 수 있음
- 통합된 퍼사드가 해당 데이터를 읽고 리포트를 빌드할 수 있음

## 3단계: 검증된 퀵스타트 예제 실행

저장소 루트에서 예제를 실행하세요:

```powershell
$env:PYTHONPATH = "src"
uv run python examples/quickstart/verified_quickstart.py
```

실제 예제 소스는 [examples/quickstart/verified_quickstart.py](../../../examples/quickstart/verified_quickstart.py)에 있습니다.

이 스크립트는 다음을 수행합니다:

- 임시 `.contexta/` 워크스페이스 생성
- 하나의 프로젝트, 실행, 스테이지 및 메트릭 레코드 작성
- 퍼사드를 통해 실행 결과를 다시 조회
- 워크스페이스의 `reports/` 디렉터리에 마크다운 스냅샷 리포트 저장

## 4단계: 실행 결과 분석

스크립트는 다음 과정을 수행했습니다:

1. 임시 루트와 `.contexta/` 워크스페이스 경로 생성
2. `UnifiedConfig`를 통해 `Contexta` 퍼사드를 해당 워크스페이스에 바인딩
3. 최소한의 표준 메타데이터와 하나의 메트릭 레코드 작성
5. `get_run_snapshot(...)`을 통해 실행 결과를 다시 조회
6. `build_snapshot_report(...)`를 통해 리포트 빌드

모든 캡처 단축키가 이미 세련된 온보딩 흐름으로 완전히 패키징된 것처럼 꾸미지 않고, 실제 표준 쓰기 및 읽기 경로를 연습하기 때문에 이 튜토리얼이 가장 솔직하고 짧은 프로토타입 튜토리얼입니다.

## 5단계: 다음으로 확인할 사항

스크립트를 실행한 후 다음 아이디어들을 살펴보세요:

- 워크스페이스 경로가 존재하는지 확인
- 실행 결과가 표준 실행 참조(Canonical run ref)를 통해 쿼리 가능한지 확인
- 리포트 객체가 제목과 섹션들을 가지고 있는지 확인
- 제품 인터페이스가 동일한 `Contexta` 퍼사드 아래에 유지되는지 확인

## 런타임 캡처(Runtime Capture) 미리보기

런타임 캡처 인터페이스는 이미 사용 가능하며, 표준 워크스페이스의 개념을 이해했다면 시도해 볼 가치가 있습니다:

```powershell
$env:PYTHONPATH = "src"
uv run python examples/quickstart/runtime_capture_preview.py
```

미리보기 소스는 [examples/quickstart/runtime_capture_preview.py](../../../examples/quickstart/runtime_capture_preview.py)에 있습니다.

현재 프로토타입 단계에서는 이를 미래 지향적인 런타임 진입 경로로 취급하고, 위에서 설명한 검증된 퀵스타트(verified quickstart)를 쿼리/리포트 온보딩을 위한 보수적인 경로로 유지하세요.

## 자주 묻는 질문

### 왜 이 튜토리얼은 '검증된 퀵스타트(Verified Quickstart)' 스크립트를 사용하나요?

워크스페이스 생성부터 리포트 생성까지 이어지는 신뢰할 수 있고 현재 검증된 경로를 제공하기 위해서입니다.

예제 자체는 내부적으로 여전히 표준 모델 쓰기를 사용하며, 이는 현재 프로토타입이 온보딩 경로에서 이미 입증한 것보다 더 많은 런타임 캡처 통합을 약속하는 것을 피하기 위함입니다.

이 예제는 내부 모듈 경로 대신 `contexta.config` 및 `contexta.contract`와 같은 공용 재내보내기 인터페이스를 사용합니다.

### 왜 `run:guide-proj.demo-run`과 같은 전체 참조(Full Refs)를 사용하나요?

`Contexta`는 안정적인 계약의 일부로 표준 식별자를 사용하기 때문입니다. 명시적인 참조를 사용하면 읽기 경로가 더 명확해지고 튜토리얼이 계약 계층과 일관되게 유지됩니다.

### `UnifiedConfig`를 반드시 사용해야 하나요?

항상 그런 것은 아닙니다. 퍼사드는 다른 설정 해결 경로를 통해서도 열릴 수 있습니다. 이 가이드에서 `UnifiedConfig`를 사용하는 이유는 온보딩 시 명시적이고 예측 가능하기 때문입니다.

## 다음 단계

이 튜토리얼 이후에는 다음 내용을 확인하세요:

- [주요 기능](./key-features.md)
- [도구 및 인터페이스](./tools-and-surfaces.md)
- [핵심 개념](./core-concepts.md)
