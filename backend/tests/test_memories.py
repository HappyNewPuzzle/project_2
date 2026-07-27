"""가짜 MemoryService로 장기 기억 REST API 계약을 검증한다."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dependencies import (
    enforce_chat_rate_limit,
    get_memory_service,
)
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

    async def search(
        self,
        query: str,
        *,
        character_id: uuid.UUID | None,
        limit: int,
    ) -> list[SimpleNamespace]:
        return [SimpleNamespace(memory=make_memory(), score=0.95)]

    async def reindex(self, *, limit: int) -> int:
        return 2

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
# 의미 검색과 재색인 라우터 테스트에서는 실제 사용자 rate limit을 건너뛴다.
app.dependency_overrides[enforce_chat_rate_limit] = lambda: None
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


def test_search_and_reindex_memories() -> None:
    """고정 경로가 UUID 경로보다 먼저 매칭되고 검색 점수와 개수를 반환한다."""

    search_response = client.get(
        "/memories/search",
        params={"query": "별과 우주"},
    )
    reindex_response = client.post(
        "/memories/reindex",
        params={"limit": 10},
    )

    assert search_response.status_code == 200
    assert search_response.json()[0]["id"] == str(MEMORY_ID)
    assert search_response.json()[0]["score"] == 0.95
    assert reindex_response.status_code == 200
    assert reindex_response.json() == {"indexed_count": 2}


def test_search_rejects_blank_query() -> None:
    """공백만 있는 검색어는 embedding API를 호출하기 전에 거부한다."""

    response = client.get(
        "/memories/search",
        params={"query": "   "},
    )

    assert response.status_code == 422
