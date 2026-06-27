from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Character Chat API"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4-mini"
    llm_system_prompt: str = (
        "You are a helpful AI chat assistant. "
        "Answer naturally and in the same language as the user."
    )
    llm_max_output_tokens: int = 1000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
