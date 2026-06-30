"""요청 ID가 포함된 구조화 JSON 로그 설정."""

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# 비동기 요청마다 독립된 request_id를 보관하며 로그 필터가 읽는다.
request_id_context: ContextVar[str] = ContextVar(
    "request_id",
    default="-",
)


class RequestContextFilter(logging.Filter):
    """모든 로그 레코드에 현재 요청 ID를 추가한다."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


class JsonFormatter(logging.Formatter):
    """운영 로그 수집기가 파싱할 수 있는 한 줄 JSON formatter."""

    EXTRA_FIELDS = (
        "event",
        "method",
        "path",
        "status_code",
        "duration_ms",
        "client_ip",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        # 요청 middleware가 extra로 넣은 운영 필드만 명시적으로 공개한다.
        for field in self.EXTRA_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str, *, json_logs: bool) -> None:
    """root logger를 stdout용 JSON 또는 사람이 읽기 쉬운 형식으로 설정한다."""

    handler = logging.StreamHandler()
    handler.addFilter(RequestContextFilter())
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s "
                "[request_id=%(request_id)s]: %(message)s"
            )
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)
