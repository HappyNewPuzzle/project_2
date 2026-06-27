"""채팅 한 턴의 DB 저장, 문맥 구성, LLM 호출 순서를 조정한다."""

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
    """이어 가려는 대화방이 존재하지 않을 때 발생한다."""


class ChatPersistenceError(RuntimeError):
    """채팅 관련 SQLAlchemy 오류를 API용 공통 오류로 변환한다."""


class ConversationCharacterMismatchError(ValueError):
    """이미 시작한 대화의 캐릭터를 중간에 바꾸려 할 때 발생한다."""


@dataclass(frozen=True, slots=True)
class ChatTurn:
    """LLM 호출 직전에 준비가 끝난 한 턴의 불변 데이터."""

    conversation_id: uuid.UUID
    character_id: uuid.UUID
    instructions: str
    messages: tuple[LLMMessage, ...]


@dataclass(frozen=True, slots=True)
class ChatResult:
    """일반(non-streaming) 채팅 호출의 최종 결과."""

    conversation_id: uuid.UUID
    character_id: uuid.UUID
    reply: str


class ChatService:
    """라우터, repository, LLM provider 사이의 유스케이스 계층."""

    def __init__(
        self,
        session: AsyncSession,
        llm: LLMProvider,
        *,
        user_id: uuid.UUID,
        history_limit: int,
    ) -> None:
        self._session = session
        self._llm = llm
        self._user_id = user_id
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
        """대화와 캐릭터를 확인하고 사용자 메시지 및 최근 문맥을 준비한다."""

        try:
            if conversation_id is None:
                # 새 대화는 요청 캐릭터 또는 항상 존재하는 기본 캐릭터를 사용한다.
                active_character_id = character_id or DEFAULT_CHARACTER_ID
                character = await self._characters.get(active_character_id)
                if (
                    character is None
                    or character.owner_id not in (None, self._user_id)
                ):
                    raise CharacterNotFoundError(str(active_character_id))
                conversation = await self._conversations.create(
                    active_character_id,
                    user_id=self._user_id,
                )
            else:
                # 기존 대화는 DB에 저장된 캐릭터를 계속 사용한다.
                conversation = await self._conversations.get(conversation_id)
                if (
                    conversation is None
                    or conversation.user_id != self._user_id
                ):
                    raise ConversationNotFoundError(str(conversation_id))
                if (
                    character_id is not None
                    and character_id != conversation.character_id
                ):
                    # 한 대화 안에서 인격과 문맥이 섞이는 것을 막는다.
                    raise ConversationCharacterMismatchError(str(conversation_id))
                character = await self._characters.get(conversation.character_id)
                if (
                    character is None
                    or character.owner_id not in (None, self._user_id)
                ):
                    raise CharacterNotFoundError(str(conversation.character_id))

            # LLM 호출 전에 사용자 메시지를 먼저 기록한다.
            self._messages.add(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=message,
            )
            await self._conversations.touch(conversation.id)
            # 여기서 별도 commit하므로 이후 LLM이 실패해도 사용자 입력은 남는다.
            await self._session.commit()

            # 방금 저장한 사용자 메시지를 포함한 최신 N개 문맥을 조회한다.
            recent_messages = await self._messages.list_recent(
                conversation.id,
                limit=self._history_limit,
            )
            # DB 문자열 역할을 provider가 이해하는 불변 LLMMessage 목록으로 변환한다.
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
            # commit 전 실패한 변경만 되돌리고 DB 세부 오류는 외부에 노출하지 않는다.
            await self._session.rollback()
            raise ChatPersistenceError("Failed to prepare chat turn") from exc

    async def complete_turn(
        self,
        conversation_id: uuid.UUID,
        reply: str,
    ) -> None:
        """완성된 AI 답변을 두 번째 트랜잭션으로 저장한다."""

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
        """일반 채팅 한 턴을 준비하고 LLM 답변까지 완성한다."""

        turn = await self.start_turn(message, conversation_id, character_id)
        # 캐릭터 지침과 최근 역할별 메시지를 provider에 각각 전달한다.
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
        """텍스트 조각을 전달하면서 모두 모아 완료 후 한 번만 저장한다."""

        chunks: list[str] = []
        # aclosing은 브라우저 연결이 끊겨도 LLM 스트림 정리를 보장한다.
        async with aclosing(
            self._llm.stream(
                turn.messages,
                instructions=turn.instructions,
            )
        ) as stream:
            async for delta in stream:
                # 클라이언트에는 즉시 전달하되 DB에는 아직 불완전한 답을 쓰지 않는다.
                chunks.append(delta)
                yield delta

        # 정상적으로 끝난 경우에만 조각을 합쳐 assistant 메시지로 저장한다.
        await self.complete_turn(turn.conversation_id, "".join(chunks))
