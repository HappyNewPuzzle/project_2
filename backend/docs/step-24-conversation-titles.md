# 24단계: 대화방 제목 자동 생성

이번 단계의 목표는 UUID만 보이던 대화방 목록에 사용자가 이해할 수 있는 짧은 제목을
표시하는 것입니다. 새 대화는 첫 사용자 메시지에서 제목을 만들고, 기존 대화는
Alembic migration이 저장된 첫 메시지로 제목을 보완합니다.

## 주요 변경 파일

- [app/services/chat_service.py](../app/services/chat_service.py)
  - `build_conversation_title()`을 추가했습니다.
  - 새 대화를 만들 때 첫 사용자 메시지를 제목으로 전달합니다.

- [app/repositories/conversation_repository.py](../app/repositories/conversation_repository.py)
  - 대화방 생성 시 `title`도 함께 저장합니다.

- [app/db/models.py](../app/db/models.py)
  - `Conversation.title`을 최대 100자의 필수 컬럼으로 선언했습니다.

- [alembic/versions/20260727_0007_add_conversation_titles.py](../alembic/versions/20260727_0007_add_conversation_titles.py)
  - 제목 컬럼을 추가합니다.
  - 기존 대화의 첫 사용자 메시지로 제목을 채웁니다.

- [app/schemas/conversation.py](../app/schemas/conversation.py)
  - 대화방 목록 응답에 `title`을 추가했습니다.

- [frontend/index.html](../../frontend/index.html)
  - 대화방 UUID 대신 제목을 목록에 표시합니다.

## 제목 생성 규칙

제목을 만들기 위해 LLM을 추가 호출하지 않습니다. 첫 메시지만으로 다음 규칙을
적용합니다.

1. 앞뒤 공백을 제거합니다.
2. 줄바꿈과 연속 공백을 한 칸으로 합칩니다.
3. 50자 이하면 그대로 사용합니다.
4. 50자를 넘으면 마지막 글자를 `…`로 바꿉니다.
5. 비어 있다면 `새 대화`를 사용합니다.

```text
입력:
"  안녕
  오늘은 별 이야기야  "

제목:
"안녕 오늘은 별 이야기야"
```

LLM 제목 생성은 더 자연스러울 수 있지만 새 대화마다 추가 비용과 지연이 생기고, 제목
API 실패가 채팅 생성에 영향을 줄 수 있습니다. 현재 단계에서는 결정적이고 실패하지
않는 제목을 사용합니다. 나중에 비동기 background job으로 LLM 제목을 덮어쓰는 구조로
확장할 수 있습니다.

## 기존 데이터 migration

이미 저장된 대화에는 제목이 없으므로 다음 순서로 안전하게 변경합니다.

```text
nullable title 컬럼 추가
  → 대화별 첫 user 메시지 조회
  → 공백 정리 후 title 저장
  → 메시지가 없으면 "새 대화"
  → title NOT NULL 적용
```

처음부터 `NOT NULL` 컬럼을 추가하면 기존 행 때문에 migration이 실패할 수 있습니다.
데이터를 먼저 채운 뒤 제약을 강화하는 이유입니다.

## API 응답

```http
GET /conversations
Authorization: Bearer {access_token}
```

```json
[
  {
    "id": "77777777-7777-7777-7777-777777777777",
    "user_id": "88888888-8888-8888-8888-888888888888",
    "character_id": "99999999-9999-9999-9999-999999999999",
    "title": "오늘은 별 이야기야",
    "created_at": "2026-07-27T10:00:00Z",
    "updated_at": "2026-07-27T10:01:00Z"
  }
]
```

프론트엔드는 제목이 사용자 메시지에서 만들어진 값이라는 점을 고려해 `innerHTML`에
넣지 않고 `textContent`로 표시합니다. 따라서 제목에 HTML 태그가 들어 있어도 코드로
실행되지 않고 일반 문자열로 보입니다.

## 테스트

```powershell
cd backend
pytest -q
```

실제 DB 검증에서는 다음 항목을 확인했습니다.

- 23단계 DB에 제목 없는 기존 대화 생성
- 24단계 migration 적용
- 첫 메시지 `"   첫   질문   둘째 줄   "`이 `"첫 질문 둘째 줄"`로 변환
- 새 HTTP 채팅의 제목이 첫 메시지와 동일
- migration downgrade 후 재적용 성공

## 다음 단계

25단계에서는 단일 HTML 파일의 프론트엔드를 React 또는 Next.js 구조로 분리해
컴포넌트, API client, 인증 상태, 대화 상태를 체계적으로 관리합니다.
