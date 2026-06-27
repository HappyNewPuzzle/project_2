from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_service import LLMProvider, get_llm_provider


class FakeLLMProvider:
    async def generate(self, message: str) -> str:
        return f"Echo: {message}"

    async def stream(self, message: str) -> AsyncIterator[str]:
        yield "Echo: "
        yield message


def override_llm_provider() -> LLMProvider:
    return FakeLLMProvider()


app.dependency_overrides[get_llm_provider] = override_llm_provider
client = TestClient(app)


def test_chat_returns_llm_reply() -> None:
    response = client.post("/chat", json={"message": "안녕"})

    assert response.status_code == 200
    assert response.json() == {"reply": "Echo: 안녕"}


def test_chat_rejects_empty_message() -> None:
    response = client.post("/chat", json={"message": ""})

    assert response.status_code == 422


def test_stream_chat_returns_sse_events() -> None:
    with client.stream(
        "POST",
        "/chat/stream",
        json={"message": "안녕"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'event: token\ndata: {"delta": "Echo: "}' in body
    assert 'event: token\ndata: {"delta": "안녕"}' in body
    assert "event: done\ndata: {}" in body
