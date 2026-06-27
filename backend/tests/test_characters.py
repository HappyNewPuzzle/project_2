import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dependencies import get_character_service
from app.main import app

CHARACTER_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


def make_character() -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=CHARACTER_ID,
        name="Luna",
        description="A moon librarian.",
        personality="Calm and curious.",
        speaking_style="Soft and concise.",
        system_prompt="Use gentle imagery.",
        created_at=now,
        updated_at=now,
    )


class FakeCharacterService:
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
    update_response = client.patch(
        f"/characters/{CHARACTER_ID}",
        json={"name": "Updated Luna"},
    )
    delete_response = client.delete(f"/characters/{CHARACTER_ID}")

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Luna"
    assert delete_response.status_code == 204
