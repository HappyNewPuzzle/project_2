"""사용자 장기 기억 생성·조회·수정·삭제 API."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dependencies import (
    ChatRateLimitDependency,
    MemoryServiceDependency,
)
from app.schemas.memory import (
    MemoryCreate,
    MemoryReindexResponse,
    MemoryResponse,
    MemorySearchResponse,
    MemoryUpdate,
)
from app.services.character_service import CharacterNotFoundError
from app.services.memory_service import (
    MemoryIndexingError,
    MemoryNotFoundError,
    MemoryPersistenceError,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/memories", tags=["memories"])


@router.post(
    "",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_memory(
    payload: MemoryCreate,
    service: MemoryServiceDependency,
) -> MemoryResponse:
    """전역 또는 특정 캐릭터 범위의 기억을 저장한다."""

    try:
        memory = await service.create(payload)
    except CharacterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found.",
        ) from exc
    except (MemoryIndexingError, MemoryPersistenceError) as exc:
        logger.exception("Failed to create memory")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory could not be stored.",
        ) from exc
    return MemoryResponse.model_validate(memory)


@router.get("", response_model=list[MemoryResponse])
async def list_memories(
    service: MemoryServiceDependency,
    character_id: uuid.UUID | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[MemoryResponse]:
    """현재 사용자의 기억을 선택적 캐릭터 범위로 조회한다."""

    try:
        memories = await service.list(
            character_id=character_id,
            offset=offset,
            limit=limit,
        )
    except CharacterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found.",
        ) from exc
    except MemoryPersistenceError as exc:
        logger.exception("Failed to list memories")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memories could not be loaded.",
        ) from exc
    return [MemoryResponse.model_validate(memory) for memory in memories]


@router.get("/search", response_model=list[MemorySearchResponse])
async def search_memories(
    service: MemoryServiceDependency,
    _rate_limit: ChatRateLimitDependency,
    query: Annotated[str, Query(min_length=1, max_length=500)],
    character_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[MemorySearchResponse]:
    """현재 사용자 범위에서 query와 의미가 가까운 활성 기억을 검색한다."""

    normalized_query = query.strip()
    if not normalized_query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Search query must not be blank.",
        )
    try:
        matches = await service.search(
            normalized_query,
            character_id=character_id,
            limit=limit,
        )
    except CharacterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found.",
        ) from exc
    except (MemoryIndexingError, MemoryPersistenceError) as exc:
        logger.exception("Failed to search memories")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memories could not be searched.",
        ) from exc
    return [
        MemorySearchResponse(
            **MemoryResponse.model_validate(match.memory).model_dump(),
            score=match.score,
        )
        for match in matches
    ]


@router.post("/reindex", response_model=MemoryReindexResponse)
async def reindex_memories(
    service: MemoryServiceDependency,
    _rate_limit: ChatRateLimitDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> MemoryReindexResponse:
    """기존 기억 중 현재 provider vector가 없는 항목을 제한적으로 재색인한다."""

    try:
        indexed_count = await service.reindex(limit=limit)
    except (MemoryIndexingError, MemoryPersistenceError) as exc:
        logger.exception("Failed to reindex memories")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memories could not be reindexed.",
        ) from exc
    return MemoryReindexResponse(indexed_count=indexed_count)


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: uuid.UUID,
    service: MemoryServiceDependency,
) -> MemoryResponse:
    """현재 사용자 소유의 기억 한 건을 반환한다."""

    try:
        memory = await service.get(memory_id)
    except MemoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found.",
        ) from exc
    except MemoryPersistenceError as exc:
        logger.exception("Failed to get memory")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory could not be loaded.",
        ) from exc
    return MemoryResponse.model_validate(memory)


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    service: MemoryServiceDependency,
) -> MemoryResponse:
    """내용, 중요도 또는 활성 상태를 부분 수정한다."""

    try:
        memory = await service.update(memory_id, payload)
    except MemoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found.",
        ) from exc
    except (MemoryIndexingError, MemoryPersistenceError) as exc:
        logger.exception("Failed to update memory")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory could not be stored.",
        ) from exc
    return MemoryResponse.model_validate(memory)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: uuid.UUID,
    service: MemoryServiceDependency,
) -> Response:
    """현재 사용자 소유의 기억을 삭제한다."""

    try:
        await service.delete(memory_id)
    except MemoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found.",
        ) from exc
    except MemoryPersistenceError as exc:
        logger.exception("Failed to delete memory")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory could not be deleted.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
