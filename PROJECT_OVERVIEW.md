# AI 캐릭터 채팅 서비스 프로젝트 설명서

이 문서는 현재 프로젝트가 어떤 서비스이고, 어디까지 구현되었으며, 앞으로 어떤 방향으로
확장할 수 있는지 한 번에 이해하기 위한 종합 설명서입니다.

## 프로젝트 목표

이 프로젝트의 목표는 사용자가 웹사이트에서 AI 캐릭터와 대화할 수 있는 서비스를 만드는
것입니다.

단순 예제 코드가 아니라 실제 서비스로 확장할 수 있도록 다음 기준을 지키며 단계적으로
구현했습니다.

- FastAPI 기반 백엔드
- 회원가입 / 로그인
- JWT 인증
- AI 캐릭터 생성과 관리
- 캐릭터별 프롬프트
- 사용자별 대화 저장
- 스트리밍 응답
- 장기 기억
- PostgreSQL 저장
- Redis 기반 rate limit 준비
- Docker Compose 실행
- GitHub Actions CI
- 최소 프론트엔드
- embedding / pgvector 확장 준비

## 현재 구현 상태

현재는 23단계까지 구현되어 있습니다.

```text
1단계  최소 채팅 API
2단계  SSE 스트리밍
3단계  PostgreSQL 저장
4단계  캐릭터 프롬프트
5단계  JWT 인증
6단계  장기 기억
7단계  Docker / health check / 로그 / rate limit
8단계  GitHub Actions CI
9단계  CI에서 Alembic migration 검증
10단계 실제 사용자 흐름 통합 테스트
11단계 사용자 권한 격리 통합 테스트
12단계 스트리밍 저장 정책 통합 테스트
13단계 FastAPI HTTP 통합 테스트
14단계 최소 정적 프론트엔드
15단계 배포 전 환경 점검
16단계 대화방 목록 / 메시지 조회 API
17단계 프론트엔드 대화 목록 연결
18단계 Redis 기반 rate limit 준비
19단계 장기 기억 자동 추출 구조
20단계 embedding / pgvector 검색 준비
21단계 실제 OpenAI embedding provider
22단계 pgvector 저장 구조와 HNSW index
23단계 장기 기억 자동 embedding과 의미 검색 API
```

## 전체 폴더 구조

```text
project2/
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ api/
│  │  │  └─ routes/
│  │  │     ├─ auth.py
│  │  │     ├─ chat.py
│  │  │     ├─ characters.py
│  │  │     ├─ conversations.py
│  │  │     ├─ health.py
│  │  │     └─ memories.py
│  │  ├─ core/
│  │  │  ├─ config.py
│  │  │  ├─ logging.py
│  │  │  ├─ middleware.py
│  │  │  ├─ rate_limit.py
│  │  │  └─ security.py
│  │  ├─ db/
│  │  │  ├─ base.py
│  │  │  ├─ models.py
│  │  │  └─ session.py
│  │  ├─ repositories/
│  │  ├─ schemas/
│  │  └─ services/
│  ├─ alembic/
│  │  └─ versions/
│  ├─ docs/
│  ├─ scripts/
│  │  └─ check_deploy_env.py
│  ├─ tests/
│  ├─ Dockerfile
│  ├─ compose.yaml
│  ├─ requirements.txt
│  └─ .env.example
├─ frontend/
│  ├─ index.html
│  └─ README.md
├─ .github/
│  └─ workflows/
│     └─ backend-ci.yml
└─ PROJECT_OVERVIEW.md
```

## 백엔드 아키텍처

백엔드는 책임을 계층별로 나눠 구현했습니다.

```text
Router
  → Service
      → Repository
          → SQLAlchemy / PostgreSQL
      → LLMProvider
          → OpenAI 또는 다른 LLM
```

각 계층의 역할은 다음과 같습니다.

- `api/routes`
  - HTTP 요청과 응답을 담당합니다.
  - 상태 코드, SSE 이벤트, Pydantic 요청 검증을 처리합니다.

- `services`
  - 실제 비즈니스 흐름을 담당합니다.
  - 예: 회원가입, 채팅 저장, 캐릭터 프롬프트 조립, 기억 추출

- `repositories`
  - SQLAlchemy 쿼리와 DB 접근을 담당합니다.
  - 서비스 계층이 SQL 세부사항을 몰라도 되게 합니다.

- `schemas`
  - API 요청/응답 데이터 형식을 정의합니다.

- `db`
  - SQLAlchemy 모델과 세션 생성을 담당합니다.

- `core`
  - 설정, 보안, rate limit, 로그, middleware 같은 공통 기능을 둡니다.

## 주요 기능

### 인증

구현된 API:

```text
POST /auth/register
POST /auth/login
GET  /auth/me
```

특징:

- Argon2 기반 비밀번호 해시
- JWT access token 발급
- Bearer token 인증
- 사용자별 데이터 격리

### 캐릭터

구현된 API:

```text
POST   /characters
GET    /characters
GET    /characters/{character_id}
PATCH  /characters/{character_id}
DELETE /characters/{character_id}
```

캐릭터는 다음 정보를 가집니다.

- 이름
- 설명
- 성격
- 말투
- 시스템 프롬프트
- 소유 사용자

채팅 시 캐릭터 정보는 LLM instructions로 조립됩니다.

### 채팅

구현된 API:

```text
POST /chat
POST /chat/stream
```

특징:

- 일반 JSON 응답
- SSE 스트리밍 응답
- 사용자 메시지 우선 저장
- AI 응답 완료 후 저장
- 스트리밍 실패 시 불완전한 assistant 메시지는 저장하지 않음
- 최근 대화 N개만 LLM에 전달
- 캐릭터별 프롬프트 적용
- 장기 기억 문맥 주입

### 대화방

구현된 API:

```text
GET    /conversations
GET    /conversations/{conversation_id}/messages
DELETE /conversations/{conversation_id}
```

특징:

- 사용자별 대화방 목록 조회
- 특정 대화방 메시지 조회
- 대화방 삭제 시 메시지도 함께 삭제
- 다른 사용자의 대화방 접근 차단

### 장기 기억

구현된 API:

```text
POST   /memories
GET    /memories
GET    /memories/{memory_id}
PATCH  /memories/{memory_id}
DELETE /memories/{memory_id}
```

특징:

- 사용자별 memory 저장
- 캐릭터별 memory 범위 지정 가능
- 중요도 `1~5`
- 활성/비활성 상태
- 채팅 시 중요도순으로 일부 기억만 프롬프트에 포함

### 장기 기억 자동 추출

설정:

```text
AUTO_MEMORY_ENABLED=false
AUTO_MEMORY_MAX_ITEMS=3
```

기본값은 꺼져 있습니다.

켜면 채팅 완료 후 다음 흐름이 추가됩니다.

```text
사용자 메시지 + AI 답변
  → LLM으로 memory 후보 JSON 추출
  → 파싱 및 중요도 보정
  → memories 테이블 저장
```

기억 추출 실패는 채팅 응답 실패로 이어지지 않도록 분리했습니다.

### embedding / pgvector 저장

현재 구현:

- `memory_embeddings` 테이블
- `EmbeddingProvider` 인터페이스
- 개발용 `HashingEmbeddingProvider`
- 실제 `OpenAIEmbeddingProvider`
- `pgvector/pgvector` PostgreSQL 17 이미지
- `embedding VECTOR(1536)` 컬럼
- cosine 거리용 HNSW index
- JSON과 pgvector 컬럼 병행 저장

```text
EmbeddingProvider
  → 1536차원 vector 생성
  → memory_embeddings.vector_json (전환기 호환)
  → memory_embeddings.embedding VECTOR(1536)
  → HNSW cosine index
```

기억 생성·내용 수정·자동 추출 시 embedding을 함께 저장합니다. 검색 API는 현재 사용자,
활성 상태, 전역/캐릭터 범위를 SQL에서 제한하고 pgvector cosine distance로 정렬합니다.
기존 미색인 기억은 제한된 batch 재색인 API로 보완할 수 있습니다.

### Rate limit

현재 구조:

```text
REDIS_URL 있음
  → RedisRateLimiter

REDIS_URL 없음
  → InMemoryRateLimiter
```

제한 대상:

- 회원가입 / 로그인: IP 기준
- 채팅 / 스트리밍: 사용자 UUID 기준

초과 시:

```text
HTTP 429
Retry-After 헤더
```

## 데이터베이스 테이블

현재 주요 테이블:

```text
users
characters
conversations
messages
memories
memory_embeddings
```

관계:

```text
User 1 ─── N Character
User 1 ─── N Conversation
User 1 ─── N Memory

Character 1 ─── N Conversation
Character 1 ─── N Memory

Conversation 1 ─── N Message
Memory 1 ─── 0..1 MemoryEmbedding
```

## 프론트엔드

프론트엔드는 현재 `frontend/index.html` 하나로 구성된 최소 정적 UI입니다.

지원 기능:

- API Base URL 입력
- 회원가입
- 로그인
- 캐릭터 생성
- 기억 저장
- 스트리밍 채팅
- 대화 목록 새로고침
- 이전 대화 열기
- 현재 대화 삭제

실행:

```powershell
cd frontend
python -m http.server 5173
```

브라우저:

```text
http://127.0.0.1:5173
```

운영용 프론트엔드는 아직 아닙니다. React/Next.js 같은 구조화된 프론트엔드는 다음 확장
후보입니다.

## Docker Compose 실행

백엔드 실행:

```powershell
cd backend
Copy-Item .env.example .env
docker compose up --build
```

Compose 구성:

- `api`
- `db` PostgreSQL
- `redis`

API 컨테이너는 시작 시 다음을 수행합니다.

```text
alembic upgrade head
uvicorn app.main:app
```

주의:

운영 환경에서 여러 API replica를 동시에 띄울 경우 migration은 컨테이너 entrypoint가 아니라
별도의 1회성 release job으로 분리하는 것이 안전합니다.

## 테스트와 CI

현재 테스트 범위:

- 라우터 계약 테스트
- 서비스 계층 테스트
- 보안 유틸리티 테스트
- rate limit 테스트
- logging / health check 테스트
- PostgreSQL 통합 테스트
- 사용자 흐름 통합 테스트
- 사용자 권한 격리 테스트
- 스트리밍 저장 정책 테스트
- FastAPI HTTP 통합 테스트
- embedding 준비 테스트

로컬 빠른 테스트:

```powershell
cd backend
pytest -q
```

DB 통합 테스트는 다음 환경변수가 있을 때만 실행됩니다.

```text
RUN_DB_INTEGRATION=1
```

GitHub Actions에서는 다음을 자동 검증합니다.

```text
pytest
alembic upgrade head
PostgreSQL 통합 테스트
Docker build
배포 환경 점검 스크립트
```

## 배포 전 점검

배포 전에 다음 스크립트를 실행할 수 있습니다.

```powershell
cd backend
python scripts/check_deploy_env.py --production
```

점검 항목:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `OPENAI_API_KEY`
- `CORS_ALLOWED_ORIGINS`
- `LOG_JSON`

개발 환경에서는 다음처럼 완화 모드로 실행할 수 있습니다.

```powershell
python scripts/check_deploy_env.py --allow-missing-openai --allow-dev-secret
```

## 중요한 설계 원칙

이 프로젝트는 다음 원칙으로 구성되어 있습니다.

1. 처음부터 모든 것을 복잡하게 만들지 않는다.
2. 기능별 책임을 파일과 계층으로 분리한다.
3. 라우터는 HTTP 변환만 담당한다.
4. 서비스는 유스케이스 흐름을 담당한다.
5. repository는 DB 접근만 담당한다.
6. LLM 호출은 provider 인터페이스 뒤에 둔다.
7. OpenAI 외 다른 LLM으로 교체 가능하게 만든다.
8. 스트리밍 실패와 저장 정책을 분리한다.
9. 사용자별 데이터 권한을 서비스 계층에서 검증한다.
10. Docker와 CI를 통해 반복 검증한다.

## 현재 한계

아직 구현되지 않았거나 후속 개선이 필요한 부분입니다.

- 운영용 프론트엔드 구조
- 대화방 제목 자동 생성
- 캐릭터 이미지 / 프로필 기능
- 중복 memory 제거
- 자동 memory 저장 전 사용자 승인 UI
- Redis 장애 시 fallback 정책
- 관리자 기능
- refresh token
- 이메일 인증
- 실제 클라우드 배포 workflow
- OpenTelemetry metrics / tracing

## 다음 추천 단계

다음에 이어서 진행한다면 추천 순서는 다음과 같습니다.

```text
21단계: 실제 OpenAI embedding provider 추가 (완료)
22단계: pgvector 지원 PostgreSQL 이미지 전환 (완료)
23단계: memory 검색 API 추가 (완료)
24단계: 대화방 제목 자동 생성
25단계: React 또는 Next.js 기반 프론트엔드 구조화
```

현재 상태는 “학습용 예제”를 넘어, 실제 서비스로 확장 가능한 백엔드 골격과 최소 UI,
운영 전 점검 체계까지 갖춘 상태입니다.
