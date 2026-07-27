"""memory_embeddings 테이블 저장과 조회를 담당한다."""

import json
import uuid

from sqlalchemy import or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Memory, MemoryEmbedding


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

    async def search(
        self,
        *,
        user_id: uuid.UUID,
        query_vector: list[float],
        character_id: uuid.UUID | None,
        limit: int,
    ) -> list[tuple[Memory, float]]:
        """현재 사용자 범위 안에서 cosine similarity가 높은 기억을 조회한다."""

        # 필터가 있는 HNSW 검색에서도 충분한 후보를 찾도록 반복 scan을 활성화한다.
        await self._session.execute(
            text("SET LOCAL hnsw.iterative_scan = strict_order")
        )
        distance = MemoryEmbedding.embedding.cosine_distance(query_vector)
        statement = (
            select(Memory, distance.label("distance"))
            .join(
                MemoryEmbedding,
                MemoryEmbedding.memory_id == Memory.id,
            )
            .where(
                Memory.user_id == user_id,
                Memory.is_active.is_(True),
                MemoryEmbedding.embedding.is_not(None),
            )
        )
        if character_id is not None:
            # 캐릭터 대화 검색은 전역 기억과 해당 캐릭터 기억만 함께 사용한다.
            statement = statement.where(
                or_(
                    Memory.character_id.is_(None),
                    Memory.character_id == character_id,
                )
            )
        # 거리 연산 자체를 오름차순 정렬하고 LIMIT해야 HNSW index를 사용할 수 있다.
        statement = statement.order_by(distance).limit(limit)
        rows = (await self._session.execute(statement)).all()
        return [
            (
                memory,
                max(-1.0, min(1.0, 1.0 - float(cosine_distance))),
            )
            for memory, cosine_distance in rows
        ]
