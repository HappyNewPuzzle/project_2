import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=10_000)
    personality: str = Field(default="", max_length=10_000)
    speaking_style: str = Field(default="", max_length=10_000)
    system_prompt: str = Field(default="", max_length=20_000)

    model_config = ConfigDict(str_strip_whitespace=True)


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=10_000)
    personality: str | None = Field(default=None, max_length=10_000)
    speaking_style: str | None = Field(default=None, max_length=10_000)
    system_prompt: str | None = Field(default=None, max_length=20_000)

    model_config = ConfigDict(str_strip_whitespace=True)


class CharacterResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    personality: str
    speaking_style: str
    system_prompt: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
