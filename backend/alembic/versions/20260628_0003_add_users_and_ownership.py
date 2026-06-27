"""Add users and resource ownership.

Revision ID: 20260628_0003
Revises: 20260628_0002
Create Date: 2026-06-28
"""

import uuid
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260628_0003"
down_revision: str | Sequence[str] | None = "20260628_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def upgrade() -> None:
    """사용자 테이블을 만들고 기존 대화를 비활성 legacy 계정에 연결한다."""

    # 외래 키 대상 users를 가장 먼저 만든다.
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
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
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 인증 도입 전에 생성된 대화의 소유자로 사용할 로그인 불가 계정이다.
    users_table = sa.table(
        "users",
        sa.column("id", sa.Uuid()),
        sa.column("email", sa.String()),
        sa.column("hashed_password", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        users_table,
        [
            {
                "id": LEGACY_USER_ID,
                "email": "legacy-system@invalid.local",
                # 유효한 Argon2 형식이지만 비활성 계정이라 로그인할 수 없다.
                "hashed_password": (
                    "$argon2id$v=19$m=65536,t=3,p=4$"
                    "wagCPXjifgvUFBzq4hqe3w$"
                    "CYaIb8sB+wtD+Vu/P4uod1+Qof8h+1g7bbDlBID48Rc"
                ),
                "is_active": False,
            }
        ],
    )

    # 기본 캐릭터는 owner_id=NULL인 공용 읽기 전용 리소스로 유지한다.
    op.add_column(
        "characters",
        sa.Column("owner_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_characters_owner_id_users",
        "characters",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_characters_owner_id", "characters", ["owner_id"])

    # 기존 행 보정을 위해 nullable로 추가한 뒤 legacy 사용자로 채운다.
    op.add_column(
        "conversations",
        sa.Column("user_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE conversations SET user_id = :user_id WHERE user_id IS NULL"
        ).bindparams(user_id=LEGACY_USER_ID)
    )
    op.alter_column(
        "conversations",
        "user_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_conversations_user_id_users",
        "conversations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])


def downgrade() -> None:
    """소유권 컬럼과 외래 키를 제거한 뒤 users 테이블을 삭제한다."""

    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_constraint(
        "fk_conversations_user_id_users",
        "conversations",
        type_="foreignkey",
    )
    op.drop_column("conversations", "user_id")

    op.drop_index("ix_characters_owner_id", table_name="characters")
    op.drop_constraint(
        "fk_characters_owner_id_users",
        "characters",
        type_="foreignkey",
    )
    op.drop_column("characters", "owner_id")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
