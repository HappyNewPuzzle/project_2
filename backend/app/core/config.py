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
    # 컨테이너 수집기가 파싱하기 쉬운 한 줄 JSON 로그 사용 여부다.
    log_json: bool = True
    # 브라우저 프론트엔드가 백엔드 API를 호출할 수 있도록 허용할 origin 목록이다.
    # 환경변수 quoting을 단순하게 유지하려고 콤마로 구분된 문자열을 사용한다.
    cors_allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    auth_rate_limit_per_minute: int = Field(default=10, ge=1, le=10_000)
    chat_rate_limit_per_minute: int = Field(default=30, ge=1, le=10_000)
    # 값이 있으면 여러 API 프로세스가 공유하는 Redis 기반 rate limit을 사용한다.
    redis_url: str | None = None

    # SQLAlchemy async 엔진은 asyncpg 드라이버가 포함된 URL을 사용한다.
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/character_chat"
    )
    # True로 바꾸면 실행되는 SQL이 로그에 보여 쿼리 디버깅에 유용하다.
    database_echo: bool = False
    # 너무 긴 대화 전체를 보내지 않고 최근 메시지만 LLM 문맥에 포함한다.
    chat_history_limit: int = Field(default=20, ge=1, le=100)
    # 중요도 순으로 가져올 활성 장기 기억의 최대 개수다.
    chat_memory_limit: int = Field(default=10, ge=0, le=50)
    # true이면 채팅 완료 후 LLM으로 장기 기억 후보를 추출해 저장한다.
    auto_memory_enabled: bool = False
    auto_memory_max_items: int = Field(default=3, ge=1, le=10)
    # hashing은 로컬 개발과 테스트에서 외부 API 비용 없이 사용할 기본 provider다.
    embedding_provider: Literal["hashing", "openai"] = "hashing"
    # DB의 VECTOR(1536) 컬럼과 길이를 맞추기 위해 provider 출력 차원을 고정한다.
    embedding_dimensions: int = Field(default=1536, ge=1536, le=1536)
    # 실제 의미 기반 벡터가 필요할 때 사용할 OpenAI embedding 모델이다.
    openai_embedding_model: str = "text-embedding-3-small"
    # 모델을 바꾸더라도 migration 전까지 DB 벡터 차원과 같은 값을 유지해야 한다.
    openai_embedding_dimensions: int = Field(
        default=1536,
        ge=1536,
        le=1536,
    )

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

    @property
    def cors_origin_list(self) -> list[str]:
        """콤마 구분 CORS origin 문자열을 FastAPI middleware용 list로 변환한다."""

        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """설정 파일을 매 요청마다 다시 읽지 않도록 최초 결과를 캐시한다."""

    return Settings()
