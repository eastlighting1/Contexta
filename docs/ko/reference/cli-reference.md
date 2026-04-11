# Contexta CLI 레퍼런스

이 페이지는 `Contexta`에 내장된 현재 명령줄 인터페이스(CLI)를 문서화합니다.

표준 CLI 명칭은 `contexta`이며, 아래의 명령 트리 전체에서 해당 이름을 사용합니다.

## 이 레퍼런스의 범위

이 페이지는 오늘날 저장소에 실제로 존재하는 명령 트리를 문서화합니다.

다음 사항은 문서화하지 않습니다:

- 마이그레이션 계획에는 제안되었으나 아직 구현되지 않은 미래의 명령 그룹
- `contexta.surfaces.cli` 내부의 헬퍼 함수
- 현재 파서의 일부가 아닌 가상의 관리자 트리

## 전역 옵션 (Global Options)

현재 파서는 명령 앞에 다음과 같은 전역 옵션을 지원합니다:

| 옵션 | 의미 |
| --- | --- |
| `--workspace <path>` | 워크스페이스 루트, 기본값 `.contexta` |
| `--profile local|test` | 설정 프로필 이름 |
| `--config <path>` | 외부 설정 패치 파일 |
| `--set key=value` | 직접적인 설정 재정의(override), 반복 가능 |
| `--format text|json` | 출력 형식, 기본값 `text` |
| `--quiet` | 해당되는 경우 결과 이외의 상태 줄 표시 안 함 |

예시:

```bash
contexta --workspace .contexta --format json runs
```

## 종료 동작 (Exit Behavior)

현재 CLI의 종료 동작은 다음과 같습니다:

- 성공 시 `0`
- 처리된 런타임 에러 시 `1`
- 인자 파싱 또는 사용법 에러 시 `2`

`--format json` 옵션을 사용하면 처리된 에러는 stderr에 JSON으로 출력됩니다.

## 명령 트리 (Command Tree)

```text
contexta/
├─ runs/
├─ run/
│  ├─ list
│  ├─ show
│  ├─ compare
│  ├─ compare-many
│  └─ diagnose
├─ lineage
├─ search/
│  ├─ runs
│  └─ artifacts
├─ compare
├─ compare-multi
├─ diagnostics
├─ trend
├─ aggregate
├─ anomaly
├─ alert
├─ report/
│  ├─ snapshot
│  └─ compare
├─ export/
│  ├─ html
│  └─ csv/
│     ├─ runs
│     ├─ compare
│     ├─ trend
│     └─ anomaly
├─ serve/
│  └─ http
├─ provenance/
│  ├─ audit
│  └─ diff
├─ artifact/
│  ├─ register
│  └─ put
├─ backup/
│  └─ create
├─ restore/
│  └─ apply
└─ recover/
   └─ replay
```

## 쿼리 및 조사 명령 (Query And Investigation Commands)

이 섹션의 예시에서는 가능한 경우 표준 실행 참조(run refs)를 사용합니다. 내부 구현에서는 일부 저장소 로컬 컨텍스트에서 더 짧은 실행 식별자를 허용할 수 있지만, 표준 참조 방식이 권장되는 공용 스타일입니다.

### `runs`

현재 워크스페이스에서 실행 목록을 직접 조회합니다.

```bash
contexta runs [--project NAME] [--status STATUS] [--after ISO] [--before ISO] [--limit N] [--offset N] [--sort started_at|ended_at|name] [--desc]
```

별칭(Alias):

- `contexta run list`

### `run show`

하나의 실행 스냅샷을 표시합니다.

```bash
contexta run show <run_id>
```

### `compare`

두 실행을 비교합니다.

```bash
contexta compare <left_run_id> <right_run_id>
```

별칭:

- `contexta run compare <left_run_id> <right_run_id>`

### `compare-multi`

여러 실행을 비교합니다.

```bash
contexta compare-multi <run_id> <run_id> [...]
```

별칭:

- `contexta run compare-many <run_id> <run_id> [...]`

### `diagnostics`

하나의 실행을 진단합니다.

```bash
contexta diagnostics <run_id> [--fail-on info|warning|error]
```

별칭:

- `contexta run diagnose <run_id> [--fail-on ...]`

### `lineage`

대상 참조에 대한 리니지(lineage)를 추적합니다.

```bash
contexta lineage <subject_ref> [--direction upstream|downstream|inbound|outbound|both] [--depth N]
```

참고:

- `upstream`과 `downstream`은 사용자 측면에서 허용되는 별칭입니다.
- 현재 구현에서는 이를 inbound/outbound 순회 방향으로 정규화하여 처리합니다.

### `search`

현재 워크스페이스 데이터를 검색합니다.

실행 검색:

```bash
contexta search runs <text> [--project NAME] [--status STATUS] [--limit N]
```

아티팩트 검색:

```bash
contexta search artifacts <text> [--kind KIND] [--limit N]
```

### `trend`

메트릭 추세를 쿼리합니다.

```bash
contexta trend <metric_key> [--project NAME] [--stage STAGE] [--status STATUS] [--after ISO] [--before ISO] [--limit N] [--offset N] [--sort started_at|ended_at|name] [--desc]
```

### `aggregate`

하나의 메트릭에 대한 집계(aggregate)를 쿼리합니다.

```bash
contexta aggregate <metric_key> [--project NAME] [--stage STAGE] [--status STATUS] [--after ISO] [--before ISO] [--limit N] [--offset N] [--sort started_at|ended_at|name] [--desc]
```

### `anomaly`

하나의 실행에 대해 이상 징후를 탐지합니다.

```bash
contexta anomaly <run_id> [--metric KEY ...] [--project NAME] [--stage STAGE]
```

### `alert`

하나의 실행에 대해 임계값 알림을 평가합니다.

```bash
contexta alert <run_id> --metric <metric_key> --operator gt|lt|gte|lte|eq|ne --threshold <value> [--stage STAGE] [--severity LEVEL]
```

## 리포트 및 내보내기 명령 (Report And Export Commands)

### `report snapshot`

하나의 실행 스냅샷에 대한 리포트를 빌드합니다.

```bash
contexta report snapshot <run_id> [--render markdown|json|html|csv] [--output PATH]
```

### `report compare`

하나의 실행 비교에 대한 리포트를 빌드합니다.

```bash
contexta report compare <left_run_id> <right_run_id> [--render markdown|json|html|csv] [--output PATH]
```

### `export html`

하나의 실행 또는 하나의 비교로부터 HTML을 내보냅니다.

```bash
contexta export html --run <run_id> [--output PATH]
contexta export html --left <left_run_id> --right <right_run_id> [--output PATH]
```

### `export csv`

현재 CSV 내보내기 인터페이스는 4개의 하위 명령을 지원합니다.

실행 목록 CSV:

```bash
contexta export csv runs [--project NAME] [--status STATUS] [--after ISO] [--before ISO] [--limit N] [--offset N] [--sort started_at|ended_at|name] [--desc] [--output PATH]
```

비교 CSV:

```bash
contexta export csv compare <left_run_id> <right_run_id> [--output PATH]
```

추세 CSV:

```bash
contexta export csv trend <metric_key> [--project NAME] [--stage STAGE] [--status STATUS] [--after ISO] [--before ISO] [--limit N] [--offset N] [--sort started_at|ended_at|name] [--desc] [--output PATH]
```

이상 탐지 CSV:

```bash
contexta export csv anomaly <run_id> [--metric KEY ...] [--project NAME] [--stage STAGE] [--output PATH]
```

## 전달 및 프로버넌스 명령 (Delivery And Provenance Commands)

### `serve http`

내장 HTTP 서버를 시작합니다.

```bash
contexta serve http [--host HOST] [--port PORT]
```

중요 참고 사항:

- 현재 명령 그룹은 `serve http`입니다.
- 현재 파서에는 별도의 최상위 `ui` 그룹이 없습니다.

### `provenance audit`

재현성 중심의 프로버넌스 신호에 대해 하나의 실행을 감사(audit)합니다.

```bash
contexta provenance audit <run_id>
```

### `provenance diff`

실행 환경을 비교합니다.

```bash
contexta provenance diff <left_run_id> <right_run_id>
```

## 아티팩트 명령 (Artifact Commands)

현재 아티팩트 인터페이스는 의도적으로 좁게 설정되어 있습니다.

### `artifact register`

아티팩트를 아티팩트 스토어에 등록합니다.

```bash
contexta artifact register <artifact_kind> <source_path> --run <run_ref> [--stage <stage_ref>] [--artifact-ref <artifact_ref>] [--mode copy|move|adopt]
```

### `artifact put`

`artifact register`의 별칭입니다.

```bash
contexta artifact put <artifact_kind> <source_path> --run <run_ref> [--stage <stage_ref>] [--artifact-ref <artifact_ref>] [--mode copy|move|adopt]
```

중요 참고 사항:

- 현재 파서는 별도의 `artifact verify`, `artifact export` 또는 `artifact import-package` 명령을 아직 노출하지 않습니다.
- 이러한 더 넓은 워크플로는 현재 내장된 명령 인터페이스가 아닌 미래의 CLI 정렬 작업에 속합니다.

## 백업, 복구 및 재생 (Backup, Restore, And Replay)

### `backup create`

워크스페이스 zip 백업을 생성합니다.

```bash
contexta backup create [--label LABEL] [--output PATH_STEM]
```

현재 동작:

- 현재 CLI는 zip 아카이브를 작성합니다.
- `--output`이 제공되면 `<PATH_STEM>.zip` 위치에 아카이브가 생성됩니다.
- 이것은 프로토타입에서의 가벼운 워크스페이스 레벨 CLI 헬퍼입니다.

### `restore apply`

백업 아카이브를 복구하거나 검증합니다.

```bash
contexta restore apply <backup_archive_path> [--target-workspace PATH] [--verify-only]
```

중요 참고 사항:

- 내부 인자 이름은 `backup_ref`이지만, 현재 명령은 백업 아카이브 경로를 기대합니다.

### `recover replay`

레코드 플레인으로부터 레코드를 재생합니다.

```bash
contexta recover replay [--mode strict|tolerant] [--run <run_ref>] [--stage <stage_ref>] [--record-type event|metric|span|degraded]
```

## 출력 모드 (Output Modes)

전역 `--format` 옵션은 명령 결과가 텍스트로 출력될지 JSON으로 출력될지를 제어합니다.

```bash
contexta --format json runs
contexta --format json diagnostics run:demo.run-01
```

일부 리포트 및 내보내기 명령은 `--render html` 또는 `--render json`과 같은 명령 로컬 렌더링 선택 사항도 지원합니다.

## 현재 프로토타입 참고 사항

현재 프로토타입 단계에서:

- 공용 문서에서는 표준 명령 명칭인 `contexta`를 사용합니다.
- 현재 런처는 `contexta`입니다.
- 현재 파서는 여기에 문서화된 명령 그룹을 지원합니다.
- 패키징 및 콘솔 스크립트 정렬 작업이 진행 중인 동안, 소스 트리 워크플로에는 여전히 저장소 로컬 설정이 필요할 수 있습니다.

이는 이 페이지가 최종적으로 발행될 런처 명칭이 아직 조정 중임을 정직하게 명시하면서도, 내장 CLI 인터페이스에 대한 현재의 명령 계약으로 읽혀야 함을 의미합니다.
