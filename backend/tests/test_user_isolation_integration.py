"""PostgreSQL에서 사용자별 데이터 격리가 실제로 지켜지는지 검증한다."""

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Sequence

import pytest

from app.db.session import get_engine, get_session_factory
from app.schemas.character import CharacterCreate
from app.schemas.memory import MemoryCreate
from app.schemas.user import UserCreate
from app.services.auth_service import AuthService
from app.services.character_service import (
    CharacterAccessDeniedError,
    CharacterNotFoundError,
    CharacterService,
)
from app.services.chat_service import ChatService, ConversationNotFoundError
from app.services.llm_service import LLMMessage
from app.services.memory_service import MemoryNotFoundError, MemoryService


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="RUN_DB_INTEGRATION=1일 때만 PostgreSQL 통합 테스트를 실행한다.",
)


class StaticLLMProvider:
    """권한 테스트에서 외부 LLM 호출을 제거하기 위한 최소 provider."""

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> str:
        """입력과 무관하게 고정 답변을 반환한다."""

        return "격리 테스트 응답입니다."

    async def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> AsyncGenerator[str, None]:
        """Protocol 충족용 스트림 구현. 이 테스트에서는 사용하지 않는다."""

        yield "격리"


async def _create_user(email_prefix: str):
    """고유 이메일로 테스트 사용자를 만들고 ORM user 객체를 반환한다."""

    session_factory = get_session_factory()
    async with session_factory() as session:
        return await AuthService(session).register(
            UserCreate(
                email=f"{email_prefix}-{uuid.uuid4().hex}@example.com",
                password="strong-password",
            ),
        )


async def _run_user_isolation_flow() -> None:
    """사용자 A의 리소스를 사용자 B가 읽거나 이어갈 수 없는지 확인한다."""

    try:
        # 서로 다른 두 사용자를 실제 users 테이블에 만든다.
        owner = await _create_user("owner")
        stranger = await _create_user("stranger")

        # 사용자가 다르더라도 같은 DB에 저장되므로 소유권 조건이 반드시 필요하다.
        session_factory = get_session_factory()
        async with session_factory() as session:
            # 1) owner가 자기 캐릭터를 만든다.
            owner_character = await CharacterService(session, user_id=owner.id).create(
                CharacterCreate(
                    name="소유자 캐릭터",
                    description="다른 사용자가 볼 수 없어야 하는 캐릭터",
                ),
            )

            # 2) owner가 해당 캐릭터에 연결된 장기 기억을 만든다.
            owner_memory = await MemoryService(session, user_id=owner.id).create(
                MemoryCreate(
                    content="소유자만 접근해야 하는 기억",
                    character_id=owner_character.id,
                    importance=5,
                ),
            )

            # 3) owner가 해당 캐릭터와 대화방을 만든다.
            owner_chat = ChatService(
                session,
                StaticLLMProvider(),
                user_id=owner.id,
                history_limit=20,
                memory_limit=10,
            )
            owner_result = await owner_chat.reply(
                "이 대화는 소유자만 이어가야 합니다.",
                conversation_id=None,
                character_id=owner_character.id,
            )

            # 4) stranger는 owner의 캐릭터를 상세 조회할 수 없어야 한다.
            with pytest.raises(CharacterAccessDeniedError):
                await CharacterService(session, user_id=stranger.id).get(
                    owner_character.id,
                )

            # 5) stranger는 owner의 캐릭터에 기억을 연결할 수도 없어야 한다.
            with pytest.raises(CharacterNotFoundError):
                await MemoryService(session, user_id=stranger.id).create(
                    MemoryCreate(
                        content="다른 사람 캐릭터에 몰래 붙이려는 기억",
                        character_id=owner_character.id,
                        importance=1,
                    ),
                )

            # 6) stranger는 owner의 기억을 직접 ID로 조회해도 찾을 수 없어야 한다.
            with pytest.raises(MemoryNotFoundError):
                await MemoryService(session, user_id=stranger.id).get(owner_memory.id)

            # 7) stranger는 owner의 conversation_id를 알아도 대화를 이어갈 수 없어야 한다.
            stranger_chat = ChatService(
                session,
                StaticLLMProvider(),
                user_id=stranger.id,
                history_limit=20,
                memory_limit=10,
            )
            with pytest.raises(ConversationNotFoundError):
                await stranger_chat.start_turn(
                    "다른 사람 대화방을 이어가려는 메시지",
                    conversation_id=owner_result.conversation_id,
                    character_id=None,
                )
    finally:
        # 테스트 간 이벤트 루프가 달라도 asyncpg 연결이 섞이지 않게 엔진을 닫는다.
        await get_engine().dispose()
        # 다음 테스트가 새 루프에 맞는 엔진과 세션 팩토리를 만들도록 캐시를 비운다.
        get_session_factory.cache_clear()
        get_engine.cache_clear()


def test_user_owned_resources_are_isolated_with_postgres() -> None:
    """실제 PostgreSQL에서 사용자 A의 데이터가 사용자 B에게 격리되는지 확인한다."""

    asyncio.run(_run_user_isolation_flow())
