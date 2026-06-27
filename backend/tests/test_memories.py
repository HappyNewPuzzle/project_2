"""가짜 MemoryService로 장기 기억 REST API 계약을 검증한다."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dependencies import get_memory_service
from app.main import app

MEMORY_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


def make_memory() -> SimpleNamespace:
    """MemoryResponse가 직렬화할 수 있는 테스트 기억 객체를 만든다."""

    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=MEMORY_ID,
        character_id=None,
        content="사용자는 천문학을 좋아한다.",
        importance=4,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


class FakeMemoryService:
    """DB 없이 기억 API의 입력·출력과 상태 코드만 검증한다."""

    async def create(self, payload: object) -> SimpleNamespace:
        return make_memory()

    async def list(
        self,
        *,
        character_id: uuid.UUID | None,
        offset: int,
        limit: int,
    ) -> list[SimpleNamespace]:
        return [make_memory()]

    async def get(self, memory_id: uuid.UUID) -> SimpleNamespace:
        return make_memory()

    async def update(
        self,
        memory_id: uuid.UUID,
        payload: object,
    ) -> SimpleNamespace:
        memory = make_memory()
        memory.importance = 5
        return memory

    async def delete(self, memory_id: uuid.UUID) -> None:
        return None


def override_memory_service() -> FakeMemoryService:
    return FakeMemoryService()


app.dependency_overrides[get_memory_service] = override_memory_service
client = TestClient(app)


def test_create_and_list_memories() -> None:
    """기억 생성 201 응답과 사용자 기억 목록을 확인한다."""

    create_response = client.post(
        "/memories",
        json={
            "content": "사용자는 천문학을 좋아한다.",
            "importance": 4,
        },
    )
    list_response = client.get("/memories")

    assert create_response.status_code == 201
    assert create_response.json()["id"] == str(MEMORY_ID)
    assert list_response.status_code == 200
    assert list_response.json()[0]["importance"] == 4


def test_update_and_delete_memory() -> None:
    """기억 중요도 부분 수정과 204 삭제 응답을 확인한다."""

    update_response = client.patch(
        f"/memories/{MEMORY_ID}",
        json={"importance": 5},
    )
    delete_response = client.delete(f"/memories/{MEMORY_ID}")

    assert update_response.status_code == 200
    assert update_response.json()["importance"] == 5
    assert delete_response.status_code == 204
