"""회원가입과 로그인 유스케이스를 처리한다."""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.models import User
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


def normalize_email(email: str) -> str:
    """이메일 비교와 unique 제약이 대소문자 차이로 우회되지 않게 정규화한다."""

    return email.strip().lower()


class AuthService:
    """비밀번호 원문을 repository에 넘기지 않는 인증 서비스."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

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

    async def login(self, email: str, password: str) -> str:
        """자격 증명을 확인하고 성공하면 짧은 수명의 JWT를 발급한다."""

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
        return create_access_token(user.id)
