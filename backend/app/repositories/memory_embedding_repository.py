"""memory_embeddings 테이블 저장과 조회를 담당한다."""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryEmbedding


class MemoryEmbeddingRepository:
    """embedding 저장 형식을 서비스 계층에서 숨긴다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        memory_id: uuid.UUID,
        provider: str,
        vector: list[float],
    ) -> None:
        """같은 memory_id embedding이 있으면 갱신하고 없으면 추가한다."""

        statement = insert(MemoryEmbedding).values(
            memory_id=memory_id,
            provider=provider,
            dimensions=len(vector),
            vector_json=json.dumps(vector),
            embedding=vector,
        )
        update_values = {
            "provider": provider,
            "dimensions": len(vector),
            "vector_json": json.dumps(vector),
            "embedding": vector,
        }
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[MemoryEmbedding.memory_id],
                set_=update_values,
            )
        )

    async def list_all(self) -> list[MemoryEmbedding]:
        """현재 저장된 embedding을 모두 반환한다.

        23단계에서 전체 조회를 pgvector similarity query로 교체한다.
        """

        return list((await self._session.scalars(select(MemoryEmbedding))).all())
