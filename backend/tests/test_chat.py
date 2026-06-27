"""실제 DB/LLM 없이 채팅 HTTP 계약을 검증하는 API 테스트."""

import uuid
from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient

from app.api.dependencies import get_chat_service
from app.db.models import DEFAULT_CHARACTER_ID
from app.main import app
from app.services.chat_service import ChatResult, ChatTurn
from app.services.llm_service import LLMMessage

TEST_CONVERSATION_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


class FakeChatService:
    """라우터만 테스트할 수 있도록 외부 의존성을 제거한 가짜 서비스."""

    async def reply(
        self,
        message: str,
        conversation_id: uuid.UUID | None,
        character_id: uuid.UUID | None,
    ) -> ChatResult:
        return ChatResult(
            conversation_id=conversation_id or TEST_CONVERSATION_ID,
            character_id=character_id or DEFAULT_CHARACTER_ID,
            reply=f"Echo: {message}",
        )

    async def start_turn(
        self,
        message: str,
        conversation_id: uuid.UUID | None,
        character_id: uuid.UUID | None,
    ) -> ChatTurn:
        return ChatTurn(
            conversation_id=conversation_id or TEST_CONVERSATION_ID,
            character_id=character_id or DEFAULT_CHARACTER_ID,
            instructions="Stay in character.",
            messages=(LLMMessage(role="user", content=message),),
        )

    async def stream_reply(
        self,
        turn: ChatTurn,
    ) -> AsyncGenerator[str, None]:
        yield "Echo: "
        yield turn.messages[-1].content


def override_chat_service() -> FakeChatService:
    """FastAPI dependency override에서 사용할 팩토리."""

    return FakeChatService()


# 테스트 요청은 진짜 DB 대신 위 가짜 서비스를 주입받는다.
app.dependency_overrides[get_chat_service] = override_chat_service
client = TestClient(app)


def test_chat_returns_llm_reply() -> None:
    """첫 채팅 응답에 대화 ID, 캐릭터 ID, 답변이 모두 포함되는지 확인한다."""

    response = client.post("/chat", json={"message": "안녕"})

    assert response.status_code == 200
    assert response.json() == {
        "conversation_id": str(TEST_CONVERSATION_ID),
        "character_id": str(DEFAULT_CHARACTER_ID),
        "reply": "Echo: 안녕",
    }


def test_chat_reuses_conversation() -> None:
    """클라이언트가 보낸 기존 대화 ID가 그대로 유지되는지 확인한다."""

    conversation_id = "22222222-2222-2222-2222-222222222222"

    response = client.post(
        "/chat",
        json={
            "message": "다시 안녕",
            "conversation_id": conversation_id,
        },
    )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == conversation_id


def test_chat_rejects_empty_message() -> None:
    """Pydantic이 빈 메시지를 422로 거부하는지 확인한다."""

    response = client.post("/chat", json={"message": ""})

    assert response.status_code == 422


def test_stream_chat_returns_sse_events() -> None:
    """스트림 이벤트 순서가 conversation → token → done인지 확인한다."""

    with client.stream(
        "POST",
        "/chat/stream",
        json={"message": "안녕"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert (
        "event: conversation\n"
        f'data: {{"conversation_id": "{TEST_CONVERSATION_ID}", '
        f'"character_id": "{DEFAULT_CHARACTER_ID}"}}'
    ) in body
    assert 'event: token\ndata: {"delta": "Echo: "}' in body
    assert 'event: token\ndata: {"delta": "안녕"}' in body
    assert "event: done\ndata: {}" in body
