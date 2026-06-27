"""가짜 CharacterService로 캐릭터 REST API 계약을 검증한다."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dependencies import get_character_service
from app.main import app

CHARACTER_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
OWNER_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")


def make_character() -> SimpleNamespace:
    """응답 스키마가 읽을 수 있는 ORM 유사 테스트 객체를 만든다."""

    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=CHARACTER_ID,
        owner_id=OWNER_ID,
        name="Luna",
        description="A moon librarian.",
        personality="Calm and curious.",
        speaking_style="Soft and concise.",
        system_prompt="Use gentle imagery.",
        created_at=now,
        updated_at=now,
    )


class FakeCharacterService:
    """DB 없이 CRUD 라우터의 직렬화와 상태 코드만 테스트한다."""

    async def create(self, payload: object) -> SimpleNamespace:
        return make_character()

    async def list(self, *, offset: int, limit: int) -> list[SimpleNamespace]:
        return [make_character()]

    async def get(self, character_id: uuid.UUID) -> SimpleNamespace:
        return make_character()

    async def update(
        self,
        character_id: uuid.UUID,
        payload: object,
    ) -> SimpleNamespace:
        character = make_character()
        character.name = "Updated Luna"
        return character

    async def delete(self, character_id: uuid.UUID) -> None:
        return None


def override_character_service() -> FakeCharacterService:
    return FakeCharacterService()


app.dependency_overrides[get_character_service] = override_character_service
client = TestClient(app)


def test_create_and_list_characters() -> None:
    """생성은 201, 목록은 캐릭터 배열을 반환하는지 확인한다."""

    create_response = client.post(
        "/characters",
        json={"name": "Luna"},
    )
    list_response = client.get("/characters")

    assert create_response.status_code == 201
    assert create_response.json()["id"] == str(CHARACTER_ID)
    assert list_response.status_code == 200
    assert list_response.json()[0]["name"] == "Luna"


def test_update_and_delete_character() -> None:
    """부분 수정 결과와 본문 없는 204 삭제 응답을 확인한다."""

    update_response = client.patch(
        f"/characters/{CHARACTER_ID}",
        json={"name": "Updated Luna"},
    )
    delete_response = client.delete(f"/characters/{CHARACTER_ID}")

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Luna"
    assert delete_response.status_code == 204
