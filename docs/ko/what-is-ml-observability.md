# ML Observability란 무엇인가?

`Contexta`는 ML Observability를 기존의 애플리케이션 Observability보다 더 넓은 분야로 봅니다.
이것은 단순히 실행 중인 시스템에서 telemetry를 수집하는 일만을 뜻하지 않습니다.
오히려 사후에 ML 실행(run)의 수명 주기를 이해하고, 비교하고, 재현하고, 설명하고, 신뢰할 수 있도록 충분히 구조화된 증거를 보존하는 일에 가깝습니다.

전통적인 Observability 논의는 흔히 세 가지 기둥에서 출발합니다.

- traces
- metrics
- logs

이 세 기둥은 ML 시스템에서도 여전히 중요합니다.
타이밍, 처리량, 오류 조사, 운영 디버깅에는 계속 유용합니다.
하지만 그것만으로는 충분하지 않습니다.

하나의 ML 워크플로는 단순한 런타임 동작 이상의 것을 만들어냅니다.
실험, 단계, 데이터셋, 체크포인트, 프롬프트 수준의 결과, 평가용 artifact, 환경 스냅샷, 배포 결정, 그리고 그 사이의 관계까지 함께 생성합니다.
만약 Observability가 주변의 증거 모델은 놓친 채 telemetry 스트림만 캡처한다면, 가장 중요한 ML 질문들 가운데 상당수는 끝내 답을 얻지 못합니다.

이 문서는 `Contexta`의 바탕이 되는 관점을 소개합니다.
이 문서는 좁은 의미의 API 레퍼런스가 아닙니다.
대신 이 프로젝트가 ML Observability를 하나의 분야로서 어떻게 바라보는지, 왜 그 관점이 기존의 세 가지 기둥보다 더 넓은지, 그리고 대상이 일반적인 서비스가 아니라 ML 시스템일 때 어떤 종류의 evidence가 first-class가 되는지를 설명합니다.

## 이 문서의 대상 독자

이 문서는 다음과 같은 독자를 위해 작성되었습니다.

- 전통적인 Observability 배경을 가진 엔지니어
- 이미 실험 추적은 하고 있지만 더 체계적인 모델을 원하는 ML 실무자
- 오프라인 evidence를 프로덕션 결과와 연결해야 하는 운영자
- API 세부 사항으로 들어가기 전에 개념적 틀을 먼저 이해하고 싶은 문서 독자

이 문서는 기능 소개 페이지보다 의도적으로 더 넓은 범위를 다룹니다.
각 개별 surface를 따로 보기 전에, 프로젝트의 시각을 분명히 이해할 수 있도록 돕는 것이 목적입니다.

## 가장 짧은 형태의 핵심 논지

이 문서 전체를 몇 문장으로 줄인다면 핵심 논지는 다음과 같습니다.

- 전통적인 Observability는 시스템이 내보내는 신호로부터 시스템을 이해할 수 있는지를 묻습니다.
- ML Observability는 ML 수명 주기를 그 evidence로부터 이해할 수 있는지를 묻습니다.
- 신호는 evidence의 일부이지만, evidence model 전체는 아닙니다.
- 유용한 ML Observability 시스템은 telemetry emission만이 아니라 구조, 컨텍스트, 관계, 품질 지표까지 보존해야 합니다.

이것이 `Contexta`가 취하는 개념적 이동입니다.

## 기존의 Observability만으로는 충분하지 않은 이유

전통적인 Observability는 다음과 같은 질문에 답하는 데 탁월합니다.

- 요청이 어디에서 시간을 소비했는가?
- 어떤 dependency가 실패했는가?
- 오류는 얼마나 발생했는가?
- latency가 악화되고 있는가?

이 질문들은 어떤 프로덕션 시스템에서도 중요합니다.
ML 시스템도 물론 여기에 답할 수 있어야 합니다.
학습 작업, 평가 파이프라인, feature builder, batch scoring 작업, 온라인 추론 서비스 모두 trace, metric, log의 도움을 받습니다.

하지만 ML 워크플로는 한 층 더 다른 종류의 질문을 만듭니다.

- 이 결과를 만든 run은 무엇인가?
- 그 run 내부의 어떤 stage가 변화를 만들었는가?
- 집계 지표는 멀쩡해 보여도 정확히 어떤 sample이 실패했는가?
- 어떤 artifact가 생성되고, 승격되고, 배포되었는가?
- 어떤 환경, 패키지 집합, 설정이 결과를 만들었는가?
- 우리가 기대했던 evidence 중 무엇이 빠졌는가?
- 이 run을 이전 run과 비교하고 delta를 설명할 수 있는가?
- 보고서나 배포 결정이 어떻게 형성되었는지 재구성할 수 있는가?

이 질문들은 부차적이지 않습니다.
ML 시스템을 구축하고, 평가하고, 검토하고, 운영하는 방식의 중심에 놓여 있습니다.

그래서 `Contexta`는 telemetry에서 멈추지 않습니다.
`Contexta`는 ML Observability를 구조화된 evidence system으로 봅니다.
`Contexta`의 관점에서 Observability 데이터는 다음 루프 전체를 지원해야 합니다.

1. capture
2. store
3. query
4. report

이 루프가 프로젝트 문서 전반에 반복해서 등장하는 이유는, 실행 중 신호를 방출하는 능력만큼이나 나중에 evidence를 읽고, 비교하고, 설명하는 능력이 중요하기 때문입니다.

## ML 시스템은 더 다양한 종류의 질문을 만든다

애플리케이션 Observability와 ML Observability의 차이를 이해하는 좋은 방법 중 하나는, 각 시스템이 주로 어떤 질문을 만들어내는지 비교해 보는 것입니다.

### 주로 운영적인 질문

이 질문들은 전통적인 Observability에 익숙한 질문들입니다.

- 서비스가 살아 있는가?
- latency가 나빠지고 있는가?
- 어떤 dependency가 실패하고 있는가?
- 어느 endpoint가 가장 많은 시간을 쓰고 있는가?
- 오류량이 증가하고 있는가?

이 질문들은 ML 시스템에서도 여전히 중요합니다.
추론 서비스, feature service, 평가 API, 학습 orchestrator 모두 이 질문의 혜택을 받습니다.

### 특히 ML에 특화된 질문

이 질문들은 traces, metrics, logs만으로는 답하기 훨씬 어렵습니다.

- 우리가 지금 논의하는 모델을 어떤 run이 만들었는가?
- 두 후보 run 사이에서 어떤 학습 또는 평가 단계가 바뀌었는가?
- 어떤 예제들이 실패했으며, 그것들이 slice나 prompt 유형별로 몰려 있는가?
- 코드가 바뀐 것인가, 환경이 바뀐 것인가, 데이터가 바뀐 것인가, 아니면 설정이 바뀐 것인가?
- 이 run의 canonical result로 어떤 artifact를 봐야 하는가?
- 배포 또는 보고 결정을 정당화하는 evidence는 무엇인가?
- 기록 중 어느 부분이 complete이고, partial이며, inferred이고, missing인가?

이런 질문들이 바로 `Contexta`가 ML Observability를 더 넓은 evidence discipline으로 프레이밍하는 이유입니다.

## ML Observability는 단순한 "MLOps 메타데이터"가 아니다

여기서 한 가지 분명히 해둘 점이 있습니다.

이 문서는 ML Observability가 단지 다음과 같다고 말하려는 것이 아닙니다.

- experiment tracking의 다른 이름
- model registry metadata
- 모델 지표용 dashboarding
- 태그 몇 개를 더한 application Observability

이 모든 것은 각자 유용합니다.
하지만 `Contexta`의 관점은 그것보다 더 넓고 더 통합적입니다.

experiment tracking은 흔히 결과 기록을 강조합니다.
model registry는 artifact 승격과 버전 관리를 강조합니다.
operational Observability는 런타임 telemetry를 강조합니다.

여기서 말하는 ML Observability는 이 세계들을 하나의 investigation model로 연결하려 합니다.
즉 run, 그 구조, 그 evidence, 그 artifact, 그 환경, 그 관계, 그리고 downstream outcome이 시간이 지난 뒤에도 함께 이해될 수 있는지를 묻습니다.

## 왜 "Evidence"가 중심 단어인가

이 문서에서 "evidence"라는 단어가 중요한 이유는, capture 이후 Observability data가 맡는 역할을 설명하기 때문입니다.

signals는 흔히 수집의 관점에서 이야기됩니다.
evidence는 설명의 관점에서 이야기됩니다.

이 차이는 중요합니다.

시스템이 telemetry를 내보낼 때 즉각적인 용도는 실시간 모니터링입니다.
반면 시스템이 evidence를 보존할 때는 이후의 사용 사례가 더 넓어집니다.

- forensic investigation
- comparison and review
- audit and governance
- reproducibility analysis
- deployment justification
- report generation

같은 metric도 두 역할을 모두 수행할 수 있습니다.
하지만 두 번째 역할을 제대로 하려면 주변 구조가 더 많이 필요합니다.

예를 들어 validation accuracy라는 숫자는 다음을 함께 알 때 훨씬 더 강한 evidence가 됩니다.

- 어느 run에 속하는가
- 어떤 stage가 만들었는가
- 어떤 environment가 만들었는가
- 어떤 artifact bundle이 이 run을 문서화하는가
- capture가 complete했는가
- 이전 run과 어떻게 비교되는가

이것이 바로 `Contexta`가 free-form telemetry-only view보다 schema-first, evidence-oriented view를 선호하는 이유입니다.

## 핵심 관점

`Contexta`의 핵심 아이디어는 ML Observability가 "runtime에 무슨 일이 있었는가?"만이 아니라 다음에도 답해야 한다는 것입니다.

- 무엇이 실행되었는가
- 실행은 어떻게 구조화되었는가
- 어떤 evidence가 생성되었는가
- 어떤 환경과 조건이 결과를 형성했는가
- 결과 객체들은 어떤 관계로 연결되는가
- evidence는 얼마나 complete하거나 incomplete한가
- 결과를 나중에 조사하고, 비교하고, 설명할 수 있는가

이것은 standard telemetry-only framing과는 다른 멘탈 모델로 이어집니다.

로그와 지표의 스트림에서 출발해 나중에 소비자가 의미를 유추하기를 기대하는 대신, `Contexta`는 runs, stages, records, artifacts, lineage, reports의 canonical structure에서 출발합니다.
telemetry는 여전히 그 구조의 일부이지만, 더 이상 전체 이야기는 아닙니다.

이 관점은 몇 가지 함의를 가집니다.

### ML Observability는 실행 인지적이다

시스템은 하나의 run 안에 이름 붙은 stage와 더 세분화된 operation이 들어 있다는 사실을 알아야 합니다.
나중에 stage-aware investigation이 필요할 텐데, 모든 것을 서로 분리된 이벤트로 납작하게 펴 버리면 안 됩니다.

### ML Observability는 evidence 지향적이다

목표는 단순히 무언가가 실행되었다는 사실을 아는 것이 아닙니다.
나중에 검토할 수 있는 evidence를 보존하는 것이 목표입니다.
metrics, events, spans, artifacts, environment snapshots 모두가 이 evidence base를 구성합니다.

### ML Observability는 재현성 인지적이다

환경 컨텍스트가 없는 metric은 신뢰하기 어렵습니다.
lineage가 없는 model bundle은 설명하기 어렵습니다.
sample-level evidence가 없는 evaluation result는 디버깅하기 어렵습니다.

### ML Observability는 불완전성에 대해 정직해야 한다

Observability 시스템은 종종 부분적으로 실패합니다.
capture gap이 생깁니다.
import 과정에서 세부 정보가 사라집니다.
compatibility upgrade로 구조가 단순화되기도 합니다.
replay는 incomplete할 수 있습니다.
`Contexta`는 degraded 또는 incomplete 상태를 숨겨진 모호함이 아니라 명시적인 데이터로 다룹니다.

### ML Observability는 수집뿐 아니라 조사를 지원해야 한다

유용한 Observability 시스템은 사용자가 run을 query하고, 결과를 compare하고, diagnostics를 보고, lineage를 따라가고, 사람이 읽을 수 있는 reports를 만들 수 있게 해야 합니다.
그렇지 않으면 그것은 storage mechanism일 뿐 investigation surface가 아닙니다.

### ML Observability는 수명 주기 인지적이다

ML 시스템은 일회성 runtime process가 아닙니다.
보통 다음을 포함합니다.

- preparation
- training 또는 generation
- evaluation
- packaging
- promotion
- deployment
- ongoing inspection

실행의 순간만 보고 그 주변 lifecycle을 보지 못하는 Observability model은, 왜 결과가 달라졌는지 또는 결과가 downstream으로 어떻게 이동했는지를 설명하기 어렵습니다.

### ML Observability는 review 지향적이다

많은 ML 결정은 실시간으로 단일 자동화 컴포넌트가 내리는 것이 아닙니다.
대개 review를 통해 이루어집니다.

- candidate run 비교
- 승격할 artifact 결정
- evaluation evidence가 충분한지 판단
- degradation이 수용 가능한지 확인

따라서 Observability system은 machine-oriented telemetry stream만 흘려보내는 것이 아니라, 사람이 evidence를 읽고 판단할 수 있도록 도와야 합니다.

## 더 넓은 정의

`Contexta`의 관점에서 ML Observability는 다음과 같이 설명할 수 있습니다.

> ML 실행, 결과, 컨텍스트, 관계, 품질에 대한 구조화된 evidence를 capture하고 보존하여, run을 시간이 지난 뒤에도 조사하고, 비교하고, 진단하고, 재현하고, 설명할 수 있게 만드는 실천.

이 정의에는 telemetry가 포함됩니다.
하지만 execution structure, artifacts, environment, lineage, completeness도 함께 포함됩니다.

그래서 이 프로젝트는 ML Observability를 단지 세 기둥으로 설명하기보다 여러 계층으로 설명하려는 경향을 갖습니다.

## 신호 모델과 증거 모델의 차이

신호 모델과 증거 모델의 차이는 별도로 분명히 해둘 가치가 있습니다.

### 신호 모델은 emission에 초점을 둔다

신호 모델은 다음을 묻습니다.

- 시스템은 무엇을 emit할 수 있는가?
- 우리는 그것을 ingest하는가?
- 어떻게 aggregate하는가?
- 어떻게 visualize하는가?

이것은 많은 운영용 dashboard와 alerting system에 잘 맞는 모델입니다.

### 증거 모델은 미래의 설명 가능성에 초점을 둔다

증거 모델은 다음을 묻습니다.

- 이것이 미래의 어떤 질문에 답하는 데 도움이 되는가?
- 신호와 함께 어떤 context가 저장되어야 하는가?
- 시간이 지나도 의미를 어떻게 보존하는가?
- uncertainty와 incompleteness를 어떻게 전달하는가?
- 관련된 조각들을 나중에 하나의 해석 가능한 객체로 어떻게 조립하는가?

`Contexta`는 훨씬 더 두 번째 모델에 가깝습니다.
signals 역시 중요하게 여기지만, 그것이 더 큰 evidence graph의 일부로 저장되기를 원합니다.

## 워크스페이스 관점

`Contexta` 관점의 미묘하지만 중요한 부분 중 하나는 workspace mindset입니다.

이 프로젝트는 개념적으로 local-first를 강하게 전제합니다.
이는 Observability data를 remote backend 어딘가에만 존재하는 것으로 보지 않고, inspectable하고 owned한 것으로 보기 때문에 중요합니다.

실제로 이 관점은 몇 가지 가치를 시사합니다.

- evidence는 canonical form으로 저장되어야 한다
- 사용자는 무엇이 존재하는지 직접 inspect할 수 있어야 한다
- reports와 exports는 같은 evidence base에서 파생되어야 한다
- recovery와 replay는 전체 이야기의 일부여야 한다

이 문서의 주제가 저장 메커니즘 자체는 아니지만, 저장 철학은 개념적 정의를 형성합니다.
evidence가 안정적인 집과 안정적인 형태를 가질 때 investigation은 더 반복 가능해집니다.

## ML Observability의 8개 계층

`Contexta`의 관점을 이해하는 가장 쉬운 방법은 여덟 개의 계층으로 생각하는 것입니다.
이 계층들은 임의적이지 않습니다.
프로젝트 문서와 코드베이스 전반에서 반복적으로 나타나는 객체와 서비스의 종류를 반영합니다.

1. execution context
2. record families
3. granularity units
4. artifact evidence
5. reproducibility context
6. relationship tracing
7. operational outcome
8. investigation and interpretation

각 계층은 서로 다른 종류의 질문에 답합니다.
이들이 함께 모여 ML Observability의 더 완전한 모델을 이룹니다.

## 8개 계층을 읽는 방법

이 여덟 개 계층은 서로 경쟁하는 것이 아니라 상호 보완적인 것으로 이해하는 편이 좋습니다.

- 앞의 계층은 무엇이 존재하는지를 정의합니다.
- 가운데 계층은 어떤 evidence가 붙는지를 정의합니다.
- 마지막 계층은 그 evidence가 어떻게 해석되는지를 정의합니다.

다른 방식으로 보면, 이것은 raw execution에서 human explanation으로 이동하는 흐름입니다.

1. 무언가가 실행된다
2. signals가 emit된다
3. 더 세분화된 단위가 관찰된다
4. outputs가 보존된다
5. 환경적 context가 캡처된다
6. 관계가 그려진다
7. 운영상의 결과가 연결된다
8. investigation surface가 전체를 이해 가능하게 만든다

이 중 하나라도 빠지면 전체 그림은 특정한 방식으로 약해집니다.
예를 들어:

- execution context가 없으면 evidence는 의미론적 위치를 잃습니다.
- granularity unit이 없으면 국소적 실패가 사라집니다.
- artifact가 없으면 결과물을 고정하기 어렵습니다.
- reproducibility context가 없으면 결과를 신뢰하기 어렵습니다.
- relationship tracing이 없으면 downstream 의미가 불투명해집니다.
- investigation surface가 없으면 evidence는 계속 사용하기 어렵습니다.

## 1. Execution Context

execution context는 무엇을 관측하고 있는지의 모양을 정의합니다.
일반적인 서비스에서는 trace만으로도 실행 구조를 설명하기에 충분할 수 있습니다.
하지만 ML에서는 구조가 보통 더 semantic하고 더 오래 남습니다.

`Contexta`는 다음 execution unit을 강조합니다.

- project
- run
- stage
- operation

### Project

project는 관련된 작업을 묶는 가장 높은 수준의 grouping입니다.
하나의 model family, 하나의 product workflow, 하나의 experiment domain, 또는 하나의 logical application boundary를 가리킬 수 있습니다.

project는 중요합니다.
ML investigation은 거의 항상 안정적인 grouping의 이점을 얻기 때문입니다.
trend analysis, run listing, model comparison, reporting 모두 run이 분명한 project scope 안에 있을 때 더 의미 있어집니다.

project context가 없으면 stored evidence는 구조 없는 실행의 더미가 되기 쉽습니다.
project context가 있으면 run은 이해 가능한 작업 체계의 일부가 됩니다.

### Run

run은 조사에서 가장 기본적인 단위입니다.
대부분의 경우 사용자가 나중에 들여다보고 싶어 하는 대상이 바로 run입니다.
하나의 run은 다음을 의미할 수 있습니다.

- 한 번의 training execution
- 한 번의 evaluation pass
- 한 번의 prompt assessment session
- 한 번의 export workflow
- 한 번의 batch inference job

이것은 관점의 가장 중요한 변화 중 하나입니다.
전통적인 Observability는 흔히 request나 process를 중심에 둡니다.
ML Observability는 흔히 run을 중심에 둡니다.

이것이 중요한 이유는 대부분의 downstream 질문이 run 중심이기 때문입니다.

- 이 run은 어떻게 수행되었는가?
- 이 run에 대해 어떤 evidence가 존재하는가?
- 이 run은 다른 run과 어떻게 다른가?
- 이 run은 어떤 artifact를 만들었는가?
- 이 run은 배포할 만큼 건강한가?

### Stage

stage는 run 안의 이름 붙은 부분입니다.
예를 들면 다음과 같습니다.

- prepare
- train
- evaluate
- export
- retrieve
- generate
- package

stage는 시스템이 semantic structure를 보존하게 해줍니다.
그 덕분에 나중의 해석은 훨씬 더 강해집니다.
`evaluate` stage의 `accuracy` metric은 숫자라는 점에서는 같아 보여도 `train` stage의 `loss` metric과 같은 것이 아닙니다.
누락된 `export` stage는 누락된 `prepare` stage와 전혀 다른 의미를 가질 수 있습니다.

실행 구조가 stage-aware일 때 시스템은 다음을 지원할 수 있습니다.

- stage-level comparison
- stage duration trends
- stage completeness checks
- stage-specific diagnostics

### Operation

operation은 stage 내부의 더 세분화된 단위입니다.
바로 이 층에서 ML Observability는 tracing과 더 직접적으로 맞닿습니다.
operation은 다음과 같은 하위 단계를 나타낼 수 있습니다.

- tokenization
- feature normalization
- retrieval
- reranking
- checkpoint serialization
- metric aggregation

operation은 stage-level visibility가 너무 거칠 때 중요해집니다.
사용자가 event, metric, artifact를 만든 정확한 sub-step으로 evidence의 범위를 좁히도록 도와줍니다.

### 왜 Execution Context가 중요한가

execution context는 해석의 backbone입니다.
이것이 없으면 telemetry를 나중에 이해하기가 훨씬 어려워집니다.
이것이 있으면 records와 artifacts는 서로 떠다니는 사실이 아니라 의미 있는 scope에 연결될 수 있습니다.

`Contexta`의 framing에서 Observability는 구조를 나중에 붙이는 것이 아니라 semantic execution structure에서 출발합니다.

### 이 계층이 없을 때의 실패 양상

execution context가 약하면 보통 다음과 같은 상태에 빠집니다.

- metrics가 의미 있는 stage에 연결되지 못한다
- logs가 이벤트를 말하지만 lifecycle 속 위치를 말하지 못한다
- artifact의 출처를 구조가 아니라 사회적 기억에 의존한다
- comparison이 모델링된 구조가 아니라 naming convention에 의존한다

즉 실행은 일어나지만 해석은 취약해집니다.

## 2. Record Families

record family는 실행 중에 append-style로 쌓이는 Observability fact입니다.
이 층은 전통적인 Observability pillar와 가장 비슷하지만, 여기서도 framing은 더 넓습니다.

`Contexta`는 네 가지 record family를 핵심으로 봅니다.

- events
- metrics
- spans
- degraded markers

### Events

event는 어떤 일이 일어났는지를 나타냅니다.
run의 서사에서 중요하게 남겨야 할 discrete fact에 적합합니다.

예를 들어:

- dataset loaded
- validation started
- checkpoint saved
- fallback path used
- schema validation failed

일반적인 시스템에서는 이런 내용이 free-form log 안에 묻혀 있을 수 있습니다.
하지만 ML Observability 시스템에서는 structured event가 더 유용합니다.
run, stage, batch, sample, operation에 연결될 수 있고 나중에 query할 수 있기 때문입니다.

### Metrics

metric은 측정된 값을 나타냅니다.
training과 evaluation 모두에서 중심적입니다.

예를 들어:

- training loss
- validation loss
- accuracy
- f1
- latency
- throughput
- artifact size
- relevance
- faithfulness

ML 시스템은 단 하나의 scope가 아니라 여러 scope에서 metric을 필요로 합니다.
`Contexta`는 이를 다음과 같은 aggregation scope로 드러냅니다.

- run
- stage
- operation
- step
- slice

metric은 흔히 가장 먼저 보는 evidence이지만, ML 시스템에서는 semantic execution context에 붙을 때 더 강해집니다.

### Spans

span은 시간이 있는 실행 구간을 나타냅니다.
run의 일부에서 duration과 sequence 정보를 제공합니다.

예를 들어:

- one inference call
- one retrieval sub-step
- one feature extraction step
- one export step

### Degraded markers

degraded marker는 `Contexta`가 ML Observability를 traces, metrics, logs보다 더 넓게 본다는 점을 분명히 보여줍니다.
이 마커는 incomplete 상태를 명시적으로 드러내기 위해 존재합니다.

예를 들어:

- partial capture
- missing inputs
- replay gaps
- import loss
- verification warnings
- recovery limitations

### 왜 Record Familiy가 중요한가

record family는 run의 시간 순서형 evidence stream을 제공합니다.
하지만 `Contexta`의 framing에서는 전체가 아니라 한 계층일 뿐입니다.
execution context, sample granularity, artifacts, investigation surface와 결합될 때 훨씬 더 큰 힘을 가집니다.

## 3. Granularity Units

ML 시스템은 aggregate statistic 아래에서 조용히 실패하는 경우가 많습니다.
그래서 `Contexta`는 batch와 sample을 독립적인 granularity unit으로 다룹니다.

### Batch

batch는 stage 안의 개별 데이터 처리 단위입니다.

예를 들어:

- one epoch
- one mini-batch group
- one cross-validation fold
- one file in a batch import
- one stream chunk

### Sample

sample은 실행 중 마주친 개별 항목입니다.

예를 들어:

- one training example
- one validation row
- one image
- one prompt
- one generated answer
- one retrieved document

### 왜 Granularity Unit이 중요한가

sample-level visibility가 없으면 평균은 멀쩡해 보여도 localized failure는 잘 드러나지 않습니다.
바로 이 계층이 aggregate monitoring view를 analysis-friendly ML view로 바꿉니다.

### 이 계층이 누락되었을 때의 실패 모드

배치 및 샘플 수준의 가시성이 없을 때, 집계된 값은 사람을 기만할 만큼 안심하게 만듭니다.
팀은 평균 결과는 알 수 있지만 다음은 알 수 없습니다:

- 어떤 프롬프트가 심하게 실패했는지
- 한 슬라이스가 퇴보했는지
- 후반 에포크에서만 경고가 나타났는지
- 작지만 중요한 하위 집합에 실패가 집중되었는지

많은 ML 문제들은 집계되기 전에 국소적으로 발생합니다.
이 계층은 문제를 초기에 드러내고 나중에 더 잘 설명하도록 돕습니다.

## 4. Artifact Evidence

ML workflow는 telemetry만 남기지 않습니다.
files, bundles, snapshots, reports처럼 실행의 evidence가 되는 출력도 함께 만듭니다.
`Contexta`는 이를 first-class artifact로 다룹니다.

예를 들어:

- dataset snapshots
- feature sets
- checkpoints
- config snapshots
- model bundles
- report bundles
- export packages
- evidence bundles
- debug bundles

### 왜 artifact가 Observability data인가

artifact는 ML 시스템에서 단순한 side effect가 아니라, 결과를 설명하는 핵심 evidence가 되는 경우가 많습니다.
checkpoint, report, model bundle, config snapshot 같은 것들은 모두 "무엇이 만들어졌는가"를 고정해 줍니다.

### Artifact Evidence는 단순 저장을 넘는다

artifact를 Observability entity로 모델링하면 다음과 연결될 수 있습니다.

- lineage
- verification
- comparison
- reporting
- export and import
- audit and recovery

### Artifact Evidence와 신뢰

metric은 무엇이 측정되었는지 말해 줍니다.
artifact는 무엇이 생산되었는지 말해 줍니다.
둘이 함께 있을 때 결과는 훨씬 설명 가능해집니다.

## 5. Reproducibility Context

실행 환경을 모르면 결과는 훨씬 덜 신뢰할 만해집니다.
ML workflow에서 reproducibility context는 optional metadata가 아니라 core Observability evidence입니다.

예를 들어:

- Python version
- platform
- package versions
- relevant environment variables
- captured-at time

### 왜 environment가 Observability에 속하는가

환경 차이는 metric 해석과 run 비교에 큰 영향을 줍니다.
package upgrade, tokenizer revision, platform change, CUDA 차이는 결과를 의미 있게 바꿀 수 있습니다.

### Reproducibility를 first-class concern으로 다루기

"어떤 조건에서 이 일이 일어났는가?"에 답하지 못하는 Observability system은 debugging, audit, comparison, deployment review를 지원하기 어렵습니다.

### Reproducibility Context와 해석

environment context는 run comparison, artifact lineage, diagnostics, reporting과 결합될 때 더욱 큰 의미를 가집니다.

## 6. Relationship Tracing

ML 시스템은 isolated record 집합이 아니라 연결된 entity 네트워크를 만듭니다.
그래서 relationship tracing은 핵심 계층이 됩니다.

`Contexta`는 다음을 사용합니다.

- lineage
- provenance

### Lineage

lineage는 entity가 서로 어떻게 연결되는지를 설명합니다.
artifact가 어디서 왔는지, 어떤 run이 어떤 model bundle을 만들었는지, 어떤 report가 무엇을 요약하는지 같은 질문이 여기에 속합니다.

### Provenance

provenance는 관계가 얼마나 믿을 만한지, 어떤 evidence와 policy가 그 관계를 뒷받침하는지를 설명합니다.

### 왜 Relationship Tracing이 중요한가

metric dashboard는 성능 저하를 보여줄 수 있지만, lineage와 provenance는 upstream input, artifact embodiment, deployment inheritance, evidence documentation을 설명합니다.

## 7. Operational Outcome

ML Observability는 experimentation에서 멈추면 안 됩니다.
experimental evidence를 operational outcome과 연결할 수 있을 때 훨씬 더 유용해집니다.

### Observability 증거로서의 배포

deployment는 단순한 release event가 아니라 이전 ML 작업의 observable result입니다.

예를 들어:

- 어떤 run이 deployed되었는가
- 어떤 artifact가 promoted되었는가
- 어떤 environment snapshot이 deployment와 연결되어 있는가
- deployment는 성공했는가 실패했는가

### 왜 이 계층이 중요한가

offline evaluation과 online use를 연결하는 다리가 바로 이 계층입니다.
이것이 없으면 experimentation과 production은 같은 이야기 안에 놓이기 어렵습니다.

### 운영 결과도 여전히 Observability다

질문은 "training 동안 무슨 일이 있었는가"에서 끝나지 않습니다.
"training의 결과물이 그 다음에 어떻게 되었는가"까지 이어집니다.

## 8. Investigation And Interpretation

앞선 계층이 무엇이 존재하는지를 설명했다면, 마지막 계층은 그 evidence로 무엇을 할 수 있는지를 설명합니다.
`Contexta`는 Observability가 investigation을 지원할 때 비로소 truly useful하다고 봅니다.

`Contexta`는 다음 interpretation surface를 강조합니다.

- query
- compare
- diagnostics
- trends
- reports

### Query

query는 run list, run snapshot, linked artifact, subject 주변 evidence를 읽는 기본 surface입니다.

### Compare

comparison은 run-to-run difference를 읽는 핵심 ML workflow입니다.
어떤 stage가 바뀌었는지, 어떤 metric이 regression을 보였는지, 어떤 artifact가 달라졌는지 살펴봅니다.

### Diagnostics

diagnostics는 degraded records, incomplete stages, missing terminal stages, failed batches, failed deployments 같은 suspicious state를 surface합니다.

### Trends

trend는 time 또는 run 간 movement를 다룹니다.
metric trend, stage duration trend, artifact size trend, step series가 여기에 속합니다.

### Reports

report는 stored evidence를 사람이 읽을 수 있는 summary로 바꿉니다.
review, sharing, archiving, governance, decision support에서 유용합니다.

### 왜 해석이 Observability의 일부인가

signals만 emit하는 시스템은 결국 사용자를 manual reconstruction으로 밀어 넣습니다.
그래서 `Contexta`는 read-oriented investigation surface 자체를 Observability의 일부로 봅니다.

## 실제 워크플로에서 계층들이 상호작용하는 방식

### 학습 워크플로

training workflow에서는 execution context, record families, granularity units, artifacts, reproducibility context, lineage, deployment linkage, interpretation surface가 모두 함께 작동합니다.
그 덕분에 단순히 "학습이 돌았다"를 넘어, 어떻게 돌았고 무엇을 만들었고 얼마나 신뢰할 수 있는지 설명할 수 있습니다.

### 평가 워크플로

evaluation workflow에서는 per-sample evidence와 aggregate metric이 함께 필요합니다.
소수의 catastrophic failure가 평균 아래 숨어 있을 수 있기 때문입니다.

### LLM 또는 RAG 워크플로

LLM 또는 RAG workflow에서는 prompt-level sample, retrieval-stage metric, generation-stage metric, relevance와 faithfulness, fallback behavior, evidence bundle, lineage가 특히 중요해집니다.

### 배포 워크플로

deployment workflow에서는 질문이 더 이상 "run이 무엇을 했는가"에 머물지 않습니다.
"그 결과 무엇이 앞으로 나아갔는가"가 더 중요해집니다.

## 약한 ML Observability 스토리의 모습

약한 ML Observability story는 흔히 다음을 보입니다.

- metric은 있지만 scope가 모호하다
- log는 있지만 lifecycle boundary가 implicit하다
- artifact는 있지만 origin이 convention에 의존한다
- environment 차이를 기억에 의존해 재구성한다
- sample-level failure가 평균 뒤에 숨는다
- 비교를 할 때마다 custom script에 의존한다
- missing evidence가 표현되지 않아 silence가 completeness처럼 보인다

## 더 강한 ML Observability 스토리의 모습

더 강한 ML Observability story는 대체로 다음을 갖습니다.

- explicit run structure
- meaningful scope에 attach된 records
- inspect 가능한 sample 또는 batch variation
- evidence object로 보존된 artifacts
- result와 함께 capture된 environment context
- explanation을 지원하는 lineage와 provenance
- 숨겨지지 않는 degraded 또는 partial state
- bespoke rescue task가 아닌 regular workflow로서의 comparison, diagnostics, reporting

## 왜 ML에서 명시적 불완전성이 특히 중요한가

ML에서는 evidence로부터 뒤늦게 결정을 내리는 경우가 많기 때문에, missing 또는 degraded evidence를 숨기면 판단이 쉽게 misleading해집니다.
그래서 partial answer는 partial로 남아야 하고, complete-looking answer로 조용히 변형되어서는 안 됩니다.

## 왜 이 관점은 보고서로 이어지는가

ML 결정은 사람이 읽는 형태로 review되는 경우가 많습니다.
run summary, candidate comparison, evidence archive, findings communication, governance workflow 모두 report를 필요로 합니다.
canonical evidence에서 report를 생성할 수 있다는 것은, evidence model이 explanation을 지원할 만큼 coherent하다는 뜻입니다.

## 완전성과 저하의 역할

`Contexta`는 completeness marker, degradation marker, degraded record, missing 또는 partial evidence note를 통해 evidence quality에 대한 정직성을 유지하려 합니다.
이것은 model comparison과 deployment decision이 overconfident해지는 일을 막는 데 중요합니다.

## 8개 계층과 세 가지 기둥의 관계

전통적인 세 pillar는 이 더 넓은 model 안에 여전히 들어갑니다.

- traces는 spans와 operation-level context에 가깝다
- metrics는 structured metric records와 trends에 가깝다
- logs는 structured events와 일부 degraded markers에 가깝다

하지만 execution structure, batch와 sample, artifacts, environment snapshot, lineage, provenance, deployment linkage, degraded-state modeling, report generation은 classic triad만으로는 잘 담기지 않습니다.

## 세 가지 기둥으로부터의 더 명시적인 매핑

### Traces

trace는 span과 operation, 일부 stage timing 정보에 가장 가깝습니다.
하지만 그것만으로는 ML run의 semantic unit을 정의하지 못합니다.

### Metrics

metric은 run, stage, operation, step, slice scope를 가진 metric record와 trend에 가장 가깝습니다.
하지만 그 의미는 evidence link와 comparison context가 explicit할 때 더 커집니다.

### Logs

log는 structured event, 일부 degraded marker, run의 narrative breadcrumb에 가장 가깝습니다.
하지만 free-form log alone은 이후의 structured comparison과 reporting에 약한 기반이 되곤 합니다.

### 세 가지 기둥 안에 깔끔하게 들어가지 않는 것들

- project와 run identity
- stage와 batch structure
- sample observation
- artifact manifest
- environment snapshot
- lineage와 provenance relation
- deployment linkage
- completeness와 degradation modeling
- canonical report generation

## ML Observability를 실용적으로 읽는 방법

성숙한 ML Observability system이라면 최소한 다음 질문에 답할 수 있어야 합니다.

- 어떤 project와 run을 보고 있는가
- 어떤 stage와 operation이 존재했는가
- 어떤 event, metric, span, degraded state가 기록되었는가
- 어떤 batch와 sample을 더 살펴봐야 하는가
- 어떤 artifact가 생성되거나 소비되었는가
- 어떤 environment와 package context가 결과를 형성했는가
- run, artifact, report, deployment는 어떻게 연결되는가
- 무엇이 최종적으로 deployed 또는 promoted되었는가
- 무엇이 missing, partial, ambiguous한가
- 이 결과를 query, compare, diagnose, trend, report할 수 있는가

## Contexta의 핵심 설계 직관

조금 더 짧게 말하면 다음과 같습니다.

- telemetry는 무슨 일이 일어났는지를 알려준다
- structure는 그것이 어디에서 일어났는지를 알려준다
- artifact는 무엇이 생산되었는지를 알려준다
- environment는 어떤 조건에서 일어났는지를 알려준다
- lineage는 그것이 어떻게 연결되는지를 알려준다
- degradation은 그 기록을 얼마나 trust해야 하는지를 알려준다
- reports와 diagnostics는 그것을 어떻게 해석해야 하는지를 알려준다

## 마지막 실용적 정의

> ML Observability는 run, stage, record, sample, artifact, environment, relationship, quality에 대한 충분히 구조화된 evidence를 보존하여, 미래의 investigation, comparison, reproducibility, review, operational decision-making을 가능하게 만드는 분야다.

## 이것이 Contexta에 의미하는 바

이 문서는 conceptual한 설명을 제공합니다.
모든 workflow가 이미 완성되었다거나, 모든 surface가 동일한 성숙도를 가졌다고 주장하지는 않습니다.
하지만 `Contexta`에 새겨진 방향성은 분명합니다.

- canonical evidence의 local-first storage
- structured run-oriented investigation
- records, artifacts, lineage, environment의 explicit modeling
- comparison, diagnostics, reporting에 대한 first-class support
- incomplete 또는 degraded state에 대한 honest treatment

`Contexta`는 ML Observability를 "ML에 적용된 logs, metrics, traces"로 보지 않습니다.
대신 ML execution과 outcome에 대한 structured evidence를 보존해, 시간이 지나도 이해 가능하고, 검토 가능하며, 신뢰할 수 있도록 유지하는 더 넓은 discipline으로 봅니다.

## 요약

`Contexta`의 의미에서 ML Observability는, 일이 일어난 뒤에도 ML execution을 읽을 수 있게 만드는 실천입니다.

여기에는 telemetry가 포함되지만, 동시에 다음도 포함됩니다.

- semantic execution structure
- sample 및 batch granularity
- artifact evidence
- reproducibility context
- lineage와 provenance
- deployment outcome
- explicit degraded-state modeling
- query, comparison, diagnostics, trends, reports를 위한 interpretation surface

이것이 이 프로젝트의 관점입니다.
그리고 이것이 바로 `Contexta`가 public concept를 telemetry alone이 아니라 runs, stages, records, artifacts, lineage, reports를 중심으로 구성하는 이유입니다.
