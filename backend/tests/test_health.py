"""health endpoint와 요청 ID middleware의 HTTP 계약을 검증한다."""

from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient

from app.db.session import get_db_session
from app.main import app


class FakeSession:
    """readiness에서 SELECT 1 호출만 기록하는 가짜 DB 세션."""

    def __init__(self) -> None:
        self.executed = False

    async def execute(self, statement: object) -> None:
        self.executed = True


fake_session = FakeSession()


async def override_db_session() -> AsyncGenerator[FakeSession, None]:
    yield fake_session


app.dependency_overrides[get_db_session] = override_db_session
client = TestClient(app)


def test_liveness_propagates_request_id() -> None:
    """liveness 응답과 외부 request ID의 응답 헤더 전파를 확인한다."""

    response = client.get(
        "/health/live",
        headers={"X-Request-ID": "test-request-123"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"] == "test-request-123"


def test_readiness_checks_database() -> None:
    """readiness가 실제로 세션 execute를 호출하는지 확인한다."""

    fake_session.executed = False
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert fake_session.executed
