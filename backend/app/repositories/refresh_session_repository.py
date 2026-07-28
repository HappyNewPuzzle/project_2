"""Refresh token hash 조회·회전·family 폐기를 담당한다."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RefreshSession


class RefreshSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        family_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshSession:
        refresh = RefreshSession(
            user_id=user_id,
            family_id=family_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(refresh)
        await self._session.flush()
        return refresh

    async def get_for_update(self, token_hash: str) -> RefreshSession | None:
        statement = (
            select(RefreshSession)
            .where(RefreshSession.token_hash == token_hash)
            .with_for_update()
        )
        return await self._session.scalar(statement)

    async def revoke_family(self, family_id: uuid.UUID, revoked_at: datetime) -> None:
        await self._session.execute(
            update(RefreshSession)
            .where(
                RefreshSession.family_id == family_id,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
