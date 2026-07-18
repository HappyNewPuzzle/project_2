"""FastAPI HTTP 라우터까지 통과하는 실제 DB 통합 테스트."""

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Sequence

import httpx
import pytest

from app.api.dependencies import get_llm_provider
from app.db.session import get_engine, get_session_factory
from app.main import app
from app.services.llm_service import LLMMessage


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="RUN_DB_INTEGRATION=1일 때만 PostgreSQL 통합 테스트를 실행한다.",
)


class ApiFlowLLMProvider:
    """HTTP 통합 테스트에서 외부 LLM 대신 사용할 가짜 provider."""

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> str:
        """입력 마지막 메시지를 포함한 예측 가능한 답변을 반환한다."""

        return f"API Echo: {messages[-1].content}"

    async def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> AsyncGenerator[str, None]:
        """스트리밍 라우터 호출 시 두 조각으로 응답한다."""

        yield "API "
        yield "Stream"


def override_llm_provider() -> ApiFlowLLMProvider:
    """FastAPI dependency override에서 사용할 provider 팩토리."""

    return ApiFlowLLMProvider()


async def _run_api_flow() -> None:
    """회원가입부터 채팅 API까지 HTTP 요청으로 검증한다."""

    # 실제 OpenAI provider 대신 테스트 provider를 주입한다.
    app.dependency_overrides[get_llm_provider] = override_llm_provider

    try:
        # ASGITransport는 네트워크 포트 없이 FastAPI 앱을 직접 호출한다.
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            email = f"api-{uuid.uuid4().hex}@example.com"
            password = "strong-password"

            # 1) HTTP 회원가입 API를 호출한다.
            register_response = await client.post(
                "/auth/register",
                json={"email": email, "password": password},
            )
            assert register_response.status_code == 201
            assert register_response.json()["email"] == email

            # 2) OAuth2 form 로그인 API로 access token을 받는다.
            login_response = await client.post(
                "/auth/login",
                data={"username": email, "password": password},
            )
            assert login_response.status_code == 200
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # 3) Bearer token으로 현재 사용자 API를 호출한다.
            me_response = await client.get("/auth/me", headers=headers)
            assert me_response.status_code == 200
            assert me_response.json()["email"] == email

            # 4) 인증된 사용자로 캐릭터를 만든다.
            character_response = await client.post(
                "/characters",
                headers=headers,
                json={
                    "name": "HTTP 루나",
                    "description": "HTTP 통합 테스트 캐릭터",
                },
            )
            assert character_response.status_code == 201
            character_id = character_response.json()["id"]

            # 5) 캐릭터에 연결된 장기 기억을 만든다.
            memory_response = await client.post(
                "/memories",
                headers=headers,
                json={
                    "content": "사용자는 HTTP 테스트를 진행 중이다",
                    "character_id": character_id,
                    "importance": 4,
                },
            )
            assert memory_response.status_code == 201

            # 6) 일반 채팅 API가 DB 저장과 가짜 LLM 호출을 통과하는지 확인한다.
            chat_response = await client.post(
                "/chat",
                headers=headers,
                json={
                    "message": "HTTP로 대화해줘",
                    "character_id": character_id,
                },
            )
            assert chat_response.status_code == 200
            chat_body = chat_response.json()
            assert chat_body["character_id"] == character_id
            assert chat_body["reply"] == "API Echo: HTTP로 대화해줘"

            # 7) 같은 대화방을 이어갈 수 있는지 확인한다.
            followup_response = await client.post(
                "/chat",
                headers=headers,
                json={
                    "message": "방금 대화 이어서 말해줘",
                    "conversation_id": chat_body["conversation_id"],
                },
            )
            assert followup_response.status_code == 200
            assert (
                followup_response.json()["conversation_id"]
                == chat_body["conversation_id"]
            )

            # 8) health live는 DB와 무관하게 살아 있어야 한다.
            live_response = await client.get("/health/live")
            assert live_response.status_code == 200

            # 9) health ready는 실제 PostgreSQL 연결까지 성공해야 한다.
            ready_response = await client.get("/health/ready")
            assert ready_response.status_code == 200
    finally:
        # 다른 테스트에 가짜 provider가 새지 않게 override를 제거한다.
        app.dependency_overrides.pop(get_llm_provider, None)
        # ASGI 통합 테스트가 사용한 asyncpg 연결 풀을 현재 루프에서 닫는다.
        await get_engine().dispose()
        # 다음 통합 테스트 파일이 새 루프에 맞춰 새 엔진을 만들도록 캐시를 비운다.
        get_session_factory.cache_clear()
        get_engine.cache_clear()


def test_http_api_flow_with_postgres() -> None:
    """실제 HTTP 라우터와 PostgreSQL을 함께 사용하는 핵심 흐름을 검증한다."""

    asyncio.run(_run_api_flow())
