"""구조화 JSON formatter가 요청 추적 필드를 보존하는지 검증한다."""

import json
import logging

from app.core.logging import JsonFormatter, RequestContextFilter, request_id_context


def test_json_formatter_includes_request_context() -> None:
    """로그 JSON에 request ID와 운영용 extra 필드가 포함되는지 확인한다."""

    token = request_id_context.set("request-abc")
    try:
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Request completed",
            args=(),
            exc_info=None,
        )
        record.event = "request_completed"
        record.status_code = 200
        RequestContextFilter().filter(record)

        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_context.reset(token)

    assert payload["message"] == "Request completed"
    assert payload["request_id"] == "request-abc"
    assert payload["event"] == "request_completed"
    assert payload["status_code"] == 200
