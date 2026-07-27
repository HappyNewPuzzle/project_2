"""실제 PostgreSQL에서 pgvector extension과 벡터 저장을 검증한다."""

import asyncio
import os
import uuid

import pytest
from sqlalchemy import text

from app.db.models import Memory, MemoryEmbedding, User
from app.db.session import get_engine, get_session_factory
from app.repositories.memory_embedding_repository import (
    MemoryEmbeddingRepository,
)


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="RUN_DB_INTEGRATION=1일 때만 PostgreSQL 통합 테스트를 실행한다.",
)


async def _run_pgvector_flow() -> None:
    """extension 확인부터 1536차원 벡터 왕복 저장까지 실행한다."""

    session_factory = get_session_factory()
    async with session_factory() as session:
        # migration이 현재 데이터베이스에 vector 확장을 활성화했는지 확인한다.
        extension_version = await session.scalar(
            text(
                "SELECT extversion FROM pg_extension "
                "WHERE extname = 'vector'"
            )
        )
        assert extension_version is not None
        index_name = await session.scalar(
            text(
                "SELECT to_regclass("
                "'ix_memory_embeddings_embedding_cosine'"
                ")"
            )
        )
        assert index_name == "ix_memory_embeddings_embedding_cosine"

        # 외래 키를 만족하도록 테스트 사용자와 장기 기억을 먼저 만든다.
        user = User(
            email=f"pgvector-{uuid.uuid4().hex}@example.com",
            hashed_password="integration-test",
        )
        session.add(user)
        await session.flush()
        memory = Memory(
            user_id=user.id,
            content="사용자는 벡터 검색을 배우고 있다",
            importance=4,
        )
        session.add(memory)
        await session.flush()

        # 첫 값만 1인 간단한 1536차원 벡터를 repository를 통해 저장한다.
        vector = [1.0] + [0.0] * 1535
        repository = MemoryEmbeddingRepository(session)
        await repository.upsert(
            memory_id=memory.id,
            provider="integration-test:1536",
            vector=vector,
        )
        await session.commit()

        # pgvector SQLAlchemy 타입이 DB 값을 Python sequence로 복원해야 한다.
        stored = await session.get(MemoryEmbedding, memory.id)
        assert stored is not None
        assert stored.embedding is not None
        assert len(stored.embedding) == 1536
        assert float(stored.embedding[0]) == 1.0

        # 사용자를 지우면 memory와 embedding도 FK CASCADE로 함께 정리된다.
        await session.delete(user)
        await session.commit()

    # 다른 통합 테스트 파일이 새 이벤트 루프용 엔진을 만들 수 있게 정리한다.
    await get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()


def test_pgvector_extension_and_storage() -> None:
    """실제 DB가 vector 타입의 1536차원 값을 저장하고 반환한다."""

    asyncio.run(_run_pgvector_flow())
