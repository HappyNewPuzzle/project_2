"""가짜 ConversationService로 대화방 REST API 계약을 검증한다."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dependencies import get_conversation_service
from app.main import app


CONVERSATION_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
USER_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")
CHARACTER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
MESSAGE_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def make_conversation() -> SimpleNamespace:
    """응답 스키마가 읽을 수 있는 대화방 유사 객체를 만든다."""

    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=CONVERSATION_ID,
        user_id=USER_ID,
        character_id=CHARACTER_ID,
        title="천문학 이야기",
        created_at=now,
        updated_at=now,
    )


def make_message() -> SimpleNamespace:
    """응답 스키마가 읽을 수 있는 메시지 유사 객체를 만든다."""

    return SimpleNamespace(
        id=MESSAGE_ID,
        conversation_id=CONVERSATION_ID,
        role="user",
        content="안녕",
        created_at=datetime.now(timezone.utc),
    )


class FakeConversationService:
    """DB 없이 대화방 라우터의 직렬화와 상태 코드만 테스트한다."""

    async def list(self, *, offset: int, limit: int) -> list[SimpleNamespace]:
        return [make_conversation()]

    async def list_messages(
        self,
        conversation_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
    ) -> list[SimpleNamespace]:
        return [make_message()]

    async def delete(self, conversation_id: uuid.UUID) -> None:
        return None


def override_conversation_service() -> FakeConversationService:
    """FastAPI dependency override에서 사용할 팩토리."""

    return FakeConversationService()


app.dependency_overrides[get_conversation_service] = override_conversation_service
client = TestClient(app)


def test_list_conversations() -> None:
    """대화방 목록 API가 배열 응답을 반환하는지 확인한다."""

    response = client.get("/conversations")

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(CONVERSATION_ID)
    assert response.json()[0]["character_id"] == str(CHARACTER_ID)
    assert response.json()[0]["title"] == "천문학 이야기"


def test_list_conversation_messages() -> None:
    """대화방 메시지 조회 API가 오래된 순서 메시지 배열을 반환하는지 확인한다."""

    response = client.get(f"/conversations/{CONVERSATION_ID}/messages")

    assert response.status_code == 200
    assert response.json()[0]["role"] == "user"
    assert response.json()[0]["content"] == "안녕"


def test_delete_conversation() -> None:
    """대화방 삭제 API가 본문 없는 204를 반환하는지 확인한다."""

    response = client.delete(f"/conversations/{CONVERSATION_ID}")

    assert response.status_code == 204
