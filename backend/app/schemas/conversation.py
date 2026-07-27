"""대화방 목록과 메시지 조회 API의 응답 스키마."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationResponse(BaseModel):
    """대화방 목록에서 보여 줄 최소 정보."""

    id: uuid.UUID
    user_id: uuid.UUID
    character_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    # SQLAlchemy ORM 객체에서 속성을 읽어 응답으로 변환한다.
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """한 대화방에 저장된 user/assistant 메시지 응답."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    # SQLAlchemy ORM 객체에서 속성을 읽어 응답으로 변환한다.
    model_config = ConfigDict(from_attributes=True)
