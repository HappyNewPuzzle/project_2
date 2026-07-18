# 13단계: FastAPI HTTP 통합 테스트

이번 단계의 목표는 서비스 계층을 직접 호출하는 테스트를 넘어 실제 FastAPI 라우터까지
통과하는 사용자 흐름을 검증하는 것입니다.

## 이번 단계에서 추가·수정한 파일

- [backend/tests/test_api_flow_integration.py](../tests/test_api_flow_integration.py)
  - `httpx.ASGITransport`로 FastAPI 앱을 직접 호출합니다.
  - 실제 PostgreSQL과 실제 JWT 인증 흐름을 사용합니다.
  - OpenAI provider만 가짜 provider로 교체합니다.
  - `/health/live`, `/health/ready`도 함께 확인합니다.

- [backend/README.md](../README.md)
  - 현재 단계를 13단계로 갱신했습니다.

- [backend/docs/README.md](README.md)
  - 13단계 문서 링크를 추가했습니다.

- [backend/docs/architecture.md](architecture.md)
  - CI 통합 테스트 범위를 HTTP 라우터까지 확장했다고 정리했습니다.

## 테스트 흐름

```text
POST /auth/register
  → POST /auth/login
  → GET /auth/me
  → POST /characters
  → POST /memories
  → POST /chat
  → POST /chat 기존 conversation_id로 이어가기
  → GET /health/live
  → GET /health/ready
```

이 테스트는 실제 FastAPI dependency, JWT 검증, DB 세션 생성, service, repository를 모두
통과합니다. 다만 OpenAI API는 호출하지 않고 `ApiFlowLLMProvider`라는 가짜 provider로
대체합니다.

## 왜 `ASGITransport`를 사용하나?

실제 uvicorn 서버를 띄우면 운영 환경과 더 비슷하지만 테스트가 무거워집니다.
`httpx.ASGITransport`를 사용하면 네트워크 포트 없이도 HTTP 요청처럼 앱을 호출할 수 있습니다.

```text
httpx AsyncClient
  → ASGITransport
  → FastAPI app
  → router / dependency / service / repository
  → PostgreSQL
```

이 방식은 빠르면서도 라우터와 인증 계층까지 검증할 수 있는 균형점입니다.

## 주의한 점: LLM provider override

통합 테스트는 실제 OpenAI API를 호출하지 않습니다.

```python
app.dependency_overrides[get_llm_provider] = override_llm_provider
```

테스트가 끝나면 override를 제거해 다른 테스트에 영향을 주지 않게 합니다.

## 이번 단계의 한계

- 실제 uvicorn 프로세스를 띄우는 smoke test는 아직 아닙니다.
- SSE 스트리밍 HTTP 응답 본문까지는 이 단계에서 확인하지 않았습니다.
- 브라우저 UI와 연결한 테스트는 아직 없습니다.

다음 단계에서는 백엔드와 연결할 수 있는 최소 프론트엔드 채팅 UI를 추가합니다.
