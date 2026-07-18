"""장기 기억 자동 추출 서비스의 파싱 규칙을 검증한다."""

from collections.abc import AsyncGenerator, Sequence

from app.services.llm_service import LLMMessage
from app.services.memory_extraction_service import MemoryExtractionService


class JsonMemoryLLMProvider:
    """테스트가 지정한 JSON 문자열을 그대로 반환하는 가짜 LLM."""

    def __init__(self, reply: str) -> None:
        self.reply = reply

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> str:
        return self.reply

    async def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> AsyncGenerator[str, None]:
        yield self.reply


def make_service(reply: str) -> MemoryExtractionService:
    """파싱 테스트에는 DB 저장을 쓰지 않으므로 session에는 None을 넣는다."""

    return MemoryExtractionService(
        None,  # type: ignore[arg-type]
        JsonMemoryLLMProvider(reply),
        user_id="00000000-0000-0000-0000-000000000001",  # type: ignore[arg-type]
        max_items=2,
    )


def test_parse_valid_memory_json() -> None:
    """정상 JSON을 중요도 범위가 보정된 memory 후보로 변환한다."""

    service = make_service(
        '{"memories":[{"content":"사용자는 천문학을 좋아한다","importance":9}]}'
    )

    memories = service._parse(service._llm.reply)  # type: ignore[attr-defined]

    assert len(memories) == 1
    assert memories[0].content == "사용자는 천문학을 좋아한다"
    assert memories[0].importance == 5


def test_parse_invalid_json_returns_empty_list() -> None:
    """LLM이 JSON이 아닌 문자열을 반환해도 빈 목록으로 안전하게 처리한다."""

    service = make_service("not json")

    assert service._parse("not json") == []


def test_parse_limits_memory_count() -> None:
    """LLM이 너무 많은 후보를 반환해도 max_items까지만 사용한다."""

    service = make_service(
        '{"memories":['
        '{"content":"a","importance":1},'
        '{"content":"b","importance":2},'
        '{"content":"c","importance":3}'
        "]}"
    )

    memories = service._parse(service._llm.reply)  # type: ignore[attr-defined]

    assert [memory.content for memory in memories] == ["a", "b"]
