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
    try:
        character = await service.create(payload)
    except CharacterPersistenceError as exc:
        logger.exception("Failed to create character")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Character could not be stored.",
        ) from exc
    return CharacterResponse.model_validate(character)


@router.get("", response_model=list[CharacterResponse])
async def list_characters(
    service: CharacterServiceDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[CharacterResponse]:
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
    try:
        character = await service.get(character_id)
    except CharacterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found.",
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
    try:
        character = await service.update(character_id, payload)
    except CharacterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found.",
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
    try:
        await service.delete(character_id)
    except CharacterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found.",
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
