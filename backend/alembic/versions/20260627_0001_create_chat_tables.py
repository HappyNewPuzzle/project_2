"""Create conversation and message tables.

Revision ID: 20260627_0001
Revises:
Create Date: 2026-06-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260627_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """대화방 테이블을 먼저 만들고 이를 참조하는 메시지 테이블을 만든다."""

    # 부모 테이블인 conversations가 외래 키 대상이므로 먼저 생성한다.
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    # messages는 role 제약과 conversations CASCADE 외래 키를 가진다.
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_messages_role",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # 최근 대화 조회 패턴에 맞춘 복합 인덱스다.
    op.create_index(
        "ix_messages_conversation_created",
        "messages",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    """upgrade의 정확한 역순으로 인덱스와 테이블을 제거한다."""

    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_table("messages")
    op.drop_table("conversations")
