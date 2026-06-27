"""모든 SQLAlchemy ORM 모델이 상속하는 공통 Base."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """모델 메타데이터를 한곳에 모아 Alembic이 테이블을 발견하게 한다."""

    pass
