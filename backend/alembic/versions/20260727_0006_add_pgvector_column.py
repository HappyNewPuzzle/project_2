"""Add pgvector extension and vector column.

Revision ID: 20260727_0006
Revises: 20260718_0005
Create Date: 2026-07-27
"""

from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import VECTOR
import sqlalchemy as sa

revision: str = "20260727_0006"
down_revision: str | Sequence[str] | None = "20260718_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """pgvector를 활성화하고 1536차원 벡터 컬럼과 검색 index를 추가한다."""

    # 확장은 데이터베이스마다 한 번만 활성화하면 되며 재실행해도 안전하다.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "memory_embeddings",
        sa.Column("embedding", VECTOR(1536), nullable=True),
    )
    # 기존 JSON 중 새 고정 차원과 같은 데이터만 안전하게 pgvector로 옮긴다.
    op.execute(
        """
        UPDATE memory_embeddings
        SET embedding = vector_json::vector
        WHERE dimensions = 1536
        """
    )
    # cosine 검색이 데이터 증가 후에도 전체 테이블 정렬로 느려지지 않게 준비한다.
    op.create_index(
        "ix_memory_embeddings_embedding_cosine",
        "memory_embeddings",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("embedding IS NOT NULL"),
    )


def downgrade() -> None:
    """HNSW index와 vector 컬럼만 제거하고 공유 확장은 유지한다."""

    op.drop_index(
        "ix_memory_embeddings_embedding_cosine",
        table_name="memory_embeddings",
    )
    op.drop_column("memory_embeddings", "embedding")
