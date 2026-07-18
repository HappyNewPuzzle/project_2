# AI Character Chat Backend

단계별 구현 이유와 코드 읽는 순서는 [학습 문서](docs/README.md)에서 확인할 수
있습니다. 전체 요청 흐름은 [아키텍처 문서](docs/architecture.md)에 정리했습니다.

## 현재 단계

19단계까지 구현되어 있습니다. Docker Compose로 API와 PostgreSQL을 함께 실행하고,
health check·구조화 로그·요청 ID·기본 rate limit을 제공합니다. 또한 GitHub Actions로
push/PR마다 pytest, PostgreSQL migration, 사용자 흐름 통합 테스트, Docker build를 자동
검증합니다. 브라우저에서 API를 손으로 확인할 수 있는 최소 정적 프론트엔드도 포함합니다.

```text
backend/
├─ app/
│  ├─ main.py
│  ├─ api/routes/
│  │  ├─ auth.py
│  │  ├─ chat.py
│  │  ├─ characters.py
│  │  ├─ conversations.py
│  │  └─ memories.py
│  ├─ core/
│  │  ├─ config.py
│  │  └─ security.py
│  ├─ db/
│  │  ├─ base.py
│  │  ├─ models.py
│  │  └─ session.py
│  ├─ repositories/
│  │  ├─ character_repository.py
│  │  ├─ conversation_repository.py
│  │  ├─ message_repository.py
│  │  ├─ memory_repository.py
│  │  └─ user_repository.py
│  ├─ schemas/
│  │  ├─ character.py
│  │  ├─ chat.py
│  │  ├─ memory.py
│  │  └─ user.py
│  └─ services/
│     ├─ auth_service.py
│     ├─ character_service.py
│     ├─ chat_service.py
│     ├─ llm_service.py
│     └─ memory_service.py
├─ alembic/versions/
├─ alembic.ini
├─ docker/entrypoint.sh
├─ scripts/
│  └─ check_deploy_env.py
├─ Dockerfile
├─ compose.yaml
├─ tests/
│  ├─ test_auth.py
│  ├─ test_api_flow_integration.py
│  ├─ test_characters.py
│  ├─ test_chat.py
│  ├─ test_chat_service.py
│  ├─ test_conversations.py
│  ├─ test_health.py
│  ├─ test_memories.py
│  ├─ test_rate_limit.py
│  ├─ test_security.py
│  ├─ test_streaming_persistence_integration.py
│  ├─ test_user_flow_integration.py
│  └─ test_user_isolation_integration.py
├─ requirements.txt
└─ .env.example

.github/
└─ workflows/
   └─ backend-ci.yml

frontend/
├─ index.html
└─ README.md
```

책임은 다음처럼 분리됩니다.

- 라우터: HTTP 입출력, SSE 형식, 상태 코드
- `AuthService`: 회원가입, Argon2 비밀번호 검증, JWT 발급
- `CharacterService`: 캐릭터 CRUD와 캐릭터 프롬프트 구성
- `ChatService`: 메시지 저장, 최근 문맥 조회, LLM 호출 순서 조정
- `MemoryService`: 사용자 장기 기억 CRUD와 캐릭터 범위 검증
- middleware: 요청 ID 전파와 구조화 접근 로그
- repository: SQLAlchemy 조회 및 추가
- `LLMProvider`: `generate()`와 `stream()` provider 경계
- GitHub Actions: push/PR 시 테스트, Alembic migration, Docker 빌드 자동 검증
- 통합 테스트: 실제 PostgreSQL 위에서 회원가입부터 채팅 저장까지 검증
- 권한 격리 테스트: 사용자별 캐릭터·기억·대화 접근 제한 검증
- 스트리밍 저장 테스트: 정상 완료된 assistant 메시지만 DB 저장
- HTTP 통합 테스트: FastAPI 라우터, JWT, DB 세션, health check 검증
- 최소 프론트엔드: 브라우저에서 로그인, 캐릭터 생성, 스트리밍 채팅 확인
- 배포 점검 스크립트: 운영 전 위험한 기본 환경값 확인
- 대화방 API: 저장된 대화 목록, 메시지 조회, 대화방 삭제
- 프론트엔드 대화 목록: 이전 대화 열기와 현재 대화 삭제
- Redis rate limit: 여러 API 프로세스가 공유할 수 있는 제한기 준비
- 자동 기억 추출: 채팅 완료 후 LLM 기반 memory 후보 저장 구조

현재 DB 모델은 `users`, `characters`, `conversations`, `messages`, `memories`를
포함합니다.

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

`.env`의 `DATABASE_URL`, `OPENAI_API_KEY`, `JWT_SECRET_KEY`를 환경에 맞게
수정하고 migration을 적용합니다. 운영 환경의 JWT secret에는 긴 무작위 값을
사용해야 합니다.

```powershell
alembic upgrade head
```

서버를 시작합니다.

```powershell
uvicorn app.main:app --reload
```

API 문서는 `http://127.0.0.1:8000/docs`에서 확인할 수 있습니다.

## Docker Compose 실행

프로젝트의 `backend` 디렉터리에서 실행합니다.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Compose는 PostgreSQL healthcheck가 통과한 뒤 API를 시작합니다. API entrypoint는
`alembic upgrade head` 성공 후 uvicorn을 실행합니다.

```powershell
docker compose ps
docker compose logs -f api
docker compose down
```

DB 데이터는 `postgres_data` named volume에 유지됩니다. 데이터까지 제거하려면
그 의미를 확인한 뒤 명시적으로 `docker compose down -v`를 사용해야 합니다.

단일 Compose 인스턴스에서는 entrypoint migration이 편리하지만, 여러 API replica를
동시에 배포하는 운영 환경에서는 migration을 별도의 1회성 release job으로 분리해야
합니다.

## Health check와 로그

```text
GET /health/live   프로세스가 HTTP를 처리할 수 있는지 확인
GET /health/ready  PostgreSQL SELECT 1까지 가능한지 확인
```

모든 응답에는 `X-Request-ID`가 포함됩니다. 요청 헤더에 같은 값을 보내면 그대로
전파하고, 없으면 서버가 UUID를 생성합니다. `LOG_JSON=true`일 때 로그는 timestamp,
level, logger, message, request_id, HTTP 처리 시간 등을 한 줄 JSON으로 출력합니다.

## Rate limit

- 회원가입/로그인: IP별 `AUTH_RATE_LIMIT_PER_MINUTE`
- 채팅/스트리밍: 사용자 UUID별 `CHAT_RATE_LIMIT_PER_MINUTE`
- 초과 응답: HTTP 429와 `Retry-After` 헤더

현재 제한기는 단일 프로세스 메모리에 저장됩니다. 여러 worker나 여러 컨테이너에서는
상태를 공유하지 않으므로 운영 확장 시 Redis 기반 제한기로 교체해야 합니다.

## 테스트

먼저 회원가입하고 로그인합니다.

```powershell
$email = "learner@example.com"
$password = "strong-password"

$user = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/auth/register `
  -ContentType "application/json" `
  -Body (@{ email = $email; password = $password } | ConvertTo-Json)

$token = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/auth/login `
  -ContentType "application/x-www-form-urlencoded" `
  -Body @{ username = $email; password = $password }

$headers = @{ Authorization = "Bearer $($token.access_token)" }
```

`/auth/login`은 OAuth2 표준 form의 `username` 필드에 이메일을 받습니다.

캐릭터를 생성합니다.

```powershell
$character = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/characters `
  -Headers $headers `
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

오래 유지할 사용자 정보를 기억으로 저장할 수 있습니다.

```powershell
$memory = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/memories `
  -Headers $headers `
  -ContentType "application/json" `
  -Body (@{
    content = "사용자는 천문학을 좋아한다"
    character_id = $character.id
    importance = 4
  } | ConvertTo-Json)
```

```text
GET    /memories
GET    /memories/{memory_id}
PATCH  /memories/{memory_id}
DELETE /memories/{memory_id}
```

`character_id`를 생략한 기억은 모든 캐릭터 대화에, 지정한 기억은 해당 캐릭터
대화에만 사용됩니다. 현재 단계에서는 기억을 명시적으로 관리하며 자동 추출은
후속 개선 사항입니다.

생성한 캐릭터와 채팅합니다.

```powershell
$body = @{
  message = "안녕! 너를 소개해줘"
  character_id = $character.id
} | ConvertTo-Json

$chat = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/chat `
  -Headers $headers `
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
`CHAT_MEMORY_LIMIT`은 중요도순 활성 기억의 최대 개수이며 기본값은 10입니다.
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
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" `
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

라우터 테스트에서는 FastAPI 의존성을 가짜 서비스로 바꾸므로 API 비용과 DB 연결이
발생하지 않습니다. 보안 유틸리티 테스트는 실제 Argon2 해시와 JWT 왕복을 확인합니다.

GitHub에 push하면 같은 테스트, PostgreSQL service container 기반 migration 검증,
사용자 흐름 통합 테스트, Docker build가 GitHub Actions에서도 자동으로 실행됩니다.
Actions 탭에서 `Backend CI` 워크플로 결과를 확인할 수 있습니다.

배포 전 환경 설정은 다음 명령으로 점검할 수 있습니다.

```powershell
python scripts/check_deploy_env.py --production
```

## 전체 로드맵

1. 최소 채팅: 단일 메시지 요청, LLM 호출, JSON 응답 (완료)
2. 스트리밍: provider의 stream 인터페이스와 `StreamingResponse`/SSE 추가 (완료)
3. 영속화: PostgreSQL, SQLAlchemy async, Alembic, 대화·메시지 모델 (완료)
4. 캐릭터: 캐릭터 CRUD, 시스템 프롬프트, 최근 대화 조립 (완료)
5. 인증: Argon2 비밀번호 해시, JWT, 사용자별 리소스 권한 (완료)
6. 장기 기억: memory CRUD, 중요도 조회, 캐릭터별 문맥 주입 (완료)
7. 운영 준비: Docker, health check, 구조화 로그, rate limit (완료)
8. CI 자동 검증: GitHub Actions, pytest, Docker build (완료)
9. Migration CI: PostgreSQL service container, Alembic upgrade 검증 (완료)
10. 통합 테스트: 실제 DB 기반 사용자 흐름 검증 (완료)
11. 권한 격리: 사용자별 캐릭터·기억·대화 접근 제한 검증 (완료)
12. 스트리밍 저장 정책: 성공/실패 스트림의 DB 기록 검증 (완료)
13. HTTP 통합 테스트: FastAPI 라우터와 실제 DB 연결 검증 (완료)
14. 최소 프론트엔드: 정적 HTML 기반 브라우저 채팅 UI (완료)
15. 배포 준비: 환경 설정 점검 스크립트와 체크리스트 (완료)
16. 대화방 API: 목록, 메시지 조회, 삭제 (완료)
17. 프론트엔드 대화 목록: 저장된 대화 열기와 삭제 (완료)
18. Redis rate limit: REDIS_URL 기반 분산 제한기 선택 (완료)
19. 자동 기억 추출: 채팅 완료 후 장기 기억 후보 저장 구조 (완료)

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

- Redis 기반 분산 rate limit
- CI에서 `/health/ready` 통합 테스트 자동 검증
- OpenTelemetry metrics와 tracing
- 장기 기억 자동 추출과 pgvector 검색
