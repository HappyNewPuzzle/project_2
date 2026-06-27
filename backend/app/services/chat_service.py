import uuid
from collections.abc import AsyncGenerator
from contextlib import aclosing
from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DEFAULT_CHARACTER_ID, MessageRole
from app.repositories.character_repository import CharacterRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.services.character_service import (
    CharacterNotFoundError,
    build_character_instructions,
)
from app.services.llm_service import LLMMessage, LLMProvider


class ConversationNotFoundError(LookupError):
    """Raised when a requested conversation does not exist."""


class ChatPersistenceError(RuntimeError):
    """Raised when a chat message cannot be persisted."""


class ConversationCharacterMismatchError(ValueError):
    """Raised when a conversation is used with a different character."""


@dataclass(frozen=True, slots=True)
class ChatTurn:
    conversation_id: uuid.UUID
    character_id: uuid.UUID
    instructions: str
    messages: tuple[LLMMessage, ...]


@dataclass(frozen=True, slots=True)
class ChatResult:
    conversation_id: uuid.UUID
    character_id: uuid.UUID
    reply: str


class ChatService:
    def __init__(
        self,
        session: AsyncSession,
        llm: LLMProvider,
        *,
        history_limit: int,
    ) -> None:
        self._session = session
        self._llm = llm
        self._history_limit = history_limit
        self._characters = CharacterRepository(session)
        self._conversations = ConversationRepository(session)
        self._messages = MessageRepository(session)

    async def start_turn(
        self,
        message: str,
        conversation_id: uuid.UUID | None,
        character_id: uuid.UUID | None,
    ) -> ChatTurn:
        try:
            if conversation_id is None:
                active_character_id = character_id or DEFAULT_CHARACTER_ID
                character = await self._characters.get(active_character_id)
                if character is None:
                    raise CharacterNotFoundError(str(active_character_id))
                conversation = await self._conversations.create(active_character_id)
            else:
                conversation = await self._conversations.get(conversation_id)
                if conversation is None:
                    raise ConversationNotFoundError(str(conversation_id))
                if (
                    character_id is not None
                    and character_id != conversation.character_id
                ):
                    raise ConversationCharacterMismatchError(str(conversation_id))
                character = await self._characters.get(conversation.character_id)
                if character is None:
                    raise CharacterNotFoundError(str(conversation.character_id))

            self._messages.add(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=message,
            )
            await self._conversations.touch(conversation.id)
            await self._session.commit()

            recent_messages = await self._messages.list_recent(
                conversation.id,
                limit=self._history_limit,
            )
            llm_messages = tuple(
                LLMMessage(
                    role=(
                        "assistant"
                        if saved_message.role == MessageRole.ASSISTANT.value
                        else "user"
                    ),
                    content=saved_message.content,
                )
                for saved_message in recent_messages
            )
            return ChatTurn(
                conversation_id=conversation.id,
                character_id=character.id,
                instructions=build_character_instructions(character),
                messages=llm_messages,
            )
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise ChatPersistenceError("Failed to prepare chat turn") from exc

    async def complete_turn(
        self,
        conversation_id: uuid.UUID,
        reply: str,
    ) -> None:
        try:
            self._messages.add(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=reply,
            )
            await self._conversations.touch(conversation_id)
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise ChatPersistenceError("Failed to store assistant message") from exc

    async def reply(
        self,
        message: str,
        conversation_id: uuid.UUID | None,
        character_id: uuid.UUID | None,
    ) -> ChatResult:
        turn = await self.start_turn(message, conversation_id, character_id)
        reply = await self._llm.generate(
            turn.messages,
            instructions=turn.instructions,
        )
        await self.complete_turn(turn.conversation_id, reply)
        return ChatResult(
            conversation_id=turn.conversation_id,
            character_id=turn.character_id,
            reply=reply,
        )

    async def stream_reply(
        self,
        turn: ChatTurn,
    ) -> AsyncGenerator[str, None]:
        chunks: list[str] = []
        async with aclosing(
            self._llm.stream(
                turn.messages,
                instructions=turn.instructions,
            )
        ) as stream:
            async for delta in stream:
                chunks.append(delta)
                yield delta

        await self.complete_turn(turn.conversation_id, "".join(chunks))
