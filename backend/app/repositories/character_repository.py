"""characters 테이블에 접근하는 SQLAlchemy repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Character
from app.schemas.character import CharacterCreate, CharacterUpdate


class CharacterRepository:
    """캐릭터 CRUD의 DB 세부사항만 담당한다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, character_id: uuid.UUID) -> Character | None:
        """UUID로 캐릭터 한 명을 조회한다."""

        return await self._session.get(Character, character_id)

    async def list(self, *, offset: int, limit: int) -> list[Character]:
        """페이지네이션 범위의 캐릭터를 안정된 순서로 반환한다."""

        statement = (
            select(Character)
            .order_by(Character.created_at, Character.id)
            .offset(offset)
            .limit(limit)
        )
        return list((await self._session.scalars(statement)).all())

    async def create(self, data: CharacterCreate) -> Character:
        """검증이 끝난 Pydantic 데이터를 ORM 객체로 변환한다."""

        character = Character(**data.model_dump())
        self._session.add(character)
        await self._session.flush()
        return character

    def update(
        self,
        character: Character,
        data: CharacterUpdate,
    ) -> Character:
        """PATCH에 실제로 포함된 필드만 기존 ORM 객체에 반영한다."""

        for field, value in data.model_dump(exclude_unset=True).items():
            # 명시적인 null은 현재 단계에서는 값 삭제가 아니라 변경 없음으로 취급한다.
            if value is not None:
                setattr(character, field, value)
        return character

    async def delete(self, character: Character) -> None:
        """삭제 대상으로 표시하며 실제 반영은 서비스의 commit에서 일어난다."""

        await self._session.delete(character)
