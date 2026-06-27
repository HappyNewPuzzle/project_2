import json
import logging
from collections.abc import AsyncIterator
from contextlib import aclosing

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import ChatServiceDependency
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import (
    ChatPersistenceError,
    ConversationCharacterMismatchError,
    ConversationNotFoundError,
)
from app.services.character_service import CharacterNotFoundError
from app.services.llm_service import (
    LLMConfigurationError,
    LLMServiceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse(event: str, data: dict[str, object]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    chat_service: ChatServiceDependency,
) -> ChatResponse:
    try:
        result = await chat_service.reply(
            request.message,
            request.conversation_id,
            request.character_id,
        )
    except CharacterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found.",
        ) from exc
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        ) from exc
    except ConversationCharacterMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conversation belongs to a different character.",
        ) from exc
    except ChatPersistenceError as exc:
        logger.exception("Chat persistence failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat history could not be stored.",
        ) from exc
    except LLMConfigurationError as exc:
        logger.error("LLM configuration error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service is not configured.",
        ) from exc
    except LLMServiceError as exc:
        logger.exception("LLM request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LLM provider could not complete the request.",
        ) from exc

    return ChatResponse(
        conversation_id=result.conversation_id,
        character_id=result.character_id,
        reply=result.reply,
    )


@router.post("/stream", response_class=StreamingResponse)
async def stream_chat(
    payload: ChatRequest,
    request: Request,
    chat_service: ChatServiceDependency,
) -> StreamingResponse:
    try:
        turn = await chat_service.start_turn(
            payload.message,
            payload.conversation_id,
            payload.character_id,
        )
    except CharacterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found.",
        ) from exc
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        ) from exc
    except ConversationCharacterMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conversation belongs to a different character.",
        ) from exc
    except ChatPersistenceError as exc:
        logger.exception("Failed to store streaming user message")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat history could not be stored.",
        ) from exc

    async def event_stream() -> AsyncIterator[str]:
        yield _sse(
            "conversation",
            {
                "conversation_id": str(turn.conversation_id),
                "character_id": str(turn.character_id),
            },
        )
        try:
            async with aclosing(
                chat_service.stream_reply(turn)
            ) as deltas:
                async for delta in deltas:
                    if await request.is_disconnected():
                        logger.info("Streaming client disconnected")
                        return
                    yield _sse("token", {"delta": delta})
        except LLMConfigurationError:
            logger.error("LLM is not configured for streaming")
            yield _sse(
                "error",
                {
                    "code": "llm_not_configured",
                    "message": "LLM service is not configured.",
                },
            )
            return
        except LLMServiceError:
            logger.exception("LLM streaming request failed")
            yield _sse(
                "error",
                {
                    "code": "llm_request_failed",
                    "message": "The LLM provider could not complete the request.",
                },
            )
            return
        except ChatPersistenceError:
            logger.exception("Failed to store streaming assistant message")
            yield _sse(
                "error",
                {
                    "code": "chat_persistence_failed",
                    "message": "Chat history could not be stored.",
                },
            )
            return

        yield _sse("done", {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
