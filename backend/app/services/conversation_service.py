"""대화방 목록, 메시지 조회, 삭제 유스케이스를 처리한다."""

from __future__ import annotations

import uuid

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository


class ConversationNotFoundError(LookupError):
    """현재 사용자의 대화방을 찾을 수 없을 때 발생한다."""


class ConversationPersistenceError(RuntimeError):
    """대화방 조회·삭제 중 DB 오류가 발생했을 때 사용하는 공통 예외."""


class ConversationService:
    """현재 사용자 범위에서만 대화방과 메시지를 다루는 서비스."""

    def __init__(self, session: AsyncSession, *, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._conversations = ConversationRepository(session)
        self._messages = MessageRepository(session)

    async def list(self, *, offset: int, limit: int) -> list[Conversation]:
        """현재 사용자에게 속한 대화방 목록만 반환한다."""

        try:
            return await self._conversations.list_for_user(
                self._user_id,
                offset=offset,
                limit=limit,
            )
        except SQLAlchemyError as exc:
            raise ConversationPersistenceError(
                "Failed to list conversations",
            ) from exc

    async def get(self, conversation_id: uuid.UUID) -> Conversation:
        """대화방을 조회하고 현재 사용자 소유인지 확인한다."""

        try:
            conversation = await self._conversations.get(conversation_id)
        except SQLAlchemyError as exc:
            raise ConversationPersistenceError(
                "Failed to get conversation",
            ) from exc

        if conversation is None or conversation.user_id != self._user_id:
            raise ConversationNotFoundError(str(conversation_id))
        return conversation

    async def list_messages(
        self,
        conversation_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
    ) -> list[Message]:
        """현재 사용자 대화방의 메시지를 오래된 순서로 조회한다."""

        await self.get(conversation_id)
        try:
            return await self._messages.list_for_conversation(
                conversation_id,
                offset=offset,
                limit=limit,
            )
        except SQLAlchemyError as exc:
            raise ConversationPersistenceError(
                "Failed to list conversation messages",
            ) from exc

    async def delete(self, conversation_id: uuid.UUID) -> None:
        """현재 사용자 대화방을 삭제하고 소속 메시지도 함께 제거한다."""

        conversation = await self.get(conversation_id)
        try:
            await self._conversations.delete(conversation)
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise ConversationPersistenceError(
                "Failed to delete conversation",
            ) from exc
