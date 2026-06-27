"""users 테이블 조회와 생성을 담당하는 repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class UserRepository:
    """인증 서비스가 SQL 세부사항을 알지 않게 한다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        """UUID로 사용자 한 명을 조회한다."""

        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        """정규화된 이메일로 사용자 한 명을 조회한다."""

        statement = select(User).where(User.email == email)
        return await self._session.scalar(statement)

    async def create(self, *, email: str, hashed_password: str) -> User:
        """새 사용자를 세션에 추가하고 UUID 생성을 위해 flush한다."""

        user = User(email=email, hashed_password=hashed_password)
        self._session.add(user)
        await self._session.flush()
        return user
