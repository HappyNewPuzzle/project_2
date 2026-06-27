"""PostgreSQL 테이블과 Python 객체 사이를 연결하는 SQLAlchemy ORM 모델."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# 캐릭터를 지정하지 않은 기존 API 요청이 사용할 고정 기본 캐릭터 ID다.
DEFAULT_CHARACTER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class MessageRole(str, enum.Enum):
    """messages.role에 저장할 수 있는 두 가지 발화 주체."""

    USER = "user"
    ASSISTANT = "assistant"


class Character(Base):
    """AI 캐릭터의 표시 정보와 LLM 행동 지침을 저장한다."""

    __tablename__ = "characters"

    # UUID는 여러 서버에서 ID를 만들어도 충돌할 가능성이 매우 낮다.
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # 이름은 목록에 자주 표시되므로 길이가 제한된 문자열로 저장한다.
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 아래 네 필드는 길이가 유동적이어서 Text 타입을 사용한다.
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    personality: Mapped[str] = mapped_column(Text, default="", nullable=False)
    speaking_style: Mapped[str] = mapped_column(Text, default="", nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 시간은 DB 서버가 기록하므로 여러 API 서버의 시계 차이를 줄일 수 있다.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 한 캐릭터는 여러 대화방에서 사용될 수 있는 1:N 관계다.
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="character",
        passive_deletes=True,
    )


class Conversation(Base):
    """한 캐릭터와 이어지는 하나의 대화방."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # 대화 도중 캐릭터가 바뀌지 않도록 대화방 자체가 캐릭터를 참조한다.
    character_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        # 사용 중인 캐릭터 삭제는 DB도 거부한다.
        ForeignKey("characters.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 대화방 삭제 시 소속 메시지도 함께 삭제되는 소유 관계다.
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    character: Mapped[Character] = relationship(back_populates="conversations")


class Message(Base):
    """사용자 또는 AI가 대화방에서 보낸 메시지 한 건."""

    __tablename__ = "messages"
    __table_args__ = (
        # 잘못된 역할 문자열이 DB에 직접 들어오는 것도 차단한다.
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_messages_role",
        ),
        # 특정 대화의 최근 메시지를 시간순으로 가져오는 쿼리를 빠르게 한다.
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # 대화방이 삭제되면 고아 메시지가 남지 않도록 CASCADE를 사용한다.
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
