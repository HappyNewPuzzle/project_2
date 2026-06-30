"""HTTP 요청 ID 전파와 접근 로그를 담당하는 순수 ASGI middleware."""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.types import Message, Receive, Scope, Send

from app.core.logging import request_id_context

logger = logging.getLogger("app.access")
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class RequestContextMiddleware:
    """요청별 ID, 응답 헤더, 처리 시간 로그를 추가한다."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        # WebSocket이나 lifespan 이벤트에는 HTTP 접근 로그를 적용하지 않는다.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        incoming = headers.get(b"x-request-id", b"").decode("latin-1")
        # 지나치게 긴 외부 값을 로그에 넣지 않고 새 UUID로 대체한다.
        request_id = incoming if 0 < len(incoming) <= 128 else str(uuid.uuid4())
        context_token = request_id_context.set(request_id)
        started_at = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = list(message.get("headers", []))
                response_headers.append(
                    (b"x-request-id", request_id.encode("latin-1"))
                )
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            logger.exception(
                "Unhandled request error",
                extra={"event": "request_failed"},
            )
            raise
        finally:
            duration_ms = round(
                (time.perf_counter() - started_at) * 1000,
                2,
            )
            client = scope.get("client")
            logger.info(
                "Request completed",
                extra={
                    "event": "request_completed",
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client[0] if client else None,
                },
            )
            request_id_context.reset(context_token)
