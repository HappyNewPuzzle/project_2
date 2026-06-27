"""memories 테이블 CRUD와 채팅용 중요도 조회를 담당한다."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Memory
from app.schemas.memory import MemoryCreate, MemoryUpdate


class MemoryRepository:
    """사용자 소유권 조건을 모든 기억 쿼리에 포함한다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, memory_id: uuid.UUID, user_id: uuid.UUID) -> Memory | None:
        statement = select(Memory).where(
            Memory.id == memory_id,
            Memory.user_id == user_id,
        )
        return await self._session.scalar(statement)

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        character_id: uuid.UUID | None,
        offset: int,
        limit: int,
    ) -> list[Memory]:
        statement = select(Memory).where(Memory.user_id == user_id)
        if character_id is not None:
            statement = statement.where(Memory.character_id == character_id)
        statement = (
            statement.order_by(Memory.updated_at.desc(), Memory.id)
            .offset(offset)
            .limit(limit)
        )
        return list((await self._session.scalars(statement)).all())

    async def list_for_prompt(
        self,
        user_id: uuid.UUID,
        character_id: uuid.UUID,
        *,
        limit: int,
    ) -> list[Memory]:
        """전역 기억과 현재 캐릭터 기억 중 활성 항목을 중요도순으로 고른다."""

        if limit == 0:
            return []
        statement = (
            select(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.is_active.is_(True),
                or_(
                    Memory.character_id.is_(None),
                    Memory.character_id == character_id,
                ),
            )
            .order_by(
                Memory.importance.desc(),
                Memory.updated_at.desc(),
                Memory.id,
            )
            .limit(limit)
        )
        return list((await self._session.scalars(statement)).all())

    async def create(
        self,
        data: MemoryCreate,
        *,
        user_id: uuid.UUID,
    ) -> Memory:
        memory = Memory(user_id=user_id, **data.model_dump())
        self._session.add(memory)
        await self._session.flush()
        return memory

    def update(self, memory: Memory, data: MemoryUpdate) -> Memory:
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(memory, field, value)
        return memory

    async def delete(self, memory: Memory) -> None:
        await self._session.delete(memory)
