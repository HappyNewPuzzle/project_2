"""장기 기억 CRUD, 캐릭터 접근 검증, 트랜잭션을 처리한다."""

import uuid

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Memory
from app.repositories.character_repository import CharacterRepository
from app.repositories.memory_repository import MemoryRepository
from app.schemas.memory import MemoryCreate, MemoryUpdate
from app.services.character_service import CharacterNotFoundError


class MemoryNotFoundError(LookupError):
    """현재 사용자 소유의 기억을 찾을 수 없을 때 발생한다."""


class MemoryPersistenceError(RuntimeError):
    """장기 기억 DB 작업 실패를 공통 예외로 감싼다."""


class MemoryService:
    """현재 사용자의 기억만 CRUD할 수 있게 보장한다."""

    def __init__(self, session: AsyncSession, *, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._memories = MemoryRepository(session)
        self._characters = CharacterRepository(session)

    async def _validate_character(self, character_id: uuid.UUID) -> None:
        character = await self._characters.get(character_id)
        if (
            character is None
            or character.owner_id not in (None, self._user_id)
        ):
            raise CharacterNotFoundError(str(character_id))

    async def list(
        self,
        *,
        character_id: uuid.UUID | None,
        offset: int,
        limit: int,
    ) -> list[Memory]:
        try:
            if character_id is not None:
                await self._validate_character(character_id)
            return await self._memories.list_for_user(
                self._user_id,
                character_id=character_id,
                offset=offset,
                limit=limit,
            )
        except CharacterNotFoundError:
            raise
        except SQLAlchemyError as exc:
            raise MemoryPersistenceError("Failed to list memories") from exc

    async def get(self, memory_id: uuid.UUID) -> Memory:
        try:
            memory = await self._memories.get(memory_id, self._user_id)
        except SQLAlchemyError as exc:
            raise MemoryPersistenceError("Failed to get memory") from exc
        if memory is None:
            raise MemoryNotFoundError(str(memory_id))
        return memory

    async def create(self, data: MemoryCreate) -> Memory:
        try:
            if data.character_id is not None:
                await self._validate_character(data.character_id)
            memory = await self._memories.create(data, user_id=self._user_id)
            await self._session.commit()
            await self._session.refresh(memory)
            return memory
        except CharacterNotFoundError:
            raise
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise MemoryPersistenceError("Failed to create memory") from exc

    async def update(
        self,
        memory_id: uuid.UUID,
        data: MemoryUpdate,
    ) -> Memory:
        memory = await self.get(memory_id)
        try:
            self._memories.update(memory, data)
            await self._session.commit()
            await self._session.refresh(memory)
            return memory
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise MemoryPersistenceError("Failed to update memory") from exc

    async def delete(self, memory_id: uuid.UUID) -> None:
        memory = await self.get(memory_id)
        try:
            await self._memories.delete(memory)
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise MemoryPersistenceError("Failed to delete memory") from exc
