"""embedding provider와 cosine 검색 준비 로직을 검증한다."""

import asyncio

from app.services.embedding_service import (
    HashingEmbeddingProvider,
    cosine_similarity,
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
