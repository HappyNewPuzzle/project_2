"""비밀번호 해시와 JWT access token 생성·검증을 담당한다."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import get_settings

# 현재 pwdlib 권장 설정은 Argon2이며, 알고리즘 세부값은 라이브러리가 관리한다.
password_hash = PasswordHash.recommended()

# 존재하지 않는 이메일도 비슷한 해시 검증 시간을 사용해 계정 존재 여부 노출을 줄인다.
DUMMY_PASSWORD_HASH = password_hash.hash("not-a-real-user-password")


class InvalidAccessTokenError(ValueError):
    """서명, 만료, subject 형식 중 하나라도 잘못된 토큰."""


def hash_password(password: str) -> str:
    """회원가입 비밀번호를 복원 불가능한 Argon2 문자열로 변환한다."""

    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """입력 비밀번호가 저장된 해시와 일치하는지 안전하게 확인한다."""

    try:
        return password_hash.verify(password, hashed_password)
    except UnknownHashError:
        # 손상되거나 지원하지 않는 해시는 인증 실패로 처리한다.
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    """사용자 UUID와 만료 시각을 담아 HS256 JWT를 서명한다."""

    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        # JWT 표준 subject에는 문자열 형태의 사용자 UUID만 넣는다.
        "sub": str(user_id),
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> uuid.UUID:
    """JWT 서명과 만료를 검증하고 subject를 사용자 UUID로 반환한다."""

    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise InvalidAccessTokenError("Token subject is missing")
        return uuid.UUID(subject)
    except (InvalidTokenError, ValueError, TypeError) as exc:
        raise InvalidAccessTokenError("Invalid access token") from exc
