"""Add automatically generated conversation titles.

Revision ID: 20260727_0007
Revises: 20260727_0006
Create Date: 2026-07-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260727_0007"
down_revision: str | Sequence[str] | None = "20260727_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """제목 컬럼을 추가하고 기존 대화는 첫 사용자 메시지로 채운다."""

    # 기존 행이 있으므로 먼저 nullable 컬럼으로 추가한 뒤 데이터를 채운다.
    op.add_column(
        "conversations",
        sa.Column(
            "title",
            sa.String(length=100),
            server_default=sa.text("'새 대화'"),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE conversations AS conversation
        SET title = COALESCE(
            NULLIF(
                LEFT(
                    BTRIM(
                        REGEXP_REPLACE(
                            COALESCE(
                                (
                                    SELECT message.content
                                    FROM messages AS message
                                    WHERE
                                        message.conversation_id = conversation.id
                                        AND message.role = 'user'
                                    ORDER BY message.created_at, message.id
                                    LIMIT 1
                                ),
                                '새 대화'
                            ),
                            '[[:space:]]+',
                            ' ',
                            'g'
                        )
                    ),
                    100
                ),
                ''
            ),
            '새 대화'
        )
        """
    )
    # 모든 기존 행을 채운 뒤 애플리케이션 모델과 같은 NOT NULL 제약을 적용한다.
    op.alter_column(
        "conversations",
        "title",
        existing_type=sa.String(length=100),
        nullable=False,
        server_default=sa.text("'새 대화'"),
    )


def downgrade() -> None:
    """대화방 제목 컬럼을 제거한다."""

    op.drop_column("conversations", "title")
