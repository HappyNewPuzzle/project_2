"""채팅 API가 주고받는 JSON 데이터의 검증 규칙."""

import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """일반 채팅과 스트리밍 채팅이 공통으로 받는 요청."""

    # 빈 문자열과 비정상적으로 큰 입력을 API 입구에서 차단한다.
    message: str = Field(min_length=1, max_length=10_000)
    # 없으면 새 대화방을 만들고, 있으면 해당 대화를 이어 간다.
    conversation_id: uuid.UUID | None = None
    # 새 대화에서 생략하면 기본 캐릭터를 사용한다.
    character_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    """클라이언트가 다음 대화에도 보관해야 할 ID와 AI 답변."""

    conversation_id: uuid.UUID
    character_id: uuid.UUID
    reply: str
