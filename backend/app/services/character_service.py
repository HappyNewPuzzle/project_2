import uuid

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Character, DEFAULT_CHARACTER_ID
from app.repositories.character_repository import CharacterRepository
from app.schemas.character import CharacterCreate, CharacterUpdate


class CharacterNotFoundError(LookupError):
    """Raised when a requested character does not exist."""


class CharacterInUseError(RuntimeError):
    """Raised when deleting a character referenced by conversations."""


class CharacterPersistenceError(RuntimeError):
    """Raised when character data cannot be persisted."""


def build_character_instructions(character: Character) -> str:
    sections = [
        f"You are roleplaying as {character.name}. Stay in character.",
    ]
    if character.description:
        sections.append(f"Character description:\n{character.description}")
    if character.personality:
        sections.append(f"Personality:\n{character.personality}")
    if character.speaking_style:
        sections.append(f"Speaking style:\n{character.speaking_style}")
    if character.system_prompt:
        sections.append(f"Additional character instructions:\n{character.system_prompt}")
    return "\n\n".join(sections)


class CharacterService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._characters = CharacterRepository(session)

    async def list(self, *, offset: int, limit: int) -> list[Character]:
        try:
            return await self._characters.list(offset=offset, limit=limit)
        except SQLAlchemyError as exc:
            raise CharacterPersistenceError("Failed to list characters") from exc

    async def get(self, character_id: uuid.UUID) -> Character:
        try:
            character = await self._characters.get(character_id)
        except SQLAlchemyError as exc:
            raise CharacterPersistenceError("Failed to get character") from exc
        if character is None:
            raise CharacterNotFoundError(str(character_id))
        return character

    async def create(self, data: CharacterCreate) -> Character:
        try:
            character = await self._characters.create(data)
            await self._session.commit()
            await self._session.refresh(character)
            return character
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise CharacterPersistenceError("Failed to create character") from exc

    async def update(
        self,
        character_id: uuid.UUID,
        data: CharacterUpdate,
    ) -> Character:
        character = await self.get(character_id)
        try:
            self._characters.update(character, data)
            await self._session.commit()
            await self._session.refresh(character)
            return character
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise CharacterPersistenceError("Failed to update character") from exc

    async def delete(self, character_id: uuid.UUID) -> None:
        if character_id == DEFAULT_CHARACTER_ID:
            raise CharacterInUseError("The default character cannot be deleted")

        character = await self.get(character_id)
        try:
            await self._characters.delete(character)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise CharacterInUseError(str(character_id)) from exc
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise CharacterPersistenceError("Failed to delete character") from exc
