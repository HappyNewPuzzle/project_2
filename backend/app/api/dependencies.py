"""FastAPI의 Depends로 서비스 객체를 조립하는 의존성 모음."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.rate_limit import get_rate_limiter
from app.core.security import InvalidAccessTokenError, decode_access_token
from app.db.models import User
from app.db.session import get_db_session
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.character_service import CharacterService
from app.services.conversation_service import ConversationService
from app.services.llm_service import LLMProvider, get_llm_provider
from app.services.memory_service import MemoryService

# 타입 별칭에 Depends를 함께 넣으면 라우터 함수의 매개변수가 간결해진다.
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
LLMDependency = Annotated[LLMProvider, Depends(get_llm_provider)]

# Swagger UI의 Authorize 버튼과 Authorization: Bearer 헤더 파싱을 함께 제공한다.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
TokenDependency = Annotated[str, Depends(oauth2_scheme)]


def get_auth_service(session: SessionDependency) -> AuthService:
    """요청별 DB 세션으로 인증 서비스를 만든다."""

    return AuthService(session)


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(
    token: TokenDependency,
    session: SessionDependency,
) -> User:
    """JWT를 검증하고 DB에서 현재 활성 사용자를 조회한다."""

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_access_token(token)
    except InvalidAccessTokenError as exc:
        raise credentials_error from exc

    try:
        user = await UserRepository(session).get(user_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        ) from exc

    if user is None:
        raise credentials_error
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user.",
        )
    return user


CurrentUserDependency = Annotated[User, Depends(get_current_user)]


def _enforce_rate_limit(key: str, *, limit: int) -> None:
    """공통 제한기를 호출하고 초과 요청을 HTTP 429로 변환한다."""

    result = get_rate_limiter().check(key, limit=limit)
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests.",
            headers={"Retry-After": str(result.retry_after_seconds)},
        )


def enforce_auth_rate_limit(request: Request) -> None:
    """회원가입·로그인을 클라이언트 IP 기준으로 제한한다."""

    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    _enforce_rate_limit(
        f"auth:{client_ip}",
        limit=settings.auth_rate_limit_per_minute,
    )


AuthRateLimitDependency = Annotated[
    None,
    Depends(enforce_auth_rate_limit),
]


def enforce_chat_rate_limit(current_user: CurrentUserDependency) -> None:
    """LLM 비용이 발생하는 채팅을 현재 사용자 UUID 기준으로 제한한다."""

    settings = get_settings()
    _enforce_rate_limit(
        f"chat:{current_user.id}",
        limit=settings.chat_rate_limit_per_minute,
    )


ChatRateLimitDependency = Annotated[
    None,
    Depends(enforce_chat_rate_limit),
]


def get_chat_service(
    session: SessionDependency,
    llm: LLMDependency,
    current_user: CurrentUserDependency,
    _rate_limit: ChatRateLimitDependency,
) -> ChatService:
    """한 DB 세션과 LLM provider를 묶어 요청 전용 ChatService를 만든다."""

    return ChatService(
        session,
        llm,
        user_id=current_user.id,
        history_limit=get_settings().chat_history_limit,
        memory_limit=get_settings().chat_memory_limit,
    )


ChatServiceDependency = Annotated[ChatService, Depends(get_chat_service)]


def get_character_service(
    session: SessionDependency,
    current_user: CurrentUserDependency,
) -> CharacterService:
    """같은 요청의 DB 세션을 사용하는 CharacterService를 만든다."""

    return CharacterService(session, user_id=current_user.id)


CharacterServiceDependency = Annotated[
    CharacterService,
    Depends(get_character_service),
]


def get_memory_service(
    session: SessionDependency,
    current_user: CurrentUserDependency,
) -> MemoryService:
    """현재 사용자 범위로 제한된 장기 기억 서비스를 만든다."""

    return MemoryService(session, user_id=current_user.id)


MemoryServiceDependency = Annotated[MemoryService, Depends(get_memory_service)]


def get_conversation_service(
    session: SessionDependency,
    current_user: CurrentUserDependency,
) -> ConversationService:
    """현재 사용자 범위로 제한된 대화방 조회 서비스를 만든다."""

    return ConversationService(session, user_id=current_user.id)


ConversationServiceDependency = Annotated[
    ConversationService,
    Depends(get_conversation_service),
]
