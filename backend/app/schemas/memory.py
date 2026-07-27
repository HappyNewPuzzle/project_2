"""장기 기억 CRUD 요청과 응답 스키마."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryCreate(BaseModel):
    """새 기억의 내용, 선택적 캐릭터 범위, 중요도를 받는다."""

    content: str = Field(min_length=1, max_length=5_000)
    character_id: uuid.UUID | None = None
    importance: int = Field(default=3, ge=1, le=5)

    model_config = ConfigDict(str_strip_whitespace=True)


class MemoryUpdate(BaseModel):
    """기억 내용·중요도·활성 상태의 부분 수정을 지원한다."""

    content: str | None = Field(default=None, min_length=1, max_length=5_000)
    importance: int | None = Field(default=None, ge=1, le=5)
    is_active: bool | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class MemoryResponse(BaseModel):
    """현재 사용자에게 공개할 장기 기억 데이터."""

    id: uuid.UUID
    character_id: uuid.UUID | None
    content: str
    importance: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemorySearchResponse(MemoryResponse):
    """의미 검색 결과에 cosine similarity 점수를 함께 반환한다."""

    score: float = Field(ge=-1.0, le=1.0)


class MemoryReindexResponse(BaseModel):
    """한 번의 재색인 요청으로 갱신한 기억 개수."""

    indexed_count: int = Field(ge=0)
