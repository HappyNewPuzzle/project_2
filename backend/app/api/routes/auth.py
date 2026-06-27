"""회원가입, 로그인, 현재 사용자 조회 API."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import AuthServiceDependency, CurrentUserDependency
from app.schemas.user import TokenResponse, UserCreate, UserResponse
from app.services.auth_service import (
    AuthPersistenceError,
    InactiveUserError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: UserCreate,
    service: AuthServiceDependency,
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
    service: AuthServiceDependency,
) -> TokenResponse:
    """OAuth2 password form의 username 필드를 이메일로 사용해 JWT를 발급한다."""

    try:
        token = await service.login(form.username, form.password)
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
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def read_current_user(
    current_user: CurrentUserDependency,
) -> UserResponse:
    """Bearer 토큰으로 인증된 현재 사용자 정보를 반환한다."""

    return UserResponse.model_validate(current_user)
