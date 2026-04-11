# Contexta HTTP 레퍼런스

이 페이지는 `Contexta`의 현재 내장된 HTTP 전달 인터페이스(surface)를 문서화합니다.

주요 경계는 다음과 같습니다:

- 내장된 HTTP 인터페이스는 동일한 표준 제품 시맨틱을 기반으로 하는 로컬 전용 전달 어댑터입니다.
- 별도의 호스팅된 서비스가 아닙니다.
- 주요 공용 Python 임포트 대상이 아닙니다.

대부분의 사용자는 CLI 런처를 통해 HTTP 인터페이스에 접근해야 합니다:

```bash
contexta serve http --host 127.0.0.1 --port 8080
```

현재 프로토타입 단계에서, 동일한 내장 서버가 저장소의 표준 `contexta` CLI를 통해 노출됩니다.

## 이 레퍼런스의 범위

이 페이지는 다음 사항을 문서화합니다:

- 내장 서버에 존재하는 현재의 GET 엔드포인트
- 기대되는 콘텐츠 타입 및 쿼리 파라미터
- 현재의 에러 엔벨로프(envelope) 동작
- JSON API 경로와 HTML UI 경로 간의 구분

`contexta.surfaces.http`를 공용 Python 임포트 홈으로 취급하지 않습니다. 해당 모듈은 저장소에 존재하지만, 여기에서의 공용 계약은 HTTP 인터페이스 그 자체입니다.

## 전송 모델 (Transport Model)

현재 내장된 HTTP 인터페이스는 다음과 같습니다:

- 로컬 전용
- HTTP 기반의 요청/응답
- 현재 구현에서는 GET 전용
- JSON API 경로와 서버 렌더링 방식의 HTML UI 경로로 구분

성공적인 응답은 다음을 사용합니다:

- JSON 경로의 경우 `application/json; charset=utf-8`
- UI 경로의 경우 `text/html; charset=utf-8`

## 서버 시작하기

문서화된 진입 경로는 CLI입니다:

```bash
contexta serve http [--host HOST] [--port PORT]
```

현재 기본값:

- host: `127.0.0.1`
- port: `8080`

HTTP 서버는 하나의 워크스페이스에 바인딩된 활성 `Contexta` 인스턴스를 중심으로 생성됩니다.

## 에러 모델 (Error Model)

JSON 에러 응답은 일관된 엔벨로프를 사용합니다:

```json
{
  "error": {
    "code": "http_not_found",
    "message": "Unknown endpoint: /does/not/exist",
    "details": null
  }
}
```

현재 에러 제품군에는 다음이 포함됩니다:

- `http_not_found`
- `http_bad_request`
- `http_internal_error`
- 제품 예외가 직접 발생했을 때의 `contexta` 파생 에러 코드들

현재의 중요한 동작:

- 알 수 없는 API 경로는 JSON `404`를 반환합니다.
- 많은 검증 에러는 JSON `400`을 반환합니다.
- 예기치 않은 내부 실패는 JSON `500`을 반환합니다.
- 여러 UI 경로 실패 또한 현재 HTML 에러 페이지 대신 동일한 JSON 에러 엔벨로프로 대체(fallback)됩니다.

마지막 지점은 UI 경로를 중심으로 브라우저 측 도구를 구축하는 경우 알아두어야 할 프로토타입의 제한 사항입니다.

## ID 스타일

현재의 쿼리 계층은 `my-proj.run-01`과 같은 짧은 실행 식별자를 허용하는 경우가 많으며, 저장소 테스트에서도 이 스타일을 많이 사용합니다.

클라이언트 코드를 제어할 수 있는 경우에는 가능한 한 표준 식별자(canonical identifiers)를 우선적으로 사용하세요. 예시:

- 실행 참조 스타일: `run:my-proj.run-01`
- 아티팩트 참조 스타일: `artifact:my-proj.run-01.model`

내장 서버는 경로 값을 기본 쿼리 계층으로 전달하므로, 허용되는 식별자 형태는 장기적인 표준 문서 스타일보다 넓을 수 있습니다.

## JSON API 경로 (JSON API Routes)

### `GET /projects`

프로젝트 이름 목록을 조회합니다.

응답 형태:

```json
{
  "projects": ["my-proj"]
}
```

회귀 테스트 통과 여부:

- 예

### `GET /runs`

실행 목록을 조회합니다.

쿼리 파라미터:

- `project`
- `status`
- `after`
- `before`
- `limit`
- `offset`
- `sort`
- `desc`

응답 형태:

```json
{
  "runs": [...]
}
```

현재 참고 사항:

- `sort`는 실행 목록 쿼리 빌더로 전달됩니다.
- `desc`가 생략되면, 현재 HTTP 빌더는 `started_at`을 기준으로 내림차순 정렬을 기본으로 합니다.

회귀 테스트 통과 여부:

- 예

### `GET /runs/{run_id}`

하나의 실행에 대한 실행 요약 페이로드를 반환합니다.

응답 구성 요소:

- `run_id`
- `project_name`
- `name`
- `status`
- `started_at`
- `ended_at`
- `stages`
- `artifact_count`
- `record_count`
- `completeness_notes`
- `provenance`

회귀 테스트 통과 여부:

- 예

### `GET /runs/{run_id}/diagnostics`

하나의 실행에 대한 진단 결과를 반환합니다.

응답:

- JSON으로 직렬화된 진단 페이로드

회귀 테스트 통과 여부:

- 예

### `GET /runs/{run_id}/lineage`

하나의 실행 파생 대상에 대한 리니지 순회 결과를 반환합니다.

쿼리 파라미터:

- `direction`
- `depth`

허용되는 방향:

- `upstream`
- `downstream`
- `inbound`
- `outbound`
- `both`

현재 동작:

- `upstream`은 `inbound`로 매핑됩니다.
- `downstream`은 `outbound`로 매핑됩니다.
- 잘못된 방향은 `400`을 반환합니다.

회귀 테스트 통과 여부:

- 예

### `GET /runs/{run_id}/report`

스냅샷 리포트 문서를 JSON으로 반환합니다.

회귀 테스트 통과 여부:

- 예

### `GET /runs/{run_id}/anomalies`

하나의 실행에 대한 이상 탐지 결과를 반환합니다.

쿼리 파라미터:

- `metric`
- `project`
- `stage`

응답 형태:

```json
{
  "anomalies": [...]
}
```

회귀 테스트 통과 여부:

- 현재 HTTP 경로 테스트에서 명시적으로 다루지 않음

### `GET /runs/{run_id}/reproducibility`

프로버넌스(provenance) 데이터로부터 파생된 재현성 중심의 페이로드를 반환합니다.

응답 구성 요소:

- `run_id`
- `environment_ref`
- `missing_fields`
- `reproducibility_score`
- `is_fully_reproducible`
- `completeness_notes`

회귀 테스트 통과 여부:

- 현재 HTTP 경로 테스트에서 명시적으로 다루지 않음

### `GET /runs/{run_id}/environment-diff/{other_run_id}`

두 실행 간의 환경 차이(diff) 페이로드를 반환합니다.

응답 구성 요소:

- `left_run_id`
- `right_run_id`
- `changed_fields`
- `missing_fields`
- `has_differences`
- 패키지 및 환경 변수 변경 블록

회귀 테스트 통과 여부:

- 현재 HTTP 경로 테스트에서 명시적으로 다루지 않음

### `GET /compare`

두 실행을 비교합니다.

필수 쿼리 파라미터:

- `left`
- `right`

필수 파라미터가 누락되면 `400`을 반환합니다.

회귀 테스트 통과 여부:

- 예

### `GET /compare/multi`

여러 실행을 비교합니다.

필수 쿼리 파라미터:

- `run_ids`

현재 형식:

- 쉼표로 구분된 실행 ID들

최소 두 개의 실행 ID가 필요합니다.

회귀 테스트 통과 여부:

- 예

### `GET /metrics/trend`

메트릭 추세를 반환합니다.

필수 쿼리 파라미터:

- `metric`

선택적 쿼리 파라미터:

- `project`
- `stage`
- `status`
- `after`
- `before`
- `limit`
- `offset`
- `sort`
- `desc`

회귀 테스트 통과 여부:

- 예

### `GET /metrics/aggregate`

하나의 메트릭에 대한 집계 결과를 반환합니다.

필수 쿼리 파라미터:

- `metric`

선택적 쿼리 파라미터:

- `project`
- `stage`
- `status`
- `after`
- `before`
- `limit`
- `offset`
- `sort`
- `desc`

회귀 테스트 통과 여부:

- 예

### `GET /alerts/evaluate/{run_id}`

하나의 실행에 대해 하나의 알림 규칙을 평가합니다.

필수 쿼리 파라미터:

- `metric`
- `operator`
- `threshold`

선택적 쿼리 파라미터:

- `stage`
- `severity`

응답 형태:

```json
{
  "results": [...]
}
```

회귀 테스트 통과 여부:

- 현재 HTTP 경로 테스트에서 명시적으로 다루지 않음

### `GET /search/runs`

실행을 검색합니다.

필수 쿼리 파라미터:

- `q`

선택적 쿼리 파라미터:

- `project`
- `status`
- `limit`

회귀 테스트 통과 여부:

- 예

### `GET /search/artifacts`

아티팩트를 검색합니다.

필수 쿼리 파라미터:

- `q`

선택적 쿼리 파라미터:

- `kind`

응답 형태:

```json
{
  "artifacts": [...]
}
```

회귀 테스트 통과 여부:

- 구현되어 있으나, 현재 HTTP 경로 테스트에서 명시적으로 다루지 않음

## HTML UI 경로 (HTML UI Routes)

성공적인 UI 경로는 서버 렌더링 방식의 HTML을 반환합니다.

현재 UI 인터페이스는 읽기 중심이며 로컬 전용입니다.

### `GET /ui`

실행 목록 페이지를 렌더링합니다.

현재 동작:

- `/ui`는 실행 목록 뷰를 직접 렌더링합니다.
- HTTP 리다이렉트를 발생시키지 않습니다.

회귀 테스트 통과 여부:

- 예

### `GET /ui/runs`

실행 목록 페이지를 렌더링합니다.

쿼리 파라미터:

- `project`
- `status`
- `after`
- `before`
- `limit`
- `offset`
- `sort`
- `desc`

관찰된 페이지 구조는 다음을 포함합니다:

- `run-list-summary`
- `runs-table`

회귀 테스트 통과 여부:

- 예

### `GET /ui/runs/{run_id}`

실행 상세 정보를 렌더링합니다.

관찰된 페이지 구조는 다음을 포함합니다:

- `run-summary`
- `stage-table`
- `artifact-table`
- `record-preview`
- `provenance-summary`
- `completeness-notes`

회귀 테스트 통과 여부:

- 예

### `GET /ui/runs/{run_id}/diagnostics`

진단 페이지를 렌더링합니다.

관찰된 페이지 구조는 다음을 포함합니다:

- `diagnostics-summary`
- `diagnostics-issues`
- `diagnostics-notes`

회귀 테스트 통과 여부:

- 예

### `GET /ui/runs/{run_id}/anomalies`

이상 탐지 페이지를 렌더링합니다.

관찰된 페이지 구조는 다음을 포함합니다:

- `anomalies-table`

회귀 테스트 통과 여부:

- 구현되어 있으나, 현재 HTTP UI 테스트에서 명시적으로 다루지 않함

### `GET /ui/compare`

실행 비교를 렌더링합니다.

필수 쿼리 파라미터:

- `left`
- `right`

관찰된 페이지 구조는 다음을 포함합니다:

- `comparison-run-header`
- `comparison-summary`
- `comparison-stage-table`
- `comparison-artifact-table`
- `comparison-provenance`
- `comparison-notes`

회귀 테스트 통과 여부:

- 예

### `GET /ui/compare/multi`

다중 실행 비교를 렌더링합니다.

필수 쿼리 파라미터:

- `run_ids`

현재 형식:

- 쉼표로 구분된 실행 ID들

관찰된 페이지 구조는 다음을 포함합니다:

- `comparison-summary`
- `comparison-stage-table`

회귀 테스트 통과 여부:

- 구현되어 있으나, 현재 HTTP UI 테스트에서 명시적으로 다루지 않음

### `GET /ui/metrics/trend`

메트릭 추세 페이지를 렌더링합니다.

필수 쿼리 파라미터:

- `metric`

선택적 쿼리 파라미터:

- `project`
- `stage`
- `status`
- `after`
- `before`
- `limit`
- `offset`
- `sort`
- `desc`

관찰된 페이지 구조는 다음을 포함합니다:

- `trend-summary`
- `trend-chart`
- `trend-run-table`
- `trend-notes`

회귀 테스트 통과 여부:

- 예

### `GET /ui/metrics/aggregate`

집계 페이지를 렌더링합니다.

필수 쿼리 파라미터:

- `metric`

관찰된 페이지 구조는 다음을 포함합니다:

- `trend-summary`
- `trend-notes`

회귀 테스트 통과 여부:

- 구현되어 있으나, 현재 HTTP UI 테스트에서 명시적으로 다루지 않음

## 회귀 테스트 범위 요약 (Regression Coverage Summary)

가장 강력한 현재의 경로 수준 증거는 다음에서 나옵니다:

- `tests/surfaces/test_http_json.py`
- `tests/surfaces/test_http_ui.py`

해당 스위트는 다음을 명시적으로 다룹니다:

- `/projects`
- `/runs`
- `/runs/{run_id}`
- `/runs/{run_id}/diagnostics`
- `/runs/{run_id}/report`
- `/runs/{run_id}/lineage`
- `/compare`
- `/compare/multi`
- `/metrics/trend`
- `/metrics/aggregate`
- `/search/runs`
- `/ui`
- `/ui/runs`
- `/ui/runs/{run_id}`
- `/ui/runs/{run_id}/diagnostics`
- `/ui/compare`
- `/ui/metrics/trend`
- 알 수 없는 경로에 대한 에러 처리

추가적인 경로들이 서버 구현에 존재하며 위에 문서화되어 있지만, 현재는 전용 경로 테스트보다는 구현 코드 읽기에 더 의존하고 있습니다.

## 현재 프로토타입 참고 사항

현재 프로토타입 단계에서:

- HTTP 인터페이스는 내장되어 있으며 로컬 전용입니다.
- 공식 시작 경로는 별도의 서버 제품이 아닌 여전히 CLI입니다.
- 성공적인 UI 경로는 HTML을 반환하지만, 여러 UI 에러 케이스는 여전히 JSON 에러 엔벨로프로 대체(fallback)됩니다.
- 경로 세트는 현재의 명시적인 경로 테스트 메트릭스보다 더 풍부합니다.

이는 이 페이지가 구현된 내용과 이미 강력한 회귀 테스트로 보호되는 내용을 명확히 구분하면서도, 현재 내장된 전달 인터페이스에 대한 정직한 계약으로 읽혀야 함을 의미합니다.
