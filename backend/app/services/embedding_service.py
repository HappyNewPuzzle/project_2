"""장기 기억 관련성 검색을 위한 embedding 경계."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.memory_embedding_repository import MemoryEmbeddingRepository


class EmbeddingProvider(Protocol):
    """OpenAI embedding이나 다른 provider로 교체 가능한 계약."""

    provider_name: str

    async def embed(self, text: str) -> list[float]:
        """텍스트 하나를 고정 길이 float 벡터로 변환한다."""
        ...


class HashingEmbeddingProvider:
    """외부 API 없이 테스트 가능한 deterministic embedding provider."""

    provider_name = "hashing-dev"

    def __init__(self, *, dimensions: int) -> None:
        self._dimensions = dimensions

    async def embed(self, text: str) -> list[float]:
        """문자 n-gram 해시를 누적해 간단한 정규화 벡터를 만든다."""

        vector = [0.0] * self._dimensions
        normalized = text.lower().strip()
        for index in range(max(1, len(normalized) - 1)):
            token = normalized[index : index + 2] or normalized
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self._dimensions
            vector[bucket] += 1.0
        length = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / length for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """두 벡터의 cosine similarity를 계산한다."""

    if len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))


@dataclass(frozen=True, slots=True)
class MemorySearchResult:
    """embedding 검색 결과 한 건."""

    memory_id: str
    score: float


class MemoryEmbeddingService:
    """memory embedding 저장과 관련성 검색을 조정한다."""

    def __init__(
        self,
        session: AsyncSession,
        provider: EmbeddingProvider,
    ) -> None:
        self._session = session
        self._provider = provider
        self._embeddings = MemoryEmbeddingRepository(session)

    async def index_memory(self, *, memory_id, content: str) -> None:
        """memory content를 embedding으로 변환해 저장한다."""

        vector = await self._provider.embed(content)
        await self._embeddings.upsert(
            memory_id=memory_id,
            provider=self._provider.provider_name,
            vector=vector,
        )
        await self._session.commit()

    async def search(self, query: str, *, limit: int) -> list[MemorySearchResult]:
        """현재는 Python에서 cosine을 계산하고, 이후 pgvector 쿼리로 교체한다."""

        query_vector = await self._provider.embed(query)
        results: list[MemorySearchResult] = []
        for embedding in await self._embeddings.list_all():
            vector = json.loads(embedding.vector_json)
            results.append(
                MemorySearchResult(
                    memory_id=str(embedding.memory_id),
                    score=cosine_similarity(query_vector, vector),
                )
            )
        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]
