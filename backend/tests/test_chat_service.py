import asyncio
import uuid
from collections.abc import AsyncGenerator, Sequence
from types import SimpleNamespace

from app.db.models import DEFAULT_CHARACTER_ID, MessageRole
from app.services.chat_service import ChatService
from app.services.llm_service import LLMMessage

CONVERSATION_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


class FakeSession:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def commit(self) -> None:
        self._events.append("commit")

    async def rollback(self) -> None:
        self._events.append("rollback")


class FakeCharacterRepository:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def get(self, character_id: uuid.UUID) -> SimpleNamespace:
        self._events.append("get_character")
        return SimpleNamespace(
            id=character_id,
            name="Luna",
            description="A moon librarian.",
            personality="Calm and curious.",
            speaking_style="Soft and concise.",
            system_prompt="Use gentle imagery.",
        )


class FakeConversationRepository:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def create(self, character_id: uuid.UUID) -> SimpleNamespace:
        self._events.append("create_conversation")
        return SimpleNamespace(
            id=CONVERSATION_ID,
            character_id=character_id,
        )

    async def get(self, conversation_id: uuid.UUID) -> SimpleNamespace:
        self._events.append("get_conversation")
        return SimpleNamespace(
            id=conversation_id,
            character_id=DEFAULT_CHARACTER_ID,
        )

    async def touch(self, conversation_id: uuid.UUID) -> None:
        self._events.append("touch_conversation")


class FakeMessageRepository:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self._messages = [
            SimpleNamespace(role="user", content="Earlier question"),
            SimpleNamespace(role="assistant", content="Earlier answer"),
        ]

    def add(
        self,
        *,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
    ) -> None:
        self._events.append(f"add_{role.value}")
        self._messages.append(SimpleNamespace(role=role.value, content=content))

    async def list_recent(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int,
    ) -> list[SimpleNamespace]:
        self._events.append("list_recent")
        return self._messages[-limit:]


class FakeLLMProvider:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self.messages: Sequence[LLMMessage] = ()
        self.instructions = ""

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> str:
        self._events.append("generate")
        self.messages = messages
        self.instructions = instructions
        return "AI reply"

    async def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> AsyncGenerator[str, None]:
        yield "AI "
        yield "reply"


def test_reply_uses_character_and_recent_history() -> None:
    events: list[str] = []
    llm = FakeLLMProvider(events)
    service = ChatService(  # type: ignore[arg-type]
        FakeSession(events),
        llm,
        history_limit=20,
    )
    service._characters = FakeCharacterRepository(events)  # type: ignore[assignment]
    service._conversations = FakeConversationRepository(events)  # type: ignore[assignment]
    service._messages = FakeMessageRepository(events)  # type: ignore[assignment]

    result = asyncio.run(service.reply("Hello", None, DEFAULT_CHARACTER_ID))

    assert result.conversation_id == CONVERSATION_ID
    assert result.character_id == DEFAULT_CHARACTER_ID
    assert result.reply == "AI reply"
    assert [(message.role, message.content) for message in llm.messages] == [
        ("user", "Earlier question"),
        ("assistant", "Earlier answer"),
        ("user", "Hello"),
    ]
    assert "Luna" in llm.instructions
    assert "Use gentle imagery." in llm.instructions
    assert events == [
        "get_character",
        "create_conversation",
        "add_user",
        "touch_conversation",
        "commit",
        "list_recent",
        "generate",
        "add_assistant",
        "touch_conversation",
        "commit",
    ]
