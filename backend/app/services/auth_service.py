"""회원가입, 로그인, 세션 갱신 유스케이스를 처리한다."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.repositories.refresh_session_repository import RefreshSessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate


class UserAlreadyExistsError(ValueError):
    """같은 이메일로 다시 가입하려 할 때 발생한다."""


class InvalidCredentialsError(ValueError):
    """이메일이나 비밀번호가 일치하지 않을 때 발생한다."""


class InactiveUserError(PermissionError):
    """비활성 사용자의 로그인 또는 API 접근을 차단한다."""


class AuthPersistenceError(RuntimeError):
    """인증 과정의 DB 오류를 공통 예외로 감싼다."""


class InvalidRefreshTokenError(ValueError):
    """refresh token이 없거나 만료되었거나 DB에 존재하지 않을 때 발생한다."""


class RefreshTokenReuseError(PermissionError):
    """이미 회전된 refresh token이 다시 사용되었을 때 발생한다."""


@dataclass(frozen=True)
class AuthTokens:
    """응답용 access token과 쿠키용 refresh token을 함께 운반한다."""

    access_token: str
    refresh_token: str


def normalize_email(email: str) -> str:
    """이메일 비교와 unique 제약이 대소문자 차이로 우회되지 않게 정규화한다."""

    return email.strip().lower()


class AuthService:
    """비밀번호 원문을 repository에 넘기지 않는 인증 서비스."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._refresh_sessions = RefreshSessionRepository(session)
        self._settings = get_settings()

    async def register(self, data: UserCreate) -> User:
        """이메일 중복을 확인하고 Argon2 해시만 DB에 저장한다."""

        email = normalize_email(str(data.email))
        try:
            if await self._users.get_by_email(email) is not None:
                raise UserAlreadyExistsError(email)

            user = await self._users.create(
                email=email,
                hashed_password=hash_password(data.password),
            )
            await self._session.commit()
            await self._session.refresh(user)
            return user
        except UserAlreadyExistsError:
            raise
        except IntegrityError as exc:
            # 동시 가입 요청의 race condition도 DB unique 제약으로 막는다.
            await self._session.rollback()
            raise UserAlreadyExistsError(email) from exc
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise AuthPersistenceError("Failed to register user") from exc

    async def login(self, email: str, password: str) -> AuthTokens:
        """자격 증명을 확인하고 access/refresh token 한 쌍을 발급한다."""

        normalized_email = normalize_email(email)
        try:
            user = await self._users.get_by_email(normalized_email)
        except SQLAlchemyError as exc:
            raise AuthPersistenceError("Failed to load user") from exc

        if user is None:
            # 존재하지 않는 사용자도 실제 Argon2 검증을 한 번 수행한다.
            verify_password(password, DUMMY_PASSWORD_HASH)
            raise InvalidCredentialsError(normalized_email)
        if not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError(normalized_email)
        if not user.is_active:
            raise InactiveUserError(normalized_email)

        # 브라우저에는 원문을, DB에는 SHA-256 해시만 저장해 DB 유출 피해를 줄인다.
        refresh_token = create_refresh_token()
        now = datetime.now(timezone.utc)
        try:
            await self._refresh_sessions.create(
                user_id=user.id,
                family_id=uuid.uuid4(),
                token_hash=hash_refresh_token(refresh_token),
                expires_at=now
                + timedelta(days=self._settings.refresh_token_expire_days),
            )
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise AuthPersistenceError("Failed to create refresh session") from exc

        return AuthTokens(
            access_token=create_access_token(user.id),
            refresh_token=refresh_token,
        )

    async def refresh(self, refresh_token: str) -> AuthTokens:
        """refresh token을 한 번만 사용하고 같은 family의 새 token으로 회전한다."""

        now = datetime.now(timezone.utc)
        try:
            current = await self._refresh_sessions.get_for_update(
                hash_refresh_token(refresh_token)
            )
            if current is None:
                raise InvalidRefreshTokenError("Unknown refresh token")

            if current.revoked_at is not None:
                # 이미 쓴 token의 재사용은 탈취 신호이므로 같은 로그인 family를 모두 폐기한다.
                await self._refresh_sessions.revoke_family(current.family_id, now)
                await self._session.commit()
                raise RefreshTokenReuseError("Refresh token was already used")

            if current.expires_at <= now:
                current.revoked_at = now
                await self._session.commit()
                raise InvalidRefreshTokenError("Expired refresh token")

            user = await self._users.get(current.user_id)
            if user is None:
                current.revoked_at = now
                await self._session.commit()
                raise InvalidRefreshTokenError("Refresh token user is missing")
            if not user.is_active:
                await self._refresh_sessions.revoke_family(current.family_id, now)
                await self._session.commit()
                raise InactiveUserError(str(user.id))

            next_refresh_token = create_refresh_token()
            current.revoked_at = now
            await self._refresh_sessions.create(
                user_id=user.id,
                family_id=current.family_id,
                token_hash=hash_refresh_token(next_refresh_token),
                expires_at=now
                + timedelta(days=self._settings.refresh_token_expire_days),
            )
            await self._session.commit()
            return AuthTokens(
                access_token=create_access_token(user.id),
                refresh_token=next_refresh_token,
            )
        except (
            InactiveUserError,
            InvalidRefreshTokenError,
            RefreshTokenReuseError,
        ):
            raise
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise AuthPersistenceError("Failed to rotate refresh token") from exc

    async def logout(self, refresh_token: str) -> None:
        """현재 refresh token이 속한 로그인 family 전체를 폐기한다."""

        now = datetime.now(timezone.utc)
        try:
            current = await self._refresh_sessions.get_for_update(
                hash_refresh_token(refresh_token)
            )
            # 모르는 token도 성공으로 처리해 token 존재 여부를 외부에 노출하지 않는다.
            if current is not None:
                await self._refresh_sessions.revoke_family(current.family_id, now)
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise AuthPersistenceError("Failed to revoke refresh session") from exc
