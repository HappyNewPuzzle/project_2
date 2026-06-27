# 2단계: SSE 스트리밍

## 목표

LLM이 답변 전체를 완성할 때까지 기다리지 않고 생성된 텍스트 조각을 즉시
클라이언트에 전달합니다.

## SSE 형식

```text
event: token
data: {"delta": "안녕"}

event: done
data: {}
```

각 이벤트는 빈 줄로 끝납니다. `conversation`, `token`, `done`, `error`를 분리해
프론트엔드가 로딩 상태와 오류를 명확하게 처리할 수 있습니다.

## 처리 흐름

```text
POST /chat/stream
  → StreamingResponse
  → event_stream() 비동기 생성기
  → LLMProvider.stream()
  → response.output_text.delta만 추출
  → token SSE 전송
  → 정상 완료 시 done SSE
```

HTTP 헤더가 전송된 후에는 상태 코드를 500으로 바꿀 수 없습니다. 그래서 스트리밍
도중 발생한 오류는 `event: error`라는 인밴드 메시지로 전달합니다.

## 자원 정리

`aclosing()`과 provider의 `finally`가 두 단계로 스트림을 닫습니다. 브라우저가
연결을 끊으면 FastAPI 생성기뿐 아니라 OpenAI upstream HTTP 연결도 종료할 수 있어
불필요한 생성 비용을 줄입니다.

`X-Accel-Buffering: no`는 Nginx 같은 프록시가 텍스트를 모아 두지 않도록 요청합니다.

## 직접 확인할 코드

1. `app/api/routes/chat.py`의 `_sse()`
2. 같은 파일의 `stream_chat()`과 `event_stream()`
3. `app/services/llm_service.py`의 `stream()`
4. `tests/test_chat.py`의 SSE 이벤트 순서 검증

## 다음 단계가 필요했던 이유

서버를 재시작하거나 다음 요청을 보내면 이전 대화가 사라졌습니다. 3단계에서는
대화와 메시지를 PostgreSQL에 영구 저장했습니다.
