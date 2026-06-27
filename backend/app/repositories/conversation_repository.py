import uuid

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, conversation_id: uuid.UUID) -> Conversation | None:
        return await self._session.get(Conversation, conversation_id)

    async def create(self, character_id: uuid.UUID) -> Conversation:
        conversation = Conversation(character_id=character_id)
        self._session.add(conversation)
        await self._session.flush()
        return conversation

    async def touch(self, conversation_id: uuid.UUID) -> None:
        statement = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )
        await self._session.execute(statement)
