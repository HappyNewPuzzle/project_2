"""FastAPI의 Depends로 서비스 객체를 조립하는 의존성 모음."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.services.chat_service import ChatService
from app.services.character_service import CharacterService
from app.services.llm_service import LLMProvider, get_llm_provider

# 타입 별칭에 Depends를 함께 넣으면 라우터 함수의 매개변수가 간결해진다.
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
LLMDependency = Annotated[LLMProvider, Depends(get_llm_provider)]


def get_chat_service(
    session: SessionDependency,
    llm: LLMDependency,
) -> ChatService:
    """한 DB 세션과 LLM provider를 묶어 요청 전용 ChatService를 만든다."""

    return ChatService(
        session,
        llm,
        history_limit=get_settings().chat_history_limit,
    )


ChatServiceDependency = Annotated[ChatService, Depends(get_chat_service)]


def get_character_service(session: SessionDependency) -> CharacterService:
    """같은 요청의 DB 세션을 사용하는 CharacterService를 만든다."""

    return CharacterService(session)


CharacterServiceDependency = Annotated[
    CharacterService,
    Depends(get_character_service),
]
