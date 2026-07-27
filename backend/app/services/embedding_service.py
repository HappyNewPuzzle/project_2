"""장기 기억 관련성 검색을 위한 embedding 경계."""

from __future__ import annotations

import hashlib
import math
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from openai import AsyncOpenAI, OpenAIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.repositories.memory_embedding_repository import MemoryEmbeddingRepository


class EmbeddingConfigurationError(RuntimeError):
    """API 키처럼 embedding 호출에 필수인 설정이 없을 때 발생한다."""


class EmbeddingServiceError(RuntimeError):
    """외부 embedding API 오류를 애플리케이션 공통 오류로 변환한다."""


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


class OpenAIEmbeddingProvider:
    """OpenAI Embeddings API를 사용하는 실제 의미 기반 provider."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        dimensions: int,
        client: Any | None = None,
    ) -> None:
        # 테스트에서는 가짜 client를 주입하고, 운영에서는 API 키로 SDK client를 만든다.
        if client is not None:
            self._client = client
        elif api_key:
            self._client = AsyncOpenAI(api_key=api_key)
        else:
            self._client = None
        self._model = model
        self._dimensions = dimensions
        # 저장된 벡터가 어떤 모델과 차원으로 생성됐는지 DB에서 구분할 수 있게 한다.
        self.provider_name = f"openai:{model}:{dimensions}"

    async def embed(self, text: str) -> list[float]:
        """텍스트 하나를 OpenAI 모델의 float embedding 벡터로 변환한다."""

        if self._client is None:
            raise EmbeddingConfigurationError("OPENAI_API_KEY is missing")

        try:
            # 공식 Python SDK 형식에 맞춰 모델, 입력, 출력 차원을 명시한다.
            response = await self._client.embeddings.create(
                model=self._model,
                input=text,
                encoding_format="float",
                dimensions=self._dimensions,
            )
        except OpenAIError as exc:
            # 상위 서비스가 OpenAI SDK의 세부 예외에 직접 의존하지 않게 감싼다.
            raise EmbeddingServiceError(
                "OpenAI embedding request failed"
            ) from exc

        if not response.data or not response.data[0].embedding:
            raise EmbeddingServiceError("OpenAI returned an empty embedding")
        return list(response.data[0].embedding)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    """환경 설정에 맞는 embedding provider 하나를 만들어 재사용한다."""

    settings = get_settings()
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            dimensions=settings.openai_embedding_dimensions,
        )
    return HashingEmbeddingProvider(dimensions=settings.embedding_dimensions)


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
        *,
        user_id: uuid.UUID,
    ) -> None:
        self._session = session
        self._provider = provider
        self._user_id = user_id
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

    async def search(
        self,
        query: str,
        *,
        character_id: uuid.UUID | None,
        limit: int,
    ) -> list[MemorySearchResult]:
        """pgvector cosine query로 현재 사용자의 가까운 memory ID를 반환한다."""

        query_vector = await self._provider.embed(query)
        rows = await self._embeddings.search(
            user_id=self._user_id,
            query_vector=query_vector,
            character_id=character_id,
            limit=limit,
        )
        return [
            MemorySearchResult(
                memory_id=str(memory.id),
                score=score,
            )
            for memory, score in rows
        ]
