from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.services.chat_service import ChatService
from app.services.character_service import CharacterService
from app.services.llm_service import LLMProvider, get_llm_provider

SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
LLMDependency = Annotated[LLMProvider, Depends(get_llm_provider)]


def get_chat_service(
    session: SessionDependency,
    llm: LLMDependency,
) -> ChatService:
    return ChatService(
        session,
        llm,
        history_limit=get_settings().chat_history_limit,
    )


ChatServiceDependency = Annotated[ChatService, Depends(get_chat_service)]


def get_character_service(session: SessionDependency) -> CharacterService:
    return CharacterService(session)


CharacterServiceDependency = Annotated[
    CharacterService,
    Depends(get_character_service),
]
