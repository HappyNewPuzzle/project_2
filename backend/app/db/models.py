"""PostgreSQL 테이블과 Python 객체 사이를 연결하는 SQLAlchemy ORM 모델."""

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# 캐릭터를 지정하지 않은 기존 API 요청이 사용할 고정 기본 캐릭터 ID다.
DEFAULT_CHARACTER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
LEGACY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


class MessageRole(str, enum.Enum):
    """messages.role에 저장할 수 있는 두 가지 발화 주체."""

    USER = "user"
    ASSISTANT = "assistant"


class User(Base):
    """회원 계정과 인증에 필요한 최소 정보를 저장한다."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # 로그인 식별자는 소문자로 정규화하며 DB unique 제약으로 중복을 막는다.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    # 원문 비밀번호 대신 Argon2 해시만 저장한다.
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
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

    characters: Mapped[list["Character"]] = relationship(
        back_populates="owner",
        passive_deletes=True,
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user",
        passive_deletes=True,
    )
    memories: Mapped[list["Memory"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Character(Base):
    """AI 캐릭터의 표시 정보와 LLM 행동 지침을 저장한다."""

    __tablename__ = "characters"

    # UUID는 여러 서버에서 ID를 만들어도 충돌할 가능성이 매우 낮다.
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # NULL인 기본/legacy 캐릭터는 공용 읽기 전용 캐릭터로 취급한다.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
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
    owner: Mapped[User | None] = relationship(back_populates="characters")
    memories: Mapped[list["Memory"]] = relationship(
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
    # 모든 대화방은 한 사용자에게 속해 사용자별 기록을 분리한다.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # 대화 도중 캐릭터가 바뀌지 않도록 대화방 자체가 캐릭터를 참조한다.
    character_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        # 사용 중인 캐릭터 삭제는 DB도 거부한다.
        ForeignKey("characters.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # 목록에서 UUID 대신 이해하기 쉬운 이름을 보여 주기 위한 자동 생성 제목이다.
    title: Mapped[str] = mapped_column(
        String(100),
        default="새 대화",
        server_default="새 대화",
        nullable=False,
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
    user: Mapped[User] = relationship(back_populates="conversations")


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


class Memory(Base):
    """최근 대화 창 밖에서도 유지할 사용자 장기 기억 한 건."""

    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint(
            "importance BETWEEN 1 AND 5",
            name="ck_memories_importance",
        ),
        # 채팅 시 사용자/캐릭터/활성 상태로 거른 뒤 중요도순 조회한다.
        Index(
            "ix_memories_lookup",
            "user_id",
            "character_id",
            "is_active",
            "importance",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # NULL이면 모든 캐릭터, UUID면 해당 캐릭터와 대화할 때만 사용한다.
    character_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("characters.id", ondelete="CASCADE"),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
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

    user: Mapped[User] = relationship(back_populates="memories")
    character: Mapped[Character | None] = relationship(back_populates="memories")
    embedding: Mapped["MemoryEmbedding | None"] = relationship(
        back_populates="memory",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class MemoryEmbedding(Base):
    """장기 기억의 의미 벡터와 생성 provider 정보를 저장한다."""

    __tablename__ = "memory_embeddings"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("memories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    # 이전 버전과 안전하게 병행하기 위해 JSON 표현은 다음 정리 migration까지 유지한다.
    vector_json: Mapped[str] = mapped_column(Text, nullable=False)
    # pgvector가 cosine 거리 계산과 HNSW index 검색에 사용할 실제 벡터 컬럼이다.
    embedding: Mapped[list[float] | None] = mapped_column(
        VECTOR(1536),
        nullable=True,
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

    memory: Mapped[Memory] = relationship(back_populates="embedding")
