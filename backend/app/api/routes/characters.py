"""캐릭터 생성·목록·상세·수정·삭제 REST API."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dependencies import CharacterServiceDependency
from app.schemas.character import (
    CharacterCreate,
    CharacterResponse,
    CharacterUpdate,
)
from app.services.character_service import (
    CharacterAccessDeniedError,
    CharacterInUseError,
    CharacterNotFoundError,
    CharacterPersistenceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/characters", tags=["characters"])


@router.post(
    "",
    response_model=CharacterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_character(
    payload: CharacterCreate,
    service: CharacterServiceDependency,
) -> CharacterResponse:
    """검증된 캐릭터 데이터를 저장하고 201 응답을 반환한다."""

    try:
        character = await service.create(payload)
    except CharacterPersistenceError as exc:
        logger.exception("Failed to create character")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Character could not be stored.",
        ) from exc
    # ORM 객체를 외부 공개용 Pydantic 응답으로 명시적으로 변환한다.
    return CharacterResponse.model_validate(character)


@router.get("", response_model=list[CharacterResponse])
async def list_characters(
    service: CharacterServiceDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[CharacterResponse]:
    """offset/limit 기반으로 캐릭터 목록을 조회한다."""

    try:
        characters = await service.list(offset=offset, limit=limit)
    except CharacterPersistenceError as exc:
        logger.exception("Failed to list characters")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Characters could not be loaded.",
        ) from exc
    return [CharacterResponse.model_validate(character) for character in characters]


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(
    character_id: uuid.UUID,
    service: CharacterServiceDependency,
) -> CharacterResponse:
    """UUID에 해당하는 캐릭터 하나를 반환한다."""

    try:
        character = await service.get(character_id)
    except CharacterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found.",
        ) from exc
    except CharacterAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this character.",
        ) from exc
    except CharacterPersistenceError as exc:
        logger.exception("Failed to get character")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Character could not be loaded.",
        ) from exc
    return CharacterResponse.model_validate(character)


@router.patch("/{character_id}", response_model=CharacterResponse)
async def update_character(
    character_id: uuid.UUID,
    payload: CharacterUpdate,
    service: CharacterServiceDependency,
) -> CharacterResponse:
    """요청 JSON에 포함된 필드만 부분 수정한다."""

    try:
        character = await service.update(character_id, payload)
    except CharacterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found.",
        ) from exc
    except CharacterAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this character.",
        ) from exc
    except CharacterPersistenceError as exc:
        logger.exception("Failed to update character")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Character could not be stored.",
        ) from exc
    return CharacterResponse.model_validate(character)


@router.delete(
    "/{character_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_character(
    character_id: uuid.UUID,
    service: CharacterServiceDependency,
) -> Response:
    """사용 중이지 않은 캐릭터를 삭제하고 본문 없는 204를 반환한다."""

    try:
        await service.delete(character_id)
    except CharacterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found.",
        ) from exc
    except CharacterAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this character.",
        ) from exc
    except CharacterInUseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Character is used by an existing conversation.",
        ) from exc
    except CharacterPersistenceError as exc:
        logger.exception("Failed to delete character")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Character could not be deleted.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
