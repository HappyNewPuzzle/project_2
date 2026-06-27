"""일반 JSON 채팅과 SSE 스트리밍 채팅 HTTP 엔드포인트."""

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

# prefix를 한 번 선언해 아래 경로들이 /chat 아래에 묶이게 한다.
router = APIRouter(prefix="/chat", tags=["chat"])


def _sse(event: str, data: dict[str, object]) -> str:
    """SSE 규격의 event/data 한 묶음을 문자열로 직렬화한다."""

    # ensure_ascii=False를 사용하면 한국어가 \uXXXX 형태로 바뀌지 않는다.
    payload = json.dumps(data, ensure_ascii=False)
    # SSE 이벤트 하나는 빈 줄 두 개로 끝나야 클라이언트가 즉시 처리한다.
    return f"event: {event}\ndata: {payload}\n\n"


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    chat_service: ChatServiceDependency,
) -> ChatResponse:
    """메시지를 저장하고 완성된 AI 답변을 JSON으로 반환한다."""

    try:
        result = await chat_service.reply(
            request.message,
            request.conversation_id,
            request.character_id,
        )
    # 서비스 계층의 도메인 예외를 의미에 맞는 HTTP 상태 코드로 변환한다.
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
    """메시지를 먼저 저장한 뒤 AI 답변을 SSE 이벤트로 실시간 전송한다."""

    try:
        # StreamingResponse 헤더를 보내기 전에 DB 검증을 끝내야 404/409를 보낼 수 있다.
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
        """StreamingResponse가 소비할 비동기 SSE 생성기."""

        # 프론트가 새 대화 ID를 즉시 저장할 수 있도록 텍스트보다 먼저 보낸다.
        yield _sse(
            "conversation",
            {
                "conversation_id": str(turn.conversation_id),
                "character_id": str(turn.character_id),
            },
        )
        try:
            # aclosing으로 클라이언트 이탈 시 내부 생성기까지 닫는다.
            async with aclosing(
                chat_service.stream_reply(turn)
            ) as deltas:
                async for delta in deltas:
                    # 연결이 끊겼다면 더 이상 비용이 들지 않도록 생성을 종료한다.
                    if await request.is_disconnected():
                        logger.info("Streaming client disconnected")
                        return
                    yield _sse("token", {"delta": delta})
        # 스트림 헤더는 이미 200으로 전송됐으므로 이후 오류는 SSE error로 알린다.
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

        # done 이벤트를 받은 클라이언트는 로딩 상태를 종료할 수 있다.
        yield _sse("done", {})

    # 프록시 버퍼링을 끄는 헤더를 넣어 토큰이 모였다가 한꺼번에 보이는 것을 막는다.
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
