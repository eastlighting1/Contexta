# 어댑터 (Adapters)

이 페이지에서는 Contexta의 선택적 싱크(sink) 어댑터를 설명합니다 — 외부
옵저버빌리티 및 실험 추적 시스템과의 통합입니다.

## 아키텍처

Contexta는 엄격한 경계를 통해 코어 런타임과 벤더 통합을 분리합니다.
코어 패키지(`contract`, `runtime`, `capture`, `store`, `interpretation`)는
외부 벤더 라이브러리에 대한 의존성이 없습니다.

어댑터는 `contexta.adapters.*`에 위치합니다. `Sink` 프로토콜을 구현하며,
생성 시 `CaptureDispatcher`에 삽입됩니다:

```python
ctx = Contexta(sinks=[MySink(), AnotherSink()])
```

레코드가 캡처되면, 디스패처가 등록된 모든 싱크로 팬아웃(fan-out)합니다.

## 의존성 정책

벤더 게이팅 어댑터는 첫 번째 `capture()` 호출 시가 아닌, **생성 시**
필요한 패키지가 없으면 `DependencyError`를 발생시킵니다. 이를 통해
잘못 구성된 싱크가 데이터가 흐르기 전에 명확하게 실패합니다.

```python
from contexta.common.errors import DependencyError

try:
    sink = OTelSink()
except DependencyError as e:
    print(e.code)  # "otel_api_not_ready"
```

선택적 extras를 설치하여 활성화합니다:

```bash
pip install 'contexta[otel]'
pip install 'contexta[mlflow]'
```

---

## StdoutSink

**Extra:** 없음 — stdlib만 사용.

모든 캡처된 레코드를 JSON 라인으로 출력합니다. 로컬 디버깅 및 CI 로그
검사에 유용합니다.

```python
from contexta.capture.sinks import StdoutSink

sink = StdoutSink(
    name="console",     # 디스패처 내의 싱크 이름
    stream="stdout",    # "stdout" 또는 "stderr"
    indent=None,        # None = 압축, 2 = 들여쓰기
)
ctx = Contexta(sinks=[sink])
```

`StdoutSink`는 모든 `PayloadFamily` 값을 지원합니다 — 수신하는 모든 것을
출력합니다.

---

## OTelSink

**Extra:** `pip install 'contexta[otel]'`

Contexta 캡처 페이로드를 OpenTelemetry API로 내보냅니다.

```python
from contexta.adapters.otel import OTelSink

sink = OTelSink(
    service_name="my-ml-service",  # OTel tracer/meter 스코프 이름
    tracer_provider=None,          # None → 전역 OTel 프로바이더 사용
    meter_provider=None,           # None → 전역 OTel 프로바이더 사용
    name="otel",
)
ctx = Contexta(sinks=[sink])
```

### 내보내기 대상

| Contexta 레코드 | OTel 개념 |
|---|---|
| `TraceSpanRecord` | Span (`tracer.start_span` 사용) |
| `MetricRecord` | Histogram 관찰값 |
| `StructuredEventRecord` | 현재 활성 스팬의 이벤트 |
| `DegradedRecord` | 현재 활성 스팬의 이벤트 (`contexta.degraded`) |

### span_kind 매핑

| Contexta `span_kind` | OTel `SpanKind` |
|---|---|
| `operation`, `internal` | `INTERNAL` |
| `io`, `network` | `CLIENT` |
| `process` | `PRODUCER` |

### 프로바이더 설정

OTelSink는 익스포터, 샘플러, 리소스를 설정하지 않습니다 — 이는 호출자의
책임입니다. `tracer_provider=None`이면 전역으로 등록된 프로바이더가 사용됩니다.

OTelSink는 `PayloadFamily.RECORD`만 지원합니다. 컨텍스트 페이로드는
무시됩니다.

---

## MLflowSink

**Extra:** `pip install 'contexta[mlflow]'`

Contexta 캡처 페이로드를 MLflow Tracking API로 내보냅니다.

```python
from contexta.adapters.mlflow import MLflowSink

sink = MLflowSink(
    run_id=None,    # None → 활성 mlflow.start_run() 컨텍스트에 로깅
    name="mlflow",
)
ctx = Contexta(sinks=[sink])
```

### 내보내기 대상

| Contexta 레코드 | MLflow 개념 |
|---|---|
| `MetricRecord` | `mlflow.log_metric` |
| `StructuredEventRecord` | `mlflow.set_tag` (`contexta.event.<key>`) |
| `DegradedRecord` | `mlflow.set_tag` (`contexta.degraded.<key>`) |

`TraceSpanRecord`는 무시됩니다 (MLflow 트레이싱 API는 버전 제한이 있으며,
향후 확장을 위해 예약됨).

### 활성 런 vs 명시적 run_id

`run_id=None`이면 현재 활성 MLflow 런을 대상으로 합니다:

```python
with mlflow.start_run():
    sink = MLflowSink()
    ctx = Contexta(sinks=[sink])
    # ... 모든 캡처가 활성 런으로 전달
```

`run_id`를 지정하면 명시적으로 포함됩니다:

```python
sink = MLflowSink(run_id="abc123def456")
```

MLflowSink는 `PayloadFamily.RECORD`만 지원합니다. 컨텍스트 페이로드는
무시됩니다.

---

## 스레드 안전성

세 어댑터 모두 기본적으로 **스레드 안전하지 않습니다**. 스레드당 별도의
싱크 인스턴스를 사용하거나 외부에서 접근을 보호하세요.

---

## 예제

각 싱크의 실행 가능한 데모는
[`examples/adapters/`](../../../examples/adapters/)를 참고하세요.
