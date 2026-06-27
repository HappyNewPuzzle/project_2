"""비동기 DB 엔진, 세션 팩토리, FastAPI 세션 의존성을 제공한다."""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """프로세스에서 하나만 사용할 SQLAlchemy 비동기 엔진을 만든다."""

    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        # 풀에서 오래된 연결을 꺼낼 때 간단한 확인을 거쳐 끊긴 연결을 피한다.
        pool_pre_ping=True,
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """요청별 AsyncSession을 생성할 수 있는 팩토리를 캐시한다."""

    return async_sessionmaker(
        bind=get_engine(),
        # commit 후에도 ORM 객체의 값을 읽을 때 불필요한 재조회가 발생하지 않는다.
        expire_on_commit=False,
        # 쿼리 전에 자동 flush하지 않고 repository가 필요한 시점을 명시한다.
        autoflush=False,
    )


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """요청 시작에 세션을 열고 요청 종료 시 자동으로 닫는 FastAPI 의존성."""

    async with get_session_factory()() as session:
        yield session
