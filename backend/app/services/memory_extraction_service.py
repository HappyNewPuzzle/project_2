"""대화 한 턴에서 장기 기억 후보를 추출하고 저장한다."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.memory_embedding_repository import MemoryEmbeddingRepository
from app.repositories.memory_repository import MemoryRepository
from app.schemas.memory import MemoryCreate
from app.services.embedding_service import (
    EmbeddingProvider,
    get_embedding_provider,
)
from app.services.llm_service import LLMMessage, LLMProvider


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExtractedMemory:
    """LLM이 제안한 장기 기억 후보."""

    content: str
    importance: int


class MemoryExtractionService:
    """LLM 출력 JSON을 검증 가능한 memory 후보로 변환해 저장한다."""

    def __init__(
        self,
        session: AsyncSession,
        llm: LLMProvider,
        *,
        user_id: uuid.UUID,
        max_items: int,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._user_id = user_id
        self._max_items = max_items
        self._embedding_provider = (
            embedding_provider or get_embedding_provider()
        )
        self._memories = MemoryRepository(session)
        self._embeddings = MemoryEmbeddingRepository(session)

    async def extract(
        self,
        *,
        user_message: str,
        assistant_reply: str,
    ) -> list[ExtractedMemory]:
        """LLM에 한 턴을 요약하게 하고 JSON memory 후보를 파싱한다."""

        instructions = (
            "Extract durable user memory candidates from the conversation turn. "
            "Return only JSON with this shape: "
            '{"memories":[{"content":"...","importance":1}]} '
            "Use Korean if the memory is Korean. "
            "Only include stable user preferences, facts, or goals. "
            "Return an empty memories array if there is nothing durable."
        )
        prompt = (
            f"User message:\n{user_message}\n\n"
            f"Assistant reply:\n{assistant_reply}\n\n"
            f"Maximum memories: {self._max_items}"
        )
        raw = await self._llm.generate(
            (LLMMessage(role="user", content=prompt),),
            instructions=instructions,
        )
        return self._parse(raw)

    def _parse(self, raw: str) -> list[ExtractedMemory]:
        """LLM JSON 문자열을 안전하게 제한된 후보 목록으로 변환한다."""

        try:
            payload: Any = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Memory extraction returned invalid JSON")
            return []

        items = payload.get("memories", []) if isinstance(payload, dict) else []
        if not isinstance(items, list):
            return []

        memories: list[ExtractedMemory] = []
        for item in items[: self._max_items]:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            try:
                importance = int(item.get("importance", 3))
            except (TypeError, ValueError):
                importance = 3
            memories.append(
                ExtractedMemory(
                    content=content[:5_000],
                    importance=min(5, max(1, importance)),
                )
            )
        return memories

    async def extract_and_store(
        self,
        *,
        user_message: str,
        assistant_reply: str,
        character_id: uuid.UUID,
    ) -> int:
        """추출된 후보를 현재 캐릭터 범위 memory로 저장하고 저장 개수를 반환한다."""

        memories = await self.extract(
            user_message=user_message,
            assistant_reply=assistant_reply,
        )
        if not memories:
            return 0

        try:
            # DB 쓰기 전에 모든 vector를 만들어 provider 실패 시 부분 저장을 피한다.
            vectors = [
                await self._embedding_provider.embed(memory.content)
                for memory in memories
            ]
            for memory, vector in zip(memories, vectors, strict=True):
                saved = await self._memories.create(
                    MemoryCreate(
                        content=memory.content,
                        character_id=character_id,
                        importance=memory.importance,
                    ),
                    user_id=self._user_id,
                )
                await self._embeddings.upsert(
                    memory_id=saved.id,
                    provider=self._embedding_provider.provider_name,
                    vector=vector,
                )
            await self._session.commit()
            return len(memories)
        except SQLAlchemyError as exc:
            await self._session.rollback()
            logger.warning("Failed to store extracted memories: %s", exc)
            return 0
