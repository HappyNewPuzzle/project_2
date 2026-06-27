"""캐릭터 CRUD API의 요청·응답 Pydantic 스키마."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CharacterCreate(BaseModel):
    """새 캐릭터 생성 시 허용하는 필드와 최대 길이."""

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=10_000)
    personality: str = Field(default="", max_length=10_000)
    speaking_style: str = Field(default="", max_length=10_000)
    system_prompt: str = Field(default="", max_length=20_000)

    # 앞뒤 공백을 자동 제거해 공백뿐인 이름이 저장되는 것을 막는다.
    model_config = ConfigDict(str_strip_whitespace=True)


class CharacterUpdate(BaseModel):
    """PATCH 요청이므로 모든 필드가 선택 사항이다."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=10_000)
    personality: str | None = Field(default=None, max_length=10_000)
    speaking_style: str | None = Field(default=None, max_length=10_000)
    system_prompt: str | None = Field(default=None, max_length=20_000)

    model_config = ConfigDict(str_strip_whitespace=True)


class CharacterResponse(BaseModel):
    """DB의 Character ORM 객체를 API JSON으로 직렬화한다."""

    id: uuid.UUID
    name: str
    description: str
    personality: str
    speaking_style: str
    system_prompt: str
    created_at: datetime
    updated_at: datetime

    # dict뿐 아니라 character.name 같은 ORM 속성에서도 값을 읽는다.
    model_config = ConfigDict(from_attributes=True)
