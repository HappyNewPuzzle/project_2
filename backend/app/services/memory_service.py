"""장기 기억 CRUD, 캐릭터 접근 검증, 트랜잭션을 처리한다."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Memory
from app.repositories.character_repository import CharacterRepository
from app.repositories.memory_embedding_repository import MemoryEmbeddingRepository
from app.repositories.memory_repository import MemoryRepository
from app.schemas.memory import MemoryCreate, MemoryUpdate
from app.services.character_service import CharacterNotFoundError
from app.services.embedding_service import (
    EmbeddingConfigurationError,
    EmbeddingProvider,
    EmbeddingServiceError,
    get_embedding_provider,
)


class MemoryNotFoundError(LookupError):
    """현재 사용자 소유의 기억을 찾을 수 없을 때 발생한다."""


class MemoryPersistenceError(RuntimeError):
    """장기 기억 DB 작업 실패를 공통 예외로 감싼다."""


class MemoryIndexingError(RuntimeError):
    """embedding 생성 또는 의미 검색이 실패했을 때 발생한다."""


@dataclass(frozen=True, slots=True)
class MemorySearchMatch:
    """서비스가 라우터에 반환할 기억과 cosine similarity 묶음."""

    memory: Memory
    score: float


class MemoryService:
    """현재 사용자의 기억만 CRUD할 수 있게 보장한다."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._embedding_provider = (
            embedding_provider or get_embedding_provider()
        )
        self._memories = MemoryRepository(session)
        self._embeddings = MemoryEmbeddingRepository(session)
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
            # DB에 쓰기 전에 vector를 생성해 provider 실패 시 불완전한 기억을 남기지 않는다.
            vector = await self._embedding_provider.embed(data.content)
            memory = await self._memories.create(data, user_id=self._user_id)
            await self._embeddings.upsert(
                memory_id=memory.id,
                provider=self._embedding_provider.provider_name,
                vector=vector,
            )
            await self._session.commit()
            await self._session.refresh(memory)
            return memory
        except CharacterNotFoundError:
            raise
        except (EmbeddingConfigurationError, EmbeddingServiceError) as exc:
            await self._session.rollback()
            raise MemoryIndexingError("Failed to index memory") from exc
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
            vector = None
            if data.content is not None and data.content != memory.content:
                # 내용이 실제로 바뀔 때만 외부 embedding 호출과 upsert를 수행한다.
                vector = await self._embedding_provider.embed(data.content)
            self._memories.update(memory, data)
            if vector is not None:
                await self._embeddings.upsert(
                    memory_id=memory.id,
                    provider=self._embedding_provider.provider_name,
                    vector=vector,
                )
            await self._session.commit()
            await self._session.refresh(memory)
            return memory
        except (EmbeddingConfigurationError, EmbeddingServiceError) as exc:
            await self._session.rollback()
            raise MemoryIndexingError("Failed to reindex memory") from exc
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise MemoryPersistenceError("Failed to update memory") from exc

    async def search(
        self,
        query: str,
        *,
        character_id: uuid.UUID | None,
        limit: int,
    ) -> list[MemorySearchMatch]:
        """query embedding과 가까운 현재 사용자의 활성 기억을 반환한다."""

        try:
            if character_id is not None:
                await self._validate_character(character_id)
            query_vector = await self._embedding_provider.embed(query)
            rows = await self._embeddings.search(
                user_id=self._user_id,
                query_vector=query_vector,
                character_id=character_id,
                limit=limit,
            )
            return [
                MemorySearchMatch(memory=memory, score=score)
                for memory, score in rows
            ]
        except CharacterNotFoundError:
            raise
        except (EmbeddingConfigurationError, EmbeddingServiceError) as exc:
            await self._session.rollback()
            raise MemoryIndexingError("Failed to embed search query") from exc
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise MemoryPersistenceError("Failed to search memories") from exc

    async def reindex(self, *, limit: int) -> int:
        """현재 provider와 맞지 않는 기존 기억을 제한된 개수만 재색인한다."""

        try:
            memories = await self._memories.list_needing_embedding(
                self._user_id,
                provider=self._embedding_provider.provider_name,
                limit=limit,
            )
            for memory in memories:
                vector = await self._embedding_provider.embed(memory.content)
                await self._embeddings.upsert(
                    memory_id=memory.id,
                    provider=self._embedding_provider.provider_name,
                    vector=vector,
                )
            await self._session.commit()
            return len(memories)
        except (EmbeddingConfigurationError, EmbeddingServiceError) as exc:
            await self._session.rollback()
            raise MemoryIndexingError("Failed to reindex memories") from exc
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise MemoryPersistenceError("Failed to reindex memories") from exc

    async def delete(self, memory_id: uuid.UUID) -> None:
        memory = await self.get(memory_id)
        try:
            await self._memories.delete(memory)
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise MemoryPersistenceError("Failed to delete memory") from exc
