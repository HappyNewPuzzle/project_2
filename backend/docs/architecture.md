# 전체 아키텍처

## 요청 흐름

일반 채팅 요청은 다음 순서로 처리됩니다.

```text
POST /chat
  → Bearer JWT 검증
  → 현재 사용자 DB 조회
  → ChatRequest 검증
  → ChatService.start_turn()
      → 캐릭터와 대화방 조회
      → 사용자 메시지 저장/commit
      → 전역/캐릭터별 장기 기억 조회
      → 최근 메시지 N개 조회
      → 캐릭터 instructions 조립
  → LLMProvider.generate()
  → AI 메시지 저장/commit
  → ChatResponse
```

스트리밍도 준비 과정은 같지만 `generate()` 대신 `stream()`을 사용합니다. 텍스트
조각은 즉시 클라이언트에 보내고, 정상 완료된 전체 답변만 DB에 저장합니다.

## 계층을 나눈 이유

라우터에서 SQL과 OpenAI 호출을 모두 수행하면 짧아 보이지만 다음 문제가 생깁니다.

- HTTP 없이 비즈니스 로직만 테스트하기 어렵습니다.
- 다른 LLM provider로 바꿀 때 모든 라우터를 수정해야 합니다.
- DB 저장 시점과 외부 API 실패 시점을 통제하기 어렵습니다.
- 기능이 늘수록 하나의 파일이 지나치게 커집니다.

현재 구조에서는 각 계층이 바로 아래 계층만 알고 있습니다.

```text
Router → Service → Repository → SQLAlchemy
                 ↘ LLMProvider → OpenAI SDK
```

repository는 commit하지 않습니다. 여러 DB 작업을 하나의 트랜잭션으로 묶을지
결정하는 책임은 유스케이스 전체를 아는 service에 있기 때문입니다.

## 오류 변환

오류도 계층 경계를 따라 변환됩니다.

```text
OpenAIError → LLMServiceError → HTTP 502 또는 SSE error
SQLAlchemyError → PersistenceError → HTTP 503 또는 SSE error
도메인 오류 → CharacterNotFoundError 등 → HTTP 404/409
```

외부 SDK의 세부 예외를 HTTP 응답에 직접 노출하지 않아 보안과 교체 가능성을 지킵니다.

## 데이터 관계

```text
User 1 ─── N Character
User 1 ─── N Conversation 1 ─── N Message
User 1 ─── N Memory
Character 1 ─── N Conversation
Character 1 ─── N Memory (선택 관계)
```

- owner가 없는 기본 캐릭터는 모든 로그인 사용자가 읽을 수 있습니다.
- 사용자는 자신이 만든 캐릭터만 수정·삭제할 수 있습니다.
- 사용자는 자신의 대화방만 이어 갈 수 있습니다.
- 캐릭터가 사용 중이면 삭제할 수 없습니다.
- 대화방을 삭제하면 소속 메시지는 함께 삭제됩니다.
- 하나의 대화방은 시작할 때 선택한 캐릭터를 계속 사용합니다.

## 인증 흐름

```text
회원가입 → Argon2 hash만 저장
로그인 → 비밀번호 verify → sub=user UUID인 JWT 발급
보호 API → Bearer JWT 서명/만료 검증 → 현재 활성 사용자 조회
```

JWT payload는 암호화되지 않으므로 비밀번호나 민감 정보를 넣지 않습니다. 서버는
`sub`의 UUID로 DB 사용자를 다시 조회해 비활성화와 삭제 상태까지 확인합니다.

## 장기 기억과 최근 대화

최근 대화는 실제 `user`/`assistant` 발화 순서를 보존합니다. 장기 기억은 중요도와
활성 상태로 선택하며, 캐릭터 규칙보다 낮은 `user` 역할의 배경 문맥 메시지로 최근
대화 앞에 추가합니다.

```text
instructions: 서비스 규칙 + 캐릭터 규칙
input:
  user: 저장된 장기 기억 배경
  user/assistant: 최근 대화 N개
```

사용자가 작성한 기억을 `instructions`에 넣지 않는 이유는 사용자 데이터를
애플리케이션 개발자 규칙과 같은 높은 권한으로 승격하지 않기 위해서입니다.

## 운영 요청 경계

```text
Client
  → RequestContextMiddleware
      → X-Request-ID 생성/전파
      → 처리 시간과 상태 코드 JSON 로그
  → RateLimit Dependency
  → Authentication Dependency
  → Route / Service
```

`/health/live`는 DB 장애와 무관하게 프로세스 생존 여부를 확인합니다.
`/health/ready`는 PostgreSQL `SELECT 1`까지 확인해 트래픽을 받을 준비가 됐는지
판단합니다.

Compose 시작 순서는 다음과 같습니다.

```text
PostgreSQL 시작
  → pg_isready healthcheck 통과
  → API container 시작
  → alembic upgrade head
  → uvicorn 시작
```

## CI 검증 경계

GitHub Actions는 운영 배포 대신 기본 품질 검증만 담당합니다.

```text
push 또는 pull request
  → Python 3.12 설치
  → requirements.txt 설치
  → pytest -q
  → PostgreSQL service container 시작
  → alembic upgrade head
  → 사용자 흐름 통합 테스트
  → FastAPI HTTP 통합 테스트
  → docker build
```

현재 CI는 실제 외부 LLM이나 운영 DB에 접속하지 않습니다. 테스트는 provider와 repository
경계를 가짜 객체로 바꾸어 빠르게 실행합니다. migration job은 GitHub Actions의 임시
PostgreSQL service container에만 접속해 `alembic upgrade head`를 검증한 뒤, 같은 DB에서
회원가입·로그인·캐릭터·기억·채팅 저장 흐름을 확인합니다. 일부 통합 테스트는
`httpx.ASGITransport`로 실제 FastAPI 라우터와 JWT 인증까지 통과합니다. Docker build는
마지막에 이미지가 정상적으로 만들어지는지 확인합니다.
