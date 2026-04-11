# 고급 Contexta 사용법

이 가이드는 루트 퍼사드(facade)를 넘어 설정, 원본(Source of Truth) 스토어, 해석 서비스(interpretation services) 또는 복구 워크플로를 직접 다루어야 하는 사용자를 위한 것입니다.

기본 원칙은 다음과 같습니다:

- 우선 `Contexta`를 사용하세요.
- 퍼사드가 충분히 구체적이지 않을 때만 하위 계층으로 내려가세요.
- 그 과정에서도 공용 네임스페이스 내부에 머무르세요.

## 언제 퍼사드를 넘어서야 하는가

기본적인 쿼리, 비교, 리포트 또는 진단 워크플로에서는 대개 고급 API가 필요하지 않습니다.

다음과 같은 경우에 퍼사드를 넘어서는 기능을 사용하세요:

- 명시적인 설정 해결(config resolution)이 필요할 때
- 메타데이터, 레코드 또는 아티팩트 플레인에 직접 쓰고 싶을 때
- 직접적인 재생(replay), 검증 또는 무결성(integrity) 작업을 수행할 때
- 복구 계획을 세울 때

## 명시적 설정 제어

가장 명확한 공용 설정 인터페이스는 `contexta.config`입니다.

설정을 직접 구축할 수 있습니다:

```python
from pathlib import Path

from contexta import Contexta
from contexta.config import UnifiedConfig, WorkspaceConfig

config = UnifiedConfig(
    project_name="advanced-proj",
    workspace=WorkspaceConfig(root_path=Path(".contexta")),
)

ctx = Contexta(config=config)
```

또는 로더를 통해 설정을 해결할 수 있습니다:

```python
from contexta.config import load_config

resolved = load_config(
    profile="test",
    workspace=".contexta",
    config={"project_name": "advanced-proj"},
)
```

다음과 같은 경우에 명시적 설정 제어를 사용하세요:

- 스크립트 및 테스트를 위한 결정론적 온보딩
- 프로필 기반 동작
- 주변 상태(ambient state) 없는 직접적인 설정 패치
- 더 명확한 워크스페이스 소유권

## 직접적인 원본(Source of Truth) 스토어 접근

퍼사드는 세 가지의 영구 저장 원본(Source of Truth) 스토어를 노출합니다:

- `ctx.metadata_store`
- `ctx.record_store`
- `ctx.artifact_store`

### 메타데이터 플레인 (Metadata Plane)

표준 프로젝트, 실행, 스테이지, 관계 또는 프로버넌스 쓰기에 대한 직접적인 제어가 필요할 때 메타데이터 플레인을 사용하세요:

```python
from contexta.contract import Project

project = Project(
    project_ref="project:advanced-proj",
    name="advanced-proj",
    created_at="2024-06-01T12:00:00Z",
)

ctx.metadata_store.projects.put_project(project)
```

### 레코드 플레인 (Record Plane)

재생, 내보내기 또는 무결성 중심의 동작이 필요할 때 레코드 플레인을 사용하세요:

```python
from contexta.store.records import ReplayMode

replay = ctx.record_store.replay(mode=ReplayMode.TOLERANT)
print(replay.record_count)
print(replay.integrity_state.value)
```

### 아티팩트 플레인 (Artifact Plane)

검증 또는 스토어 수준의 조사가 필요할 때 아티팩트 플레인을 사용하세요:

```python
summary = ctx.artifact_store.inspect_store()
print(summary.artifact_count)
print(summary.verified_count)
```

해당 작업이 진정으로 플레인에 특화된 경우에만 이러한 플레인 API로 이동하세요. 대부분의 읽기 워크플로에서는 퍼사드가 여전히 더 나은 진입점입니다.

## 직접적인 해석 서비스 (Interpretation Services)

이미 `Contexta` 인스턴스가 있다면, 그 뒤에 지연 생성된 서비스들을 사용하는 것이 가장 자연스러운 고급 경로입니다:

- `ctx.query_service`
- `ctx.compare_service`
- `ctx.diagnostics_service`
- `ctx.lineage_service`
- `ctx.trend_service`
- `ctx.alert_service`
- `ctx.provenance_service`
- `ctx.report_builder`

예를 들어:

```python
query_service = ctx.query_service
compare_service = ctx.compare_service

snapshot = query_service.get_run_snapshot("run:advanced-proj.demo-run")
comparison = compare_service.compare_runs(
    "run:advanced-proj.demo-run",
    "run:advanced-proj.demo-run-v2",
)
```

이 방식은 직접 스토어 및 저장소 그래프를 다시 구축하지 않고 서비스 수준의 제어를 원할 때 유용합니다.

## 복구 워크플로 (Recovery Workflows)

복구는 임시 쉘 스크립트가 아니라 제품 내부의 기능이어야 합니다.

### 백업 계획 및 생성

```python
from contexta.recovery import create_workspace_backup, plan_workspace_backup

plan = plan_workspace_backup(ctx.config, label="manual")
result = create_workspace_backup(ctx.config, plan)

print(result.backup_ref)
print(result.location)
```

실행 가능한 예제:

- [복구 백업/복구 예제](../../../examples/recovery/backup_restore_verify.py)

### 복구 계획 (Restore Planning)

```python
from contexta.recovery import plan_restore, restore_workspace

restore_plan = plan_restore(
    ctx.config,
    result.backup_ref,
    verify_only=True,
)
restore_check = restore_workspace(ctx.config, restore_plan)

print(restore_check.status)
print(restore_check.verification_notes)
```

실행 가능한 예제:

- [Outbox 메시지 재처리 예제](../../../examples/recovery/replay_outbox_demo.py)
- [복구 아티팩트 전송 예제](../../../examples/recovery/artifact_transfer_demo.py)

다음 작업이 필요할 때 복구 패키지를 사용하세요:

- 백업 또는 복구 계획
- Outbox 메시지 재처리(Replay)

## 준수해야 할 공용 경계 (Public Boundaries)

안전한 공용 대상:

- `contexta`
- `contexta.config`
- `contexta.contract`
- `contexta.capture`
- `contexta.store.metadata`
- `contexta.store.records`
- `contexta.store.artifacts`
- `contexta.interpretation`
- `contexta.recovery`

다음과 같은 내부 네임스페이스를 대상으로 새로운 코드를 작성하지 마세요:

- `contexta.api`
- `contexta.runtime`
- `contexta.common`
- `contexta.surfaces`

이러한 모듈들은 저장소에 존재하지만, 사용자나 기여자가 기반으로 삼기를 바라는 공용 계약이 아닙니다.

## 프로토타입 유의 사항

현재 프로토타입 단계에서:

- 패키징이 외부에서 처리되지 않는 한, 로컬 체크아웃에서의 소스 트리 스크립트는 여전히 `PYTHONPATH=src`가 필요합니다.

이는 과도기적인 세부 사항이며, 장기적으로 지향하는 제품의 정체성은 아닙니다.

## 다음 읽을거리

다음으로 이어지는 문서:

- [테스트 가이드](./testing.md)
- 작성 완료된 API, CLI 및 HTTP 레퍼런스
