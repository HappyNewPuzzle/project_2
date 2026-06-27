"""Alembic이 비동기 SQLAlchemy 설정으로 migration을 실행하게 하는 환경 파일."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.db.base import Base
from app.db import models  # noqa: F401

# alembic.ini에서 읽은 현재 Alembic 설정 객체다.
config = context.config

if config.config_file_name is not None:
    # alembic.ini의 로깅 설정을 Python logging에 적용한다.
    fileConfig(config.config_file_name)

# 실제 연결 주소는 코드와 동일하게 .env 설정을 우선 사용한다.
config.set_main_option(
    "sqlalchemy.url",
    get_settings().database_url.replace("%", "%%"),
)
# models를 import했으므로 Base.metadata에는 모든 ORM 테이블이 등록되어 있다.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """DB에 연결하지 않고 실행할 SQL 스크립트를 생성하는 모드."""

    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """동기 Alembic 작업을 전달받은 연결에서 실행한다."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """asyncpg 연결을 열고 동기 Alembic 함수를 안전하게 브리지한다."""

    # migration 실행에는 장기 커넥션 풀이 필요 없으므로 NullPool을 사용한다.
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """일반 `alembic upgrade` 명령에서 비동기 migration을 실행한다."""

    asyncio.run(run_async_migrations())


# --sql 옵션 유무에 따라 offline/online 경로를 선택한다.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
