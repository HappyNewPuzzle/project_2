import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm_service import (
    LLMConfigurationError,
    LLMProvider,
    LLMServiceError,
    get_llm_provider,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])
LLMDependency = Annotated[LLMProvider, Depends(get_llm_provider)]


def _sse(event: str, data: dict[str, str]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, llm: LLMDependency) -> ChatResponse:
    try:
        reply = await llm.generate(request.message)
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

    return ChatResponse(reply=reply)


@router.post("/stream", response_class=StreamingResponse)
async def stream_chat(
    payload: ChatRequest,
    request: Request,
    llm: LLMDependency,
) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        try:
            async for delta in llm.stream(payload.message):
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

        yield _sse("done", {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
