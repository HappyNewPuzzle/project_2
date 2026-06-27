"""messages 테이블의 저장과 최근 문맥 조회를 담당한다."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, MessageRole


class MessageRepository:
    """메시지 관련 SQL을 서비스 계층에서 분리한다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(
        self,
        *,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
    ) -> Message:
        """메시지를 세션에 추가하되 commit은 호출자에게 맡긴다."""

        message = Message(
            conversation_id=conversation_id,
            role=role.value,
            content=content,
        )
        self._session.add(message)
        return message

    async def list_recent(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int = 20,
    ) -> list[Message]:
        """가장 최근 메시지 N개를 오래된 것부터 읽는 순서로 반환한다."""

        # DB에서는 최신 N개를 고르기 위해 내림차순으로 제한한다.
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list((await self._session.scalars(statement)).all())
        # LLM에는 실제 대화 순서대로 보내야 하므로 메모리에서 다시 뒤집는다.
        messages.reverse()
        return messages
