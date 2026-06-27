"""회원가입·로그인·현재 사용자 API 계약을 외부 DB 없이 검증한다."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dependencies import get_auth_service, get_current_user
from app.main import app

USER_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")


def make_user() -> SimpleNamespace:
    """응답 스키마가 읽을 수 있는 테스트 사용자 객체를 만든다."""

    return SimpleNamespace(
        id=USER_ID,
        email="learner@example.com",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


class FakeAuthService:
    """DB와 Argon2 연산 없이 인증 라우터 응답만 검증한다."""

    async def register(self, payload: object) -> SimpleNamespace:
        return make_user()

    async def login(self, email: str, password: str) -> str:
        return "signed.test.token"


def override_auth_service() -> FakeAuthService:
    return FakeAuthService()


async def override_current_user() -> SimpleNamespace:
    return make_user()


app.dependency_overrides[get_auth_service] = override_auth_service
app.dependency_overrides[get_current_user] = override_current_user
client = TestClient(app)


def test_register_returns_public_user() -> None:
    """회원가입 응답에 비밀번호나 해시가 노출되지 않는지 확인한다."""

    response = client.post(
        "/auth/register",
        json={
            "email": "learner@example.com",
            "password": "strong-password",
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == str(USER_ID)
    assert "password" not in response.json()
    assert "hashed_password" not in response.json()


def test_login_returns_bearer_token() -> None:
    """OAuth2 form 로그인 결과가 Bearer token 형식인지 확인한다."""

    response = client.post(
        "/auth/login",
        data={
            "username": "learner@example.com",
            "password": "strong-password",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "signed.test.token",
        "token_type": "bearer",
    }


def test_read_current_user() -> None:
    """현재 사용자 endpoint가 인증 의존성의 사용자를 반환하는지 확인한다."""

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "learner@example.com"
