"""비밀번호 해시와 JWT round-trip을 검증하는 보안 유틸리티 테스트."""

import uuid

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_verified() -> None:
    """원문과 다른 Argon2 해시가 올바른 비밀번호만 허용하는지 확인한다."""

    password = "correct horse battery staple"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong password", hashed)


def test_access_token_round_trip() -> None:
    """JWT subject에서 원래 사용자 UUID를 복구할 수 있는지 확인한다."""

    user_id = uuid.UUID("77777777-7777-7777-7777-777777777777")

    token = create_access_token(user_id)

    assert decode_access_token(token) == user_id
