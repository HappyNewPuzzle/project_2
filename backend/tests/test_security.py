"""비밀번호 해시와 JWT round-trip을 검증하는 보안 유틸리티 테스트."""

import uuid

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
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


def test_refresh_token_is_random_and_only_hash_is_stored() -> None:
    """두 refresh 원문이 다르고 저장용 digest가 원문을 노출하지 않는지 확인한다."""

    first = create_refresh_token()
    second = create_refresh_token()

    assert first != second
    assert len(first) >= 64
    assert hash_refresh_token(first) != first
    assert len(hash_refresh_token(first)) == 64
