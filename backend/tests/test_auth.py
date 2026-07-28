"""회원가입·로그인·현재 사용자 API 계약을 외부 DB 없이 검증한다."""

import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_auth_service, get_current_user
from app.main import app
from app.services.auth_service import AuthTokens

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

    async def login(self, email: str, password: str) -> AuthTokens:
        return AuthTokens(
            access_token="signed.test.token",
            refresh_token="opaque-refresh-token",
        )

    async def refresh(self, refresh_token: str) -> AuthTokens:
        assert refresh_token == "opaque-refresh-token"
        return AuthTokens(
            access_token="renewed.test.token",
            refresh_token="rotated-refresh-token",
        )

    async def logout(self, refresh_token: str) -> None:
        assert refresh_token in {
            "opaque-refresh-token",
            "rotated-refresh-token",
        }


def override_auth_service() -> FakeAuthService:
    return FakeAuthService()


async def override_current_user() -> SimpleNamespace:
    return make_user()


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """이 모듈을 실행할 때만 가짜 인증 의존성을 적용해 다른 통합 테스트와 격리한다."""

    app.dependency_overrides[get_auth_service] = override_auth_service
    app.dependency_overrides[get_current_user] = override_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_auth_service, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_register_returns_public_user(client: TestClient) -> None:
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


def test_login_returns_bearer_token(client: TestClient) -> None:
    """로그인 결과와 JavaScript가 읽을 수 없는 refresh 쿠키를 확인한다."""

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
    set_cookie = response.headers["set-cookie"]
    assert "character_chat_refresh=opaque-refresh-token" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/auth" in set_cookie


def test_refresh_rotates_cookie_and_returns_new_access_token(
    client: TestClient,
) -> None:
    """refresh endpoint가 access token과 refresh 쿠키를 모두 교체하는지 확인한다."""

    client.cookies.set(
        "character_chat_refresh",
        "opaque-refresh-token",
        path="/auth",
    )
    response = client.post("/auth/refresh")

    assert response.status_code == 200
    assert response.json()["access_token"] == "renewed.test.token"
    assert "character_chat_refresh=rotated-refresh-token" in response.headers[
        "set-cookie"
    ]


def test_logout_clears_refresh_cookie(client: TestClient) -> None:
    """로그아웃이 서버 폐기를 요청하고 브라우저 쿠키를 만료시키는지 확인한다."""

    client.cookies.set(
        "character_chat_refresh",
        "rotated-refresh-token",
        path="/auth",
    )
    response = client.post("/auth/logout")

    assert response.status_code == 204
    assert "character_chat_refresh=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_read_current_user(client: TestClient) -> None:
    """현재 사용자 endpoint가 인증 의존성의 사용자를 반환하는지 확인한다."""

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "learner@example.com"
