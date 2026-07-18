"""스트리밍 응답의 DB 저장 시점을 실제 PostgreSQL로 검증한다."""

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Sequence

import pytest
from sqlalchemy import select

from app.db.models import Message, MessageRole
from app.db.session import get_engine, get_session_factory
from app.schemas.character import CharacterCreate
from app.schemas.user import UserCreate
from app.services.auth_service import AuthService
from app.services.character_service import CharacterService
from app.services.chat_service import ChatService
from app.services.llm_service import LLMMessage


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="RUN_DB_INTEGRATION=1일 때만 PostgreSQL 통합 테스트를 실행한다.",
)


class SuccessfulStreamingLLMProvider:
    """정상 스트리밍 조각을 순서대로 내보내는 가짜 provider."""

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> str:
        """Protocol 충족용 일반 응답. 이 테스트에서는 사용하지 않는다."""

        return "사용하지 않는 응답"

    async def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> AsyncGenerator[str, None]:
        """세 조각을 정상적으로 끝까지 전달한다."""

        yield "안녕"
        yield ", "
        yield "스트리밍!"


class FailingStreamingLLMProvider:
    """중간에 끊기는 스트리밍 상황을 재현하는 가짜 provider."""

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> str:
        """Protocol 충족용 일반 응답. 이 테스트에서는 사용하지 않는다."""

        return "사용하지 않는 응답"

    async def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> AsyncGenerator[str, None]:
        """첫 조각을 보낸 뒤 외부 LLM 오류처럼 예외를 발생시킨다."""

        yield "불완전"
        raise RuntimeError("stream interrupted")


async def _create_user_and_character() -> tuple[uuid.UUID, uuid.UUID]:
    """스트리밍 테스트에 필요한 사용자와 캐릭터를 실제 DB에 만든다."""

    session_factory = get_session_factory()
    async with session_factory() as session:
        user = await AuthService(session).register(
            UserCreate(
                email=f"stream-{uuid.uuid4().hex}@example.com",
                password="strong-password",
            ),
        )
        character = await CharacterService(session, user_id=user.id).create(
            CharacterCreate(name="스트리머"),
        )
        return user.id, character.id


async def _list_messages(conversation_id: uuid.UUID) -> list[Message]:
    """대화방 메시지를 오래된 순서로 조회한다."""

    session_factory = get_session_factory()
    async with session_factory() as session:
        return list(
            (
                await session.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.asc())
                )
            ).all()
        )


async def _run_successful_streaming_flow() -> None:
    """정상 스트리밍 완료 후 assistant 메시지가 저장되는지 확인한다."""

    user_id, character_id = await _create_user_and_character()
    session_factory = get_session_factory()

    async with session_factory() as session:
        chat = ChatService(
            session,
            SuccessfulStreamingLLMProvider(),
            user_id=user_id,
            history_limit=20,
            memory_limit=10,
        )
        turn = await chat.start_turn(
            "스트리밍으로 말해줘.",
            conversation_id=None,
            character_id=character_id,
        )

        chunks: list[str] = []
        async for delta in chat.stream_reply(turn):
            chunks.append(delta)

        assert chunks == ["안녕", ", ", "스트리밍!"]

    saved_messages = await _list_messages(turn.conversation_id)
    assert [message.role for message in saved_messages] == [
        MessageRole.USER.value,
        MessageRole.ASSISTANT.value,
    ]
    assert saved_messages[1].content == "안녕, 스트리밍!"


async def _run_failed_streaming_flow() -> None:
    """스트리밍 중단 시 불완전한 assistant 메시지를 저장하지 않는지 확인한다."""

    user_id, character_id = await _create_user_and_character()
    session_factory = get_session_factory()

    async with session_factory() as session:
        chat = ChatService(
            session,
            FailingStreamingLLMProvider(),
            user_id=user_id,
            history_limit=20,
            memory_limit=10,
        )
        turn = await chat.start_turn(
            "중간에 실패하는 스트림",
            conversation_id=None,
            character_id=character_id,
        )

        received: list[str] = []
        with pytest.raises(RuntimeError):
            async for delta in chat.stream_reply(turn):
                received.append(delta)

        assert received == ["불완전"]

    saved_messages = await _list_messages(turn.conversation_id)
    assert [message.role for message in saved_messages] == [
        MessageRole.USER.value,
    ]
    assert saved_messages[0].content == "중간에 실패하는 스트림"


async def _run_streaming_persistence_tests() -> None:
    """하나의 이벤트 루프 안에서 성공/실패 스트리밍 저장 정책을 모두 검증한다."""

    try:
        await _run_successful_streaming_flow()
        await _run_failed_streaming_flow()
    finally:
        # asyncpg 연결 풀은 현재 이벤트 루프가 닫히기 전에 정리해야 한다.
        await get_engine().dispose()
        # 다음 통합 테스트 파일이 새 루프에서 새 엔진을 만들 수 있게 캐시를 비운다.
        get_session_factory.cache_clear()
        get_engine.cache_clear()


def test_streaming_persists_only_completed_assistant_messages() -> None:
    """스트리밍 성공/실패 상황의 메시지 저장 정책을 실제 DB로 확인한다."""

    asyncio.run(_run_streaming_persistence_tests())
