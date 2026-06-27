# 3단계: PostgreSQL 영속화

## 목표

대화방, 사용자 메시지, AI 메시지를 PostgreSQL에 저장하고 DB 구조 변경을
Alembic migration으로 재현합니다.

## 추가된 계층

- `db/models.py`: `Conversation`, `Message`
- `db/session.py`: 비동기 엔진과 요청별 세션
- `repositories`: DB 조회와 ORM 객체 추가
- `services/chat_service.py`: 트랜잭션 순서
- `alembic`: 테이블 생성 이력

## 두 번 commit하는 이유

```text
사용자 메시지 commit
  → 외부 LLM 호출
  → AI 메시지 commit
```

LLM 호출은 느리거나 실패할 수 있습니다. DB 트랜잭션을 열린 채 기다리면 연결을
오래 점유하고 잠금 가능성도 커집니다. 사용자 메시지를 먼저 확정하면 LLM 장애가
발생해도 어떤 요청이 실패했는지 기록이 남습니다.

스트리밍 답변은 조각마다 INSERT하지 않습니다. 정상 완료 후 조각을 합쳐 하나의
assistant 메시지로 저장합니다. 연결이 끊긴 불완전한 답변은 저장하지 않습니다.

## migration 순서

`20260627_0001_create_chat_tables.py`는 부모인 `conversations`를 먼저 만들고
자식인 `messages`를 생성합니다. downgrade는 외래 키 관계 때문에 정확히 역순으로
삭제합니다.

## 실행과 확인

```powershell
alembic upgrade head
alembic current
```

```sql
SELECT conversation_id, role, content, created_at
FROM messages
ORDER BY created_at;
```

## 직접 확인할 코드

1. `app/db/session.py`의 세션 수명
2. `app/repositories/message_repository.py`의 commit 없는 저장
3. `app/services/chat_service.py`의 `start_turn()`과 `complete_turn()`
4. `tests/test_chat_service.py`의 이벤트 순서 assertion

## 다음 단계가 필요했던 이유

모든 대화가 같은 일반 assistant 프롬프트를 사용했습니다. 4단계에서는 캐릭터를
저장하고 대화마다 성격과 말투를 선택하도록 확장했습니다.
