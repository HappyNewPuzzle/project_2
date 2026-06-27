"""conversations 테이블에 대한 최소 DB 연산을 캡슐화한다."""

import uuid

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation


class ConversationRepository:
    """비즈니스 판단 없이 Conversation 조회와 변경만 담당한다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, conversation_id: uuid.UUID) -> Conversation | None:
        """기본 키로 대화방을 조회하고 없으면 None을 반환한다."""

        return await self._session.get(Conversation, conversation_id)

    async def create(self, character_id: uuid.UUID) -> Conversation:
        """캐릭터에 연결된 새 대화방을 만들고 ID 생성을 위해 flush한다."""

        conversation = Conversation(character_id=character_id)
        self._session.add(conversation)
        # flush는 INSERT를 보내지만 commit은 하지 않아 트랜잭션 제어권을 서비스에 둔다.
        await self._session.flush()
        return conversation

    async def touch(self, conversation_id: uuid.UUID) -> None:
        """새 메시지가 생긴 대화방의 최근 활동 시각을 갱신한다."""

        statement = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )
        await self._session.execute(statement)
