# 19단계: 장기 기억 자동 추출 구조

이번 단계의 목표는 채팅이 끝난 뒤 LLM으로 장기 기억 후보를 추출해 `memories` 테이블에
저장할 수 있는 구조를 추가하는 것입니다.

## 추가·수정한 파일

- [backend/app/services/memory_extraction_service.py](../app/services/memory_extraction_service.py)
  - LLM에게 JSON 형식의 memory 후보를 요청합니다.
  - JSON 파싱, 중요도 보정, 최대 개수 제한을 처리합니다.
  - 추출된 후보를 현재 캐릭터 범위 memory로 저장합니다.

- [backend/app/services/chat_service.py](../app/services/chat_service.py)
  - 일반 채팅과 스트리밍 채팅이 정상 완료된 뒤 자동 추출을 선택적으로 실행합니다.

- [backend/app/core/config.py](../app/core/config.py)
  - `AUTO_MEMORY_ENABLED`
  - `AUTO_MEMORY_MAX_ITEMS`

- [backend/tests/test_memory_extraction_service.py](../tests/test_memory_extraction_service.py)
  - JSON 파싱과 후보 개수 제한을 검증합니다.

## 기본값은 꺼져 있음

자동 기억 추출은 LLM 비용이 추가로 발생하고, 저장 정책도 서비스 성격에 따라 달라질 수
있습니다. 그래서 기본값은 꺼져 있습니다.

```text
AUTO_MEMORY_ENABLED=false
AUTO_MEMORY_MAX_ITEMS=3
```

켜면 채팅 응답 저장 후 다음 흐름이 추가됩니다.

```text
assistant 메시지 저장
  → 한 턴의 user/assistant 내용으로 기억 후보 추출
  → JSON 파싱
  → character_id 범위 memory 저장
```

## 실패 격리

자동 기억 추출이 실패해도 채팅 응답 자체는 실패하지 않습니다. 기억 추출은 “부가 기능”이고,
사용자가 이미 받은 assistant 답변 저장이 더 중요한 핵심 경로이기 때문입니다.

## 한계

- 중복 기억 제거는 아직 없습니다.
- 사용자 승인 UX 없이 자동 저장합니다.
- 추출 prompt는 아직 단순합니다.
- embedding 기반 관련성 검색과 연결되지는 않았습니다.

다음 단계에서는 pgvector/embedding 검색을 붙일 수 있도록 DB와 provider 경계를 준비합니다.
