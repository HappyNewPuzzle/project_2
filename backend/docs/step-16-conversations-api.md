# 16단계: 대화방 목록과 메시지 조회 API

이번 단계의 목표는 저장된 대화를 다시 열 수 있는 백엔드 API를 추가하는 것입니다.
지금까지는 채팅을 저장했지만, 클라이언트가 과거 대화 목록을 조회하는 API가 없었습니다.

## 추가·수정한 파일

- [backend/app/api/routes/conversations.py](../app/api/routes/conversations.py)
  - `GET /conversations`
  - `GET /conversations/{conversation_id}/messages`
  - `DELETE /conversations/{conversation_id}`

- [backend/app/services/conversation_service.py](../app/services/conversation_service.py)
  - 현재 사용자 소유 대화방만 조회/삭제합니다.

- [backend/app/schemas/conversation.py](../app/schemas/conversation.py)
  - 대화방 응답과 메시지 응답 스키마를 분리했습니다.

- [backend/tests/test_conversations.py](../tests/test_conversations.py)
  - 라우터 계약 테스트를 추가했습니다.

## 왜 필요한가?

실제 채팅 서비스에서는 사용자가 과거 대화를 다시 열 수 있어야 합니다.

```text
대화 저장
  → 대화방 목록 조회
  → 특정 대화방 메시지 조회
  → 이어서 채팅
```

이 API가 있어야 프론트엔드에서 “이전 대화 목록”을 만들 수 있습니다.

## 권한 규칙

대화방은 항상 한 사용자에게 속합니다.

- 사용자는 자신의 대화방 목록만 볼 수 있습니다.
- 사용자는 자신의 대화방 메시지만 볼 수 있습니다.
- 사용자는 자신의 대화방만 삭제할 수 있습니다.
- 다른 사용자의 `conversation_id`를 알아도 404로 처리합니다.

## 이번 단계의 한계

- 대화방 제목 자동 생성은 아직 없습니다.
- 페이지네이션은 offset/limit 방식입니다.
- 메시지 검색 기능은 아직 없습니다.

다음 단계에서는 이 API를 최소 프론트엔드에 연결해 과거 대화를 다시 열 수 있게 합니다.
