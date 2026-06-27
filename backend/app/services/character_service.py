"""캐릭터 CRUD의 비즈니스 규칙과 프롬프트 조립을 담당한다."""

import uuid

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Character, DEFAULT_CHARACTER_ID
from app.repositories.character_repository import CharacterRepository
from app.schemas.character import CharacterCreate, CharacterUpdate


class CharacterNotFoundError(LookupError):
    """요청한 캐릭터가 없을 때 라우터가 404로 변환할 예외."""


class CharacterInUseError(RuntimeError):
    """기존 대화가 참조하는 캐릭터를 삭제하려 할 때 발생한다."""


class CharacterPersistenceError(RuntimeError):
    """DB 장애를 캐릭터 도메인의 공통 저장 오류로 감싼다."""


def build_character_instructions(character: Character) -> str:
    """구조화된 캐릭터 필드를 LLM용 instructions 문자열로 조립한다."""

    # 이름과 역할 유지는 모든 캐릭터에 항상 포함되는 최소 지침이다.
    sections = [
        f"You are roleplaying as {character.name}. Stay in character.",
    ]
    # 비어 있는 선택 필드는 프롬프트에 불필요한 제목을 남기지 않는다.
    if character.description:
        sections.append(f"Character description:\n{character.description}")
    if character.personality:
        sections.append(f"Personality:\n{character.personality}")
    if character.speaking_style:
        sections.append(f"Speaking style:\n{character.speaking_style}")
    if character.system_prompt:
        sections.append(f"Additional character instructions:\n{character.system_prompt}")
    # 구역 사이를 빈 줄로 나눠 모델과 개발자가 읽기 쉽게 만든다.
    return "\n\n".join(sections)


class CharacterService:
    """캐릭터 트랜잭션과 삭제 제한 같은 도메인 규칙을 처리한다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._characters = CharacterRepository(session)

    async def list(self, *, offset: int, limit: int) -> list[Character]:
        """캐릭터 목록을 repository에서 조회하고 DB 오류를 변환한다."""

        try:
            return await self._characters.list(offset=offset, limit=limit)
        except SQLAlchemyError as exc:
            raise CharacterPersistenceError("Failed to list characters") from exc

    async def get(self, character_id: uuid.UUID) -> Character:
        """캐릭터를 찾고, 없으면 명시적인 도메인 예외를 발생시킨다."""

        try:
            character = await self._characters.get(character_id)
        except SQLAlchemyError as exc:
            raise CharacterPersistenceError("Failed to get character") from exc
        if character is None:
            raise CharacterNotFoundError(str(character_id))
        return character

    async def create(self, data: CharacterCreate) -> Character:
        """캐릭터 생성 전체를 하나의 트랜잭션으로 확정한다."""

        try:
            character = await self._characters.create(data)
            await self._session.commit()
            # commit 후 DB가 만든 시간값까지 응답에 포함하려고 다시 읽는다.
            await self._session.refresh(character)
            return character
        except SQLAlchemyError as exc:
            # 실패한 세션을 다음 작업에 재사용하지 않도록 rollback한다.
            await self._session.rollback()
            raise CharacterPersistenceError("Failed to create character") from exc

    async def update(
        self,
        character_id: uuid.UUID,
        data: CharacterUpdate,
    ) -> Character:
        """전달된 필드만 수정하고 최신 DB 상태를 반환한다."""

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
        """미사용 캐릭터만 삭제하며 기본 캐릭터는 항상 보존한다."""

        # 캐릭터를 생략한 채팅이 항상 동작하려면 기본 캐릭터가 사라지면 안 된다.
        if character_id == DEFAULT_CHARACTER_ID:
            raise CharacterInUseError("The default character cannot be deleted")

        character = await self.get(character_id)
        try:
            await self._characters.delete(character)
            await self._session.commit()
        except IntegrityError as exc:
            # conversations 외래 키의 RESTRICT 위반을 사용자 친화적 409로 바꿀 수 있다.
            await self._session.rollback()
            raise CharacterInUseError(str(character_id)) from exc
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise CharacterPersistenceError("Failed to delete character") from exc
