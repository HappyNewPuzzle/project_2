"""대화방 목록, 메시지 조회, 삭제 API."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dependencies import ConversationServiceDependency
from app.schemas.conversation import ConversationResponse, MessageResponse
from app.services.conversation_service import (
    ConversationNotFoundError,
    ConversationPersistenceError,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    service: ConversationServiceDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ConversationResponse]:
    """현재 사용자의 대화방 목록을 최근 활동순으로 반환한다."""

    try:
        conversations = await service.list(offset=offset, limit=limit)
    except ConversationPersistenceError as exc:
        logger.exception("Failed to list conversations")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Conversations could not be loaded.",
        ) from exc
    return [
        ConversationResponse.model_validate(conversation)
        for conversation in conversations
    ]


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_conversation_messages(
    conversation_id: uuid.UUID,
    service: ConversationServiceDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[MessageResponse]:
    """현재 사용자 대화방의 메시지를 오래된 순서로 반환한다."""

    try:
        messages = await service.list_messages(
            conversation_id,
            offset=offset,
            limit=limit,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        ) from exc
    except ConversationPersistenceError as exc:
        logger.exception("Failed to list conversation messages")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Conversation messages could not be loaded.",
        ) from exc
    return [MessageResponse.model_validate(message) for message in messages]


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    service: ConversationServiceDependency,
) -> Response:
    """현재 사용자 대화방과 소속 메시지를 삭제한다."""

    try:
        await service.delete(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        ) from exc
    except ConversationPersistenceError as exc:
        logger.exception("Failed to delete conversation")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Conversation could not be deleted.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
