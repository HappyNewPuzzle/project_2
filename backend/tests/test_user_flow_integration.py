"""PostgreSQL을 사용하는 실제 사용자 흐름 통합 테스트.

이 파일은 평소 빠른 `pytest`에서는 건너뛰고, CI의 PostgreSQL service container가
준비된 `RUN_DB_INTEGRATION=1` 환경에서만 실행한다.
"""

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Sequence

import pytest
from sqlalchemy import select

from app.core.security import hash_refresh_token
from app.db.models import Message, MessageRole, RefreshSession
from app.db.session import get_engine, get_session_factory
from app.schemas.character import CharacterCreate
from app.schemas.memory import MemoryCreate
from app.schemas.user import UserCreate
from app.services.auth_service import AuthService, RefreshTokenReuseError
from app.services.character_service import CharacterService
from app.services.chat_service import ChatService
from app.services.llm_service import LLMMessage
from app.services.memory_service import MemoryService


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="RUN_DB_INTEGRATION=1일 때만 PostgreSQL 통합 테스트를 실행한다.",
)


class RecordingLLMProvider:
    """외부 API 비용 없이 ChatService가 넘긴 프롬프트 재료를 기록하는 가짜 LLM."""

    def __init__(self) -> None:
        # 마지막 generate 호출의 messages를 테스트에서 검증하기 위해 보관한다.
        self.messages: Sequence[LLMMessage] = ()
        # 마지막 generate 호출의 instructions도 함께 보관한다.
        self.instructions = ""

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> str:
        """LLM 호출 대신 입력을 기록하고 고정 답변을 반환한다."""

        self.messages = messages
        self.instructions = instructions
        return "안녕하세요, 저는 루나예요."

    async def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> AsyncGenerator[str, None]:
        """Protocol 충족용 스트림 구현. 이 테스트에서는 사용하지 않는다."""

        yield "안녕하세요"


async def _run_user_flow() -> None:
    """회원가입부터 채팅 저장까지 실제 DB 세션 하나로 이어서 검증한다."""

    # CI에서 이미 migration이 적용된 PostgreSQL에 연결하는 세션 팩토리를 가져온다.
    session_factory = get_session_factory()

    try:
        # 세션은 요청 한 건처럼 열고, 테스트가 끝나면 자동으로 닫히게 한다.
        async with session_factory() as session:
            # 매번 다른 이메일을 사용해 로컬에서 여러 번 실행해도 unique 충돌을 피한다.
            email = f"flow-{uuid.uuid4().hex}@example.com"
            password = "strong-password"

            # 1) 실제 AuthService로 회원가입하고 DB에 user가 저장되는지 확인한다.
            user = await AuthService(session).register(
                UserCreate(email=email, password=password),
            )
            assert user.email == email

            # 2) 같은 계정으로 로그인해 access/refresh token 쌍이 발급되는지 확인한다.
            tokens = await AuthService(session).login(email, password)
            assert tokens.access_token
            assert tokens.refresh_token

            # 3) refresh token을 회전하면 같은 family 안에 새 세션이 생긴다.
            rotated_tokens = await AuthService(session).refresh(tokens.refresh_token)
            assert rotated_tokens.access_token
            assert rotated_tokens.refresh_token != tokens.refresh_token

            refresh_rows = (
                await session.scalars(
                    select(RefreshSession).where(
                        RefreshSession.user_id == user.id
                    )
                )
            ).all()
            assert len(refresh_rows) == 2
            original_row = next(
                row
                for row in refresh_rows
                if row.token_hash == hash_refresh_token(tokens.refresh_token)
            )
            rotated_row = next(
                row
                for row in refresh_rows
                if row.token_hash
                == hash_refresh_token(rotated_tokens.refresh_token)
            )
            assert original_row.revoked_at is not None
            assert rotated_row.revoked_at is None

            # 4) 이미 쓴 token을 재사용하면 탈취로 보고 family 전체가 폐기된다.
            with pytest.raises(RefreshTokenReuseError):
                await AuthService(session).refresh(tokens.refresh_token)
            await session.refresh(rotated_row)
            assert rotated_row.revoked_at is not None

            # 5) 실제 CharacterService로 사용자 소유 캐릭터를 만든다.
            character = await CharacterService(session, user_id=user.id).create(
                CharacterCreate(
                    name="루나",
                    description="달빛 도서관의 사서",
                    personality="차분하고 호기심이 많다",
                    speaking_style="부드럽고 간결하게 말한다",
                    system_prompt="가끔 달과 책에 관한 비유를 사용한다",
                ),
            )
            assert character.owner_id == user.id

            # 6) 실제 MemoryService로 캐릭터에 연결된 장기 기억을 저장한다.
            memory = await MemoryService(session, user_id=user.id).create(
                MemoryCreate(
                    content="사용자는 천문학을 좋아한다",
                    character_id=character.id,
                    importance=5,
                ),
            )
            assert memory.character_id == character.id

            # 7) 실제 ChatService에 가짜 LLM을 주입해 저장과 문맥 조립을 검증한다.
            llm = RecordingLLMProvider()
            chat = ChatService(
                session,
                llm,
                user_id=user.id,
                history_limit=20,
                memory_limit=10,
            )
            result = await chat.reply(
                "안녕! 나를 기억해줘.",
                conversation_id=None,
                character_id=character.id,
            )

            # 8) 응답에는 새 대화방 ID, 캐릭터 ID, 가짜 LLM 답변이 포함되어야 한다.
            assert result.character_id == character.id
            assert result.reply == "안녕하세요, 저는 루나예요."

            # 9) 캐릭터 instructions가 LLM 호출 경계까지 전달되는지 확인한다.
            assert "You are roleplaying as 루나." in llm.instructions
            assert "달빛 도서관의 사서" in llm.instructions

            # 10) 장기 기억이 최근 대화 앞의 user 문맥으로 들어갔는지 확인한다.
            assert llm.messages[0].role == "user"
            assert "사용자는 천문학을 좋아한다" in llm.messages[0].content
            assert llm.messages[-1].content == "안녕! 나를 기억해줘."

            # 11) DB에는 사용자 메시지와 assistant 메시지가 모두 저장되어야 한다.
            saved_messages = (
                await session.scalars(
                    select(Message)
                    .where(Message.conversation_id == result.conversation_id)
                    .order_by(Message.created_at.asc())
                )
            ).all()
            assert [message.role for message in saved_messages] == [
                MessageRole.USER.value,
                MessageRole.ASSISTANT.value,
            ]
            assert saved_messages[0].content == "안녕! 나를 기억해줘."
            assert saved_messages[1].content == "안녕하세요, 저는 루나예요."
    finally:
        # asyncpg 연결은 이벤트 루프에 묶이므로 테스트 종료 전에 풀을 명시적으로 닫는다.
        await get_engine().dispose()
        # 다음 통합 테스트가 새 이벤트 루프에서 새 엔진을 만들 수 있게 캐시를 비운다.
        get_session_factory.cache_clear()
        get_engine.cache_clear()


def test_register_login_character_memory_chat_flow_with_postgres() -> None:
    """실제 PostgreSQL 위에서 핵심 사용자 흐름이 끝까지 이어지는지 확인한다."""

    asyncio.run(_run_user_flow())
