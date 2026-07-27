"""embedding provider와 cosine 검색 준비 로직을 검증한다."""

import asyncio
from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.services.embedding_service import (
    EmbeddingConfigurationError,
    HashingEmbeddingProvider,
    OpenAIEmbeddingProvider,
    cosine_similarity,
    get_embedding_provider,
)


def test_cosine_similarity_identical_vectors() -> None:
    """같은 방향의 벡터는 similarity가 1에 가깝다."""

    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_dimension_mismatch_returns_zero() -> None:
    """차원이 다른 벡터는 비교하지 않고 0으로 처리한다."""

    assert cosine_similarity([1.0], [1.0, 0.0]) == 0.0


def test_hashing_embedding_has_fixed_dimensions() -> None:
    """개발용 hashing embedding은 설정한 차원의 벡터를 만든다."""

    provider = HashingEmbeddingProvider(dimensions=16)

    vector = asyncio.run(provider.embed("천문학을 좋아한다"))

    assert len(vector) == 16
    assert any(value > 0 for value in vector)


class FakeEmbeddingsResource:
    """실제 네트워크 대신 호출 인자와 가짜 vector를 돌려주는 테스트 대역."""

    def __init__(self) -> None:
        self.arguments: dict[str, object] | None = None

    async def create(self, **kwargs):
        self.arguments = kwargs
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])]
        )


def test_openai_embedding_provider_uses_configured_model() -> None:
    """OpenAI provider가 SDK에 모델·입력·차원 설정을 정확히 전달한다."""

    embeddings = FakeEmbeddingsResource()
    client = SimpleNamespace(embeddings=embeddings)
    provider = OpenAIEmbeddingProvider(
        api_key=None,
        model="text-embedding-3-small",
        dimensions=3,
        client=client,
    )

    vector = asyncio.run(provider.embed("사용자는 퍼즐을 좋아한다"))

    assert vector == [0.1, 0.2, 0.3]
    assert embeddings.arguments == {
        "model": "text-embedding-3-small",
        "input": "사용자는 퍼즐을 좋아한다",
        "encoding_format": "float",
        "dimensions": 3,
    }
    assert provider.provider_name == "openai:text-embedding-3-small:3"


def test_openai_embedding_provider_requires_api_key() -> None:
    """API 키와 주입 client가 모두 없으면 외부 요청 전에 명확히 실패한다."""

    provider = OpenAIEmbeddingProvider(
        api_key=None,
        model="text-embedding-3-small",
        dimensions=1536,
    )

    with pytest.raises(
        EmbeddingConfigurationError,
        match="OPENAI_API_KEY is missing",
    ):
        asyncio.run(provider.embed("기억"))


def test_provider_factory_selects_openai_from_environment(monkeypatch) -> None:
    """환경변수만 바꿔 provider 구현과 모델 설정을 교체할 수 있다."""

    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("OPENAI_EMBEDDING_DIMENSIONS", "256")
    # 두 함수가 이전 테스트의 설정 객체를 재사용하지 않도록 캐시를 비운다.
    get_settings.cache_clear()
    get_embedding_provider.cache_clear()

    provider = get_embedding_provider()

    assert isinstance(provider, OpenAIEmbeddingProvider)
    assert provider.provider_name == "openai:text-embedding-3-small:256"

    # 뒤에 실행되는 테스트가 이 테스트의 설정을 재사용하지 않게 정리한다.
    get_embedding_provider.cache_clear()
    get_settings.cache_clear()
