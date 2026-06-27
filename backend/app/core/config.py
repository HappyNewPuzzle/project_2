"""환경변수와 .env 파일을 타입이 있는 설정 객체로 변환한다."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """서비스에서 사용하는 모든 설정의 단일 진입점."""

    # API 문서와 로그에 표시되는 애플리케이션 기본 정보다.
    app_name: str = "AI Character Chat API"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # SQLAlchemy async 엔진은 asyncpg 드라이버가 포함된 URL을 사용한다.
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/character_chat"
    )
    # True로 바꾸면 실행되는 SQL이 로그에 보여 쿼리 디버깅에 유용하다.
    database_echo: bool = False
    # 너무 긴 대화 전체를 보내지 않고 최근 메시지만 LLM 문맥에 포함한다.
    chat_history_limit: int = Field(default=20, ge=1, le=100)

    # API 키가 없어도 앱과 문서는 실행되며, 실제 채팅 요청에서 명확한 오류를 낸다.
    openai_api_key: str | None = None
    # 모델 이름을 코드 밖으로 빼 두면 provider 코드를 고치지 않고 교체할 수 있다.
    openai_model: str = "gpt-5.4-mini"
    # 모든 캐릭터 프롬프트보다 앞에 붙는 서비스 공통 지침이다.
    llm_system_prompt: str = (
        "You are a helpful AI chat assistant. "
        "Answer naturally and in the same language as the user."
    )
    # 한 응답이 과도하게 길어져 비용이 커지는 것을 제한한다.
    llm_max_output_tokens: int = 1000

    # JWT는 서명되지만 암호화되지는 않는다. secret은 토큰 위조 방지에 사용한다.
    jwt_secret_key: str = Field(
        default="dev-only-change-this-secret-key-123456",
        min_length=32,
    )
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1, le=10_080)

    # 실행 디렉터리의 .env를 읽고, 아직 사용하지 않는 키는 무시한다.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """설정 파일을 매 요청마다 다시 읽지 않도록 최초 결과를 캐시한다."""

    return Settings()
