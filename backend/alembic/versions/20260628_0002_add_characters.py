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

DEFAULT_CHARACTER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def upgrade() -> None:
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

    characters_table = sa.table(
        "characters",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("personality", sa.Text()),
        sa.column("speaking_style", sa.Text()),
        sa.column("system_prompt", sa.Text()),
    )
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

    op.add_column(
        "conversations",
        sa.Column("character_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE conversations "
            "SET character_id = :character_id "
            "WHERE character_id IS NULL"
        ).bindparams(character_id=DEFAULT_CHARACTER_ID)
    )
    op.alter_column(
        "conversations",
        "character_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
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
