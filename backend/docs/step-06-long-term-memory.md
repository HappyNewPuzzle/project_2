# 6단계: 장기 기억

## 목표

최근 대화 N개에서 밀려난 뒤에도 유지할 사용자 정보를 별도 `memories` 테이블에
저장하고, 다음 대화의 배경 문맥으로 사용합니다.

## 기억 범위

- `character_id=NULL`: 모든 캐릭터에 적용되는 전역 사용자 기억
- `character_id=UUID`: 특정 캐릭터와 대화할 때만 적용되는 기억
- `is_active=false`: 삭제하지 않고 프롬프트 사용만 중지
- `importance=1~5`: 제한된 개수에서 우선 선택할 중요도

모든 기억에는 `user_id`가 있어 다른 사용자의 기억을 조회하거나 수정할 수 없습니다.

## 기억 API

```text
POST   /memories
GET    /memories
GET    /memories/{id}
PATCH  /memories/{id}
DELETE /memories/{id}
```

현재는 사용자가 기억을 명시적으로 생성합니다. 자동 추출을 바로 넣지 않은 이유는
별도 LLM 비용, 잘못 추출된 사실 수정, 중복 병합, 민감 정보 정책이 먼저 필요하기
때문입니다.

## 채팅 조회 순서

```text
현재 user_id
  + 활성 상태
  + 전역 또는 현재 character_id
  → importance DESC
  → updated_at DESC
  → CHAT_MEMORY_LIMIT
```

최근 메시지는 시간순, 기억은 중요도순이라는 서로 다른 조회 전략을 사용하므로
repository 메서드도 분리되어 있습니다.

## 프롬프트 권한

캐릭터 규칙은 애플리케이션이 관리하므로 `instructions`에 들어갑니다. 기억 내용은
사용자가 관리하는 데이터이므로 높은 권한으로 올리지 않고 별도의 `user` 메시지로
최근 대화 앞에 추가합니다.

```text
user: Previously saved background information...
      - 사용자는 천문학을 좋아한다.
user: 최근 질문
assistant: 최근 답변
user: 현재 질문
```

## migration

`20260628_0004_add_long_term_memories.py`는 다음을 추가합니다.

- `memories` 테이블
- users/characters 외래 키
- importance 1~5 CHECK 제약
- 사용자·캐릭터·활성 상태·중요도 복합 인덱스

사용자나 캐릭터가 삭제되면 관련 기억도 `CASCADE`로 제거됩니다.

## 직접 확인할 코드

1. `app/db/models.py`의 `Memory`
2. `app/repositories/memory_repository.py`의 `list_for_prompt()`
3. `app/services/memory_service.py`의 소유권 검증
4. `app/services/chat_service.py`의 기억 메시지 조립
5. `tests/test_chat_service.py`의 LLM 입력 순서 검증

## 다음 단계

7단계에서는 Docker 배포 구조, health check, 운영 로그, rate limit을 추가하고,
장기 기억은 이후 pgvector embedding 검색으로 확장할 수 있습니다.
