"""자동 embedding, pgvector 검색, 사용자·캐릭터 격리를 실제 DB에서 검증한다."""

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Sequence

import pytest

from app.db.models import Character, Memory, User
from app.db.session import get_engine, get_session_factory
from app.schemas.memory import MemoryCreate, MemoryUpdate
from app.services.llm_service import LLMMessage
from app.services.memory_extraction_service import MemoryExtractionService
from app.services.memory_service import MemoryService


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="RUN_DB_INTEGRATION=1일 때만 PostgreSQL 통합 테스트를 실행한다.",
)


class SemanticTestEmbeddingProvider:
    """키워드별 축이 다른 1536차원 벡터를 만드는 결정적 테스트 provider."""

    provider_name = "semantic-test:1536"

    async def embed(self, text: str) -> list[float]:
        vector = [0.0] * 1536
        normalized = text.lower()
        if "astronomy" in normalized:
            vector[0] = 1.0
        elif "cooking" in normalized:
            vector[1] = 1.0
        else:
            vector[2] = 1.0
        return vector


class ExtractedMemoryLLMProvider:
    """자동 추출 서비스에 검색 가능한 기억 JSON을 반환한다."""

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> str:
        return (
            '{"memories":[{"content":"The user studies astronomy",'
            '"importance":5}]}'
        )

    async def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> AsyncGenerator[str, None]:
        yield ""


async def _run_memory_search_flow() -> None:
    """기억 생성부터 범위 검색, 수정 재색인, 기존 데이터 재색인을 확인한다."""

    session_factory = get_session_factory()
    provider = SemanticTestEmbeddingProvider()
    async with session_factory() as session:
        owner = User(
            email=f"memory-owner-{uuid.uuid4().hex}@example.com",
            hashed_password="integration-test",
        )
        stranger = User(
            email=f"memory-stranger-{uuid.uuid4().hex}@example.com",
            hashed_password="integration-test",
        )
        session.add_all([owner, stranger])
        await session.flush()
        active_character = Character(
            owner_id=owner.id,
            name="Active character",
            description="",
            personality="",
            speaking_style="",
            system_prompt="",
        )
        other_character = Character(
            owner_id=owner.id,
            name="Other character",
            description="",
            personality="",
            speaking_style="",
            system_prompt="",
        )
        session.add_all([active_character, other_character])
        await session.commit()

        owner_service = MemoryService(
            session,
            user_id=owner.id,
            embedding_provider=provider,
        )
        astronomy = await owner_service.create(
            MemoryCreate(
                content="The user enjoys astronomy",
                character_id=active_character.id,
                importance=5,
            )
        )
        global_memory = await owner_service.create(
            MemoryCreate(
                content="Astronomy is a global preference",
                importance=4,
            )
        )
        other_scope = await owner_service.create(
            MemoryCreate(
                content="Astronomy for another character",
                character_id=other_character.id,
                importance=5,
            )
        )
        editable = await owner_service.create(
            MemoryCreate(
                content="The user practices cooking",
                character_id=active_character.id,
            )
        )
        inactive = await owner_service.create(
            MemoryCreate(
                content="Old astronomy memory",
                character_id=active_character.id,
            )
        )
        await owner_service.update(
            inactive.id,
            MemoryUpdate(is_active=False),
        )

        stranger_service = MemoryService(
            session,
            user_id=stranger.id,
            embedding_provider=provider,
        )
        stranger_memory = await stranger_service.create(
            MemoryCreate(content="The stranger enjoys astronomy")
        )

        # 캐릭터 검색에는 전역+해당 캐릭터만 포함하고 타 사용자와 비활성 기억은 제외한다.
        matches = await owner_service.search(
            "astronomy",
            character_id=active_character.id,
            limit=10,
        )
        result_ids = {match.memory.id for match in matches}
        assert astronomy.id in result_ids
        assert global_memory.id in result_ids
        assert editable.id in result_ids
        assert other_scope.id not in result_ids
        assert inactive.id not in result_ids
        assert stranger_memory.id not in result_ids
        assert matches[0].score == pytest.approx(1.0)

        # 내용 수정은 같은 트랜잭션에서 embedding도 바꾸므로 즉시 검색 순위에 반영된다.
        await owner_service.update(
            editable.id,
            MemoryUpdate(content="The user now studies astronomy"),
        )
        updated_matches = await owner_service.search(
            "astronomy",
            character_id=active_character.id,
            limit=10,
        )
        updated = next(
            match for match in updated_matches if match.memory.id == editable.id
        )
        assert updated.score == pytest.approx(1.0)

        # 과거 버전처럼 embedding 없는 기억은 재색인 API 대상이 된다.
        legacy = Memory(
            user_id=owner.id,
            content="Legacy astronomy memory",
            importance=3,
        )
        session.add(legacy)
        await session.commit()
        assert await owner_service.reindex(limit=10) == 1

        # 자동 추출된 기억도 저장과 동시에 embedding이 생성되어 검색된다.
        extracted_count = await MemoryExtractionService(
            session,
            ExtractedMemoryLLMProvider(),
            user_id=owner.id,
            max_items=2,
            embedding_provider=provider,
        ).extract_and_store(
            user_message="I study astronomy",
            assistant_reply="I will remember that.",
            character_id=active_character.id,
        )
        assert extracted_count == 1
        final_matches = await owner_service.search(
            "astronomy",
            character_id=active_character.id,
            limit=20,
        )
        assert any(
            match.memory.content == "The user studies astronomy"
            for match in final_matches
        )

        # 캐릭터 FK는 RESTRICT이므로 캐릭터를 먼저 지운 뒤 테스트 사용자를 정리한다.
        await session.delete(active_character)
        await session.delete(other_character)
        await session.flush()
        # 사용자 삭제 시 남은 전역 기억과 embedding은 FK CASCADE로 함께 정리된다.
        await session.delete(owner)
        await session.delete(stranger)
        await session.commit()

    await get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()


def test_memory_embedding_search_and_scope() -> None:
    """실제 pgvector DB에서 기억의 전체 의미 검색 흐름을 검증한다."""

    asyncio.run(_run_memory_search_flow())
