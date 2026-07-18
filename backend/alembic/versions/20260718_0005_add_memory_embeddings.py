"""Add memory embeddings table.

Revision ID: 20260718_0005
Revises: 20260628_0004
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260718_0005"
down_revision: str | Sequence[str] | None = "20260628_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """pgvector 전환 전 embedding 저장용 테이블을 추가한다."""

    op.create_table(
        "memory_embeddings",
        sa.Column("memory_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("vector_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["memory_id"],
            ["memories.id"],
            name="fk_memory_embeddings_memory_id_memories",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("memory_id"),
    )


def downgrade() -> None:
    """embedding 저장 테이블을 제거한다."""

    op.drop_table("memory_embeddings")
