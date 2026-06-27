"""Add characters and connect them to conversations.

Revision ID: 20260628_0002
Revises: 20260627_0001
Create Date: 2026-06-28
"""

import uuid
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260628_0002"
down_revision: str | Sequence[str] | None = "20260627_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 기존 /chat 호출과 기존 conversation을 보존하기 위한 고정 기본 캐릭터다.
DEFAULT_CHARACTER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def upgrade() -> None:
    """캐릭터를 만든 뒤 기존 대화를 기본 캐릭터에 안전하게 연결한다."""

    # 1) 외래 키 대상인 characters 테이블을 먼저 생성한다.
    op.create_table(
        "characters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "personality",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "speaking_style",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "system_prompt",
            sa.Text(),
            nullable=False,
        ),
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

    # 2) ORM을 사용하지 않는 migration용 임시 테이블 표현을 만든다.
    characters_table = sa.table(
        "characters",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("personality", sa.Text()),
        sa.column("speaking_style", sa.Text()),
        sa.column("system_prompt", sa.Text()),
    )
    # 3) 캐릭터를 지정하지 않은 요청이 쓸 기본 레코드를 삽입한다.
    op.bulk_insert(
        characters_table,
        [
            {
                "id": DEFAULT_CHARACTER_ID,
                "name": "Assistant",
                "description": "A helpful general-purpose AI assistant.",
                "personality": "Friendly, thoughtful, and reliable.",
                "speaking_style": "Natural and clear.",
                "system_prompt": (
                    "Answer naturally and in the same language as the user."
                ),
            }
        ],
    )

    # 4) 기존 행이 있으므로 처음에는 nullable 컬럼으로 추가한다.
    op.add_column(
        "conversations",
        sa.Column("character_id", sa.Uuid(), nullable=True),
    )
    # 5) 기존 모든 대화를 기본 캐릭터에 연결해 NULL을 제거한다.
    op.execute(
        sa.text(
            "UPDATE conversations "
            "SET character_id = :character_id "
            "WHERE character_id IS NULL"
        ).bindparams(character_id=DEFAULT_CHARACTER_ID)
    )
    # 6) 데이터 보정 후에야 NOT NULL 제약을 안전하게 걸 수 있다.
    op.alter_column(
        "conversations",
        "character_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    # 7) 캐릭터 삭제 제한과 조회 성능용 외래 키/인덱스를 추가한다.
    op.create_foreign_key(
        "fk_conversations_character_id_characters",
        "conversations",
        "characters",
        ["character_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_conversations_character_id",
        "conversations",
        ["character_id"],
    )


def downgrade() -> None:
    """대화 연결을 먼저 제거한 뒤 characters 테이블을 삭제한다."""

    op.drop_index(
        "ix_conversations_character_id",
        table_name="conversations",
    )
    op.drop_constraint(
        "fk_conversations_character_id_characters",
        "conversations",
        type_="foreignkey",
    )
    op.drop_column("conversations", "character_id")
    op.drop_table("characters")
