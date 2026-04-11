# Contexta 운영 가이드

이 가이드는 복구 중심의 `Contexta` 워크플로를 다루는 운영자 및 고급 사용자를 위한 것입니다.

현재 공용 운영 페이스(surface)는 다음 사항들을 중심으로 구성되어 있습니다:

- 워크스페이스 백업
- 복구 계획 및 검증 전용(verify-only) 체크
- 아웃박스(outbox) 재생(Replay)
- 아티팩트 검증 및 전송

현재의 프로토타입 단계에서 가장 신뢰할 수 있는 운영자 경로는 `contexta.recovery`의 공용 Python API와 [`examples/recovery/`](../../examples/recovery/README.md)에 있는 실행 가능한 예제들입니다.

## 여기서 시작하세요

복구 인터페이스가 처음이라면 다음 순서대로 확인하세요:

1. [고급 사용법](./user-guide/advanced.md)
2. [복구 예제](../../examples/recovery/README.md)
3. [CLI 레퍼런스](./reference/cli-reference.md)

이 경로는 운영 가이드를 실행 가능한 예제 및 현재 명령 동작과 연결하여 제공합니다.

## 핵심 원칙

- 적용하기 전에 먼저 계획을 세우는 것을 권장합니다.
- 파괴적인 복구를 수행하기 전에 검증 전용 복구(verify-only restore)를 먼저 수행하는 것을 권장합니다.
- 복구 작업은 하나의 명시적인 워크스페이스 내부에서 유지하세요.
- 내부 모듈을 직접 사용하는 대신 공용 복구 API와 예제를 사용하세요.

## 백업 (Backup)

현재 공식 백업 워크플로는 다음과 같습니다:

```python
from contexta.recovery import create_workspace_backup, plan_workspace_backup

plan = plan_workspace_backup(config, label="manual")
result = create_workspace_backup(config, plan)
```

이 작업을 통해 얻을 수 있는 것:

- 안정적인 백업 참조(reference)
- 설정된 복구 루트 아래의 백업 디렉터리
- 포함된 섹션들을 설명하는 매니페스트(manifest)

현재 운영 참고 사항:

- 캐시 및 내보내기는 명시적으로 포함하지 않는 한 기본적으로 제외됩니다.
- 백업 출력물은 워크스페이스 지향적이며, 원격 스냅샷 서비스가 아닙니다.
- 백업 헬퍼는 더 침습적인 작업을 수행하기 전의 사전 변경 체크포인트로 사용하기에 안전합니다.

실행 가능한 예제:

- [백업 및 검증 전용 복구 예제](../../examples/recovery/backup_restore_verify.py)

## 복구 (Restore)

현재 가장 안전한 복구 방식은 검증 전용(verify-only)입니다:

```python
from contexta.recovery import plan_restore, restore_workspace

restore_plan = plan_restore(config, backup_ref, verify_only=True)
restore_result = restore_workspace(config, restore_plan)
```

다음 사항을 확인하고 싶을 때 검증 전용 방식을 사용하세요:

- 백업 매니페스트를 읽을 수 있는지 여부
- 준비된 워크스페이스가 구체화될 수 있는지 여부
- 메타데이터, 레코드 및 아티팩트가 현재의 검증 경로를 통과하는지 여부

현재 운영 참고 사항:

- 검증 전용 방식은 대상 워크스페이스를 덮어쓰지 않습니다.
- 검증 전용이 아닌 복구는 대상 워크스페이스의 내용을 대체할 수 있습니다.
- 설정에 의해 활성화된 경우, 복구 작업은 적용 전에 안전 백업을 생성할 수 있습니다.

## 재생 (Replay)

재생은 일반적인 쿼리 워크플로가 아닌 복구-아웃박스(recovery-outbox) 처리를 위한 것입니다.

공식 진입점은 다음과 같습니다:

```python
from contexta.recovery import replay_outbox

result = replay_outbox(config)
```

다음의 경우에 재생 기능을 사용하세요:

- 실패한 싱크(sink) 전달을 재시도할 때
- 승인됨, 대기 중, 데드 레터(dead-lettered) 카운트를 조사할 때
- 실패한 페이로드를 재생 대상 싱크로 이동할 때

현재 운영 참고 사항:

- 재생 기능을 사용하려면 `config.recovery.outbox_root` 설정이 필요합니다.
- 기본 재생 싱크는 워크스페이스의 내보내기(exports) 영역 아래에 기록됩니다.
- 재생은 복구 동작이므로 숨겨진 부작용으로 실행하기보다는 의도적으로 실행해야 합니다.

실행 가능한 예제:

- [아웃박스 재생 예제](../../examples/recovery/replay_outbox_demo.py)

## 아티팩트 검증 및 전송 (Artifact Verification And Transfer)

아티팩트 전송은 현재 최상위 복구 퍼사드(facade)보다는 아티팩트 스토어의 공용 인터페이스를 통해 처리하는 것이 가장 좋습니다.

유용한 현재 작업들:

- `inspect_store(...)`
- `verify_artifact(...)`
- `verify_all(...)`
- `export_artifact(...)`
- `import_export_package(...)`

다음의 경우에 이 기능들을 사용하세요:

- 저장된 아티팩트 본문을 검증할 때
- 자기 설명적 패키지(self-describing package)를 내보낼 때
- 해당 패키지를 다른 스토어 루트로 가져올 때

실행 가능한 예제:

- [아티팩트 전송 예제](../../examples/recovery/artifact_transfer_demo.py)

## 안전 체크리스트

위험한 복구 작업을 시작하기 전:

- 대상 워크스페이스 경로를 확인하세요.
- 데이터가 중요하다면 새로운 백업을 생성하세요.
- 검증 전용 복구를 먼저 수행하는 것을 권장합니다.
- 경고, 손실 정보 및 검증 노트를 무시하지 말고 면밀히 조사하세요.

## 명령줄 참고 사항 (Command-Line Notes)

내장된 CLI는 이미 작은 유지보수 기능을 제공합니다:

- `contexta backup create`
- `contexta restore apply`
- `contexta recover replay`

현재 프로토타입 단계에서:

- 공용 문서는 표준 `contexta` 명칭을 사용합니다.
- Python API와 실행 가능한 예제는 여전히 가장 명확한 운영자 계약을 유지합니다.

참고:

- [CLI 레퍼런스](./reference/cli-reference.md)

## 유효성 검사

운영 문서나 예제를 변경한 경우 다음 명령을 다시 실행하세요:

```powershell
uv run pytest tests/e2e/test_recovery_examples.py -q
```

변경 사항이 재생 동작이나 복구 로직에도 영향을 미치는 경우, [테스트 가이드](./user-guide/testing.md)에서 가장 가까운 복구 스위트로 유효성 검사를 확장하세요.
