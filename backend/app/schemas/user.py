"""회원가입, 로그인 토큰, 현재 사용자 응답 스키마."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """회원가입 시 이메일과 충분한 길이의 비밀번호를 받는다."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(str_strip_whitespace=True)


class UserResponse(BaseModel):
    """비밀번호 해시를 제외한 외부 공개 사용자 정보."""

    id: uuid.UUID
    email: EmailStr
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """OAuth2 Bearer 인증에 사용하는 access token 응답."""

    access_token: str
    token_type: str = "bearer"
