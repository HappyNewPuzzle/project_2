# 1단계: 최소 채팅 API

## 목표

DB나 로그인 없이 `POST /chat`으로 메시지를 보내고 LLM의 완성 답변을 JSON으로
받는 것이 첫 목표였습니다.

## 당시 필요한 최소 책임

- `main.py`: FastAPI 앱 생성
- `schemas/chat.py`: 요청과 응답 JSON 검증
- `api/routes/chat.py`: HTTP 엔드포인트
- `services/llm_service.py`: OpenAI 호출
- `.env.example`: API 키와 모델 설정 예시

## 핵심 설계

LLM 코드를 라우터에 직접 넣지 않고 `LLMProvider` 뒤에 배치했습니다. 덕분에 테스트는
가짜 provider를 사용할 수 있고, 나중에 다른 회사의 API도 같은 인터페이스로
교체할 수 있습니다.

설정 객체는 시작 시 API 키가 없어도 생성됩니다. 따라서 `/docs`는 열 수 있고,
실제 채팅 요청에서만 `LLMConfigurationError`가 발생합니다.

## 요청과 응답의 기본 형태

```json
{ "message": "안녕" }
```

```json
{ "reply": "안녕하세요!" }
```

현재 코드는 이후 단계 기능 때문에 ID도 함께 반환하지만, LLM 호출의 기본 흐름은
여전히 이 단계의 구조를 유지합니다.

## 직접 확인할 코드

1. `app/main.py`에서 라우터가 등록되는 부분
2. `app/schemas/chat.py`의 메시지 길이 검증
3. `app/services/llm_service.py`의 `LLMProvider`
4. `app/api/routes/chat.py`의 일반 `chat()` 함수

## 다음 단계가 필요했던 이유

완성 답변을 기다리는 동안 사용자는 화면이 멈춘 것처럼 느낍니다. 이를 해결하기 위해
2단계에서 생성 중인 텍스트를 바로 전달하는 스트리밍을 추가했습니다.
