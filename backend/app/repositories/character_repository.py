import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Character
from app.schemas.character import CharacterCreate, CharacterUpdate


class CharacterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, character_id: uuid.UUID) -> Character | None:
        return await self._session.get(Character, character_id)

    async def list(self, *, offset: int, limit: int) -> list[Character]:
        statement = (
            select(Character)
            .order_by(Character.created_at, Character.id)
            .offset(offset)
            .limit(limit)
        )
        return list((await self._session.scalars(statement)).all())

    async def create(self, data: CharacterCreate) -> Character:
        character = Character(**data.model_dump())
        self._session.add(character)
        await self._session.flush()
        return character

    def update(
        self,
        character: Character,
        data: CharacterUpdate,
    ) -> Character:
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(character, field, value)
        return character

    async def delete(self, character: Character) -> None:
        await self._session.delete(character)
