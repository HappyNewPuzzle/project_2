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
Character 1 ─── N Conversation
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
