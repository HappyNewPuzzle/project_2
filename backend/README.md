# AI Character Chat Backend

## 현재 단계

4단계까지 구현되어 있습니다. 캐릭터별 성격·말투·시스템 프롬프트를 설정하고,
최근 대화 기록을 포함해 일반 JSON 또는 SSE 스트리밍 채팅을 생성합니다.

```text
backend/
├─ app/
│  ├─ main.py
│  ├─ api/routes/
│  │  ├─ chat.py
│  │  └─ characters.py
│  ├─ core/config.py
│  ├─ db/
│  │  ├─ base.py
│  │  ├─ models.py
│  │  └─ session.py
│  ├─ repositories/
│  │  ├─ character_repository.py
│  │  ├─ conversation_repository.py
│  │  └─ message_repository.py
│  ├─ schemas/
│  │  ├─ character.py
│  │  └─ chat.py
│  └─ services/
│     ├─ character_service.py
│     ├─ chat_service.py
│     └─ llm_service.py
├─ alembic/versions/
├─ alembic.ini
├─ tests/
│  ├─ test_characters.py
│  ├─ test_chat.py
│  └─ test_chat_service.py
├─ requirements.txt
└─ .env.example
```

책임은 다음처럼 분리됩니다.

- 라우터: HTTP 입출력, SSE 형식, 상태 코드
- `CharacterService`: 캐릭터 CRUD와 캐릭터 프롬프트 구성
- `ChatService`: 메시지 저장, 최근 문맥 조회, LLM 호출 순서 조정
- repository: SQLAlchemy 조회 및 추가
- `LLMProvider`: `generate()`와 `stream()` provider 경계

현재 DB 모델은 `characters`, `conversations`, `messages`를 포함합니다.
사용자와 소유권 관계는 인증을 구현하는 5단계에서 추가합니다.

## 실행

PowerShell에서:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

PostgreSQL에 데이터베이스를 생성합니다.

```powershell
psql -U postgres -c "CREATE DATABASE character_chat;"
```

`.env`의 `DATABASE_URL`과 `OPENAI_API_KEY`를 환경에 맞게 수정하고 migration을
적용합니다.

```powershell
alembic upgrade head
```

서버를 시작합니다.

```powershell
uvicorn app.main:app --reload
```

API 문서는 `http://127.0.0.1:8000/docs`에서 확인할 수 있습니다.

## 테스트

캐릭터를 생성합니다.

```powershell
$character = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/characters `
  -ContentType "application/json" `
  -Body '{
    "name": "루나",
    "description": "달빛 도서관의 사서",
    "personality": "차분하고 호기심이 많다",
    "speaking_style": "부드럽고 간결하게 말한다",
    "system_prompt": "가끔 달과 책에 관한 비유를 사용한다"
  }'
```

캐릭터 목록과 상세 정보는 다음 API로 조회합니다.

```text
GET /characters
GET /characters/{character_id}
PATCH /characters/{character_id}
DELETE /characters/{character_id}
```

생성한 캐릭터와 채팅합니다.

```powershell
$body = @{
  message = "안녕! 너를 소개해줘"
  character_id = $character.id
} | ConvertTo-Json

$chat = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body $body
```

첫 요청의 응답에는 새 대화 ID가 포함됩니다.

```json
{
  "conversation_id": "5f21f144-c21a-4879-b2aa-cad1ba30c845",
  "character_id": "d2135518-40bb-43e9-921c-1d77ea35a732",
  "reply": "안녕하세요!"
}
```

문맥을 이어갈 요청은 같은 대화 ID를 전달합니다. 대화에 연결된 캐릭터는 고정되므로
후속 요청에서는 `character_id`를 생략할 수 있습니다.

```json
{
  "message": "아까 이야기한 내용을 기억해?",
  "conversation_id": "5f21f144-c21a-4879-b2aa-cad1ba30c845"
}
```

`CHAT_HISTORY_LIMIT`에 지정한 최근 메시지 수만 LLM에 전달됩니다. 기본값은 20입니다.
첫 요청에서 캐릭터를 생략하면 migration이 생성한 기본 `Assistant` 캐릭터를 사용합니다.

저장 결과는 PostgreSQL에서 확인할 수 있습니다.

```powershell
psql -U postgres -d character_chat `
  -c "SELECT conversation_id, role, content, created_at FROM messages ORDER BY created_at;"
```

스트리밍 응답은 `curl.exe -N`으로 버퍼링 없이 확인할 수 있습니다.

```powershell
curl.exe -N `
  -X POST http://127.0.0.1:8000/chat/stream `
  -H "Content-Type: application/json" `
  -d '{"message":"스트리밍으로 자기소개해줘"}'
```

응답 형식:

```text
event: conversation
data: {"conversation_id": "5f21f144-c21a-4879-b2aa-cad1ba30c845", "character_id": "d2135518-40bb-43e9-921c-1d77ea35a732"}

event: token
data: {"delta": "안녕"}

event: token
data: {"delta": "!"}

event: done
data: {}
```

스트리밍 도중 오류가 발생하면 HTTP 상태 코드는 이미 전송된 뒤이므로 `event: error`로
오류를 알립니다. 클라이언트는 `conversation`, `token`, `done`, `error` 이벤트를 각각
처리해야 합니다.

API 키 없이 자동 테스트:

```powershell
pytest
```

테스트에서는 FastAPI 의존성을 가짜 `ChatService`로 바꾸므로 API 비용과 DB 연결이
발생하지 않습니다.

## 전체 로드맵

1. 최소 채팅: 단일 메시지 요청, LLM 호출, JSON 응답 (완료)
2. 스트리밍: provider의 stream 인터페이스와 `StreamingResponse`/SSE 추가 (완료)
3. 영속화: PostgreSQL, SQLAlchemy async, Alembic, 대화·메시지 모델 (완료)
4. 캐릭터: 캐릭터 CRUD, 시스템 프롬프트, 최근 대화 조립 (완료)
5. 인증: 비밀번호 해시, JWT access token, 사용자별 리소스 권한
6. 장기 기억: 최근 N개 메시지, 요약 및 memory 테이블, 이후 pgvector 검색
7. 운영 준비: Docker, 구조화 로그, 관측성, rate limit, 테스트와 배포 자동화

## 저장 동작

1. 새 대화방을 만들거나 전달받은 `conversation_id`를 확인합니다.
2. 대화에 연결된 캐릭터를 조회합니다.
3. 사용자 메시지를 먼저 커밋합니다.
4. 최근 메시지 N개와 캐릭터 instructions를 조립합니다.
5. LLM 응답을 생성합니다.
6. 생성이 완료되면 AI 메시지를 별도 커밋합니다.

LLM 호출이 실패해도 사용자 메시지는 남습니다. 스트리밍 도중 연결이 끊기면 완성되지
않은 AI 메시지는 저장하지 않습니다.

## 다음 단계에서 개선할 점

- `users` 테이블과 비밀번호 해시
- 회원가입 및 로그인 API
- JWT access token 검증
- 캐릭터와 대화방 소유권 및 접근 제어
