"""회원가입, 로그인, 현재 사용자 조회 API."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import (
    AuthRateLimitDependency,
    AuthServiceDependency,
    CurrentUserDependency,
)
from app.core.config import get_settings
from app.schemas.user import TokenResponse, UserCreate, UserResponse
from app.services.auth_service import (
    AuthPersistenceError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshTokenReuseError,
    UserAlreadyExistsError,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """JavaScript가 읽지 못하는 쿠키에 refresh token을 저장한다."""

    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path="/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    """발급 때와 같은 경로 속성으로 브라우저의 refresh 쿠키를 삭제한다."""

    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path="/auth",
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite=settings.refresh_cookie_samesite,
    )


def refresh_cookie_delete_header() -> str:
    """HTTPException 응답에도 쿠키 삭제 header를 전달할 수 있게 만든다."""

    response = Response()
    clear_refresh_cookie(response)
    return response.headers["set-cookie"]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: UserCreate,
    service: AuthServiceDependency,
    _rate_limit: AuthRateLimitDependency,
) -> UserResponse:
    """새 계정을 만들되 응답에는 비밀번호 해시를 포함하지 않는다."""

    try:
        user = await service.register(payload)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        ) from exc
    except AuthPersistenceError as exc:
        logger.exception("User registration failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User could not be registered.",
        ) from exc
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    response: Response,
    service: AuthServiceDependency,
    _rate_limit: AuthRateLimitDependency,
) -> TokenResponse:
    """OAuth2 password form의 username 필드를 이메일로 사용해 JWT를 발급한다."""

    try:
        tokens = await service.login(form.username, form.password)
    except (InvalidCredentialsError, InactiveUserError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except AuthPersistenceError as exc:
        logger.exception("User login failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        ) from exc
    set_refresh_cookie(response, tokens.refresh_token)
    return TokenResponse(access_token=tokens.access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    request: Request,
    response: Response,
    service: AuthServiceDependency,
    _rate_limit: AuthRateLimitDependency,
) -> TokenResponse:
    """HttpOnly 쿠키를 회전하고 새로운 짧은 수명의 access token을 반환한다."""

    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is missing.",
        )
    try:
        tokens = await service.refresh(refresh_token)
    except (
        InactiveUserError,
        InvalidRefreshTokenError,
        RefreshTokenReuseError,
    ) as exc:
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh session is invalid.",
            headers={"Set-Cookie": refresh_cookie_delete_header()},
        ) from exc
    except AuthPersistenceError as exc:
        logger.exception("Refresh token rotation failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        ) from exc

    set_refresh_cookie(response, tokens.refresh_token)
    return TokenResponse(access_token=tokens.access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    service: AuthServiceDependency,
) -> None:
    """서버 세션 family를 폐기하고 브라우저 refresh 쿠키도 제거한다."""

    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    try:
        if refresh_token:
            await service.logout(refresh_token)
    except AuthPersistenceError as exc:
        logger.exception("Logout session revocation failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        ) from exc
    clear_refresh_cookie(response)


@router.get("/me", response_model=UserResponse)
async def read_current_user(
    current_user: CurrentUserDependency,
) -> UserResponse:
    """Bearer 토큰으로 인증된 현재 사용자 정보를 반환한다."""

    return UserResponse.model_validate(current_user)
