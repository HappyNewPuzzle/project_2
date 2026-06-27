"""OpenAI 호출을 교체 가능한 LLMProvider 인터페이스 뒤에 숨긴다."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Protocol, Sequence

from openai import AsyncOpenAI, OpenAIError

from app.core.config import get_settings


class LLMConfigurationError(RuntimeError):
    """API 키처럼 provider 실행에 필수인 설정이 없을 때 발생한다."""


class LLMServiceError(RuntimeError):
    """외부 LLM 요청 실패를 애플리케이션 공통 오류로 변환한다."""


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """LLM에 전달할 한 개의 과거 발화."""

    # Literal을 사용하면 지원하지 않는 role을 타입 검사 단계에서 발견할 수 있다.
    role: Literal["user", "assistant"]
    content: str


class LLMProvider(Protocol):
    """ChatService가 특정 LLM SDK에 의존하지 않게 하는 계약."""

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> str:
        """Generate one assistant response."""
        ...

    def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> AsyncGenerator[str, None]:
        """Yield assistant response text as it is generated."""
        ...


class OpenAILLMProvider:
    """OpenAI Responses API를 사용하는 LLMProvider 구현체."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        system_prompt: str,
        max_output_tokens: int,
    ) -> None:
        # 키가 없을 때 SDK 객체를 만들지 않아 서버 자체는 정상 기동할 수 있다.
        self._client = AsyncOpenAI(api_key=api_key) if api_key else None
        self._model = model
        self._system_prompt = system_prompt
        self._max_output_tokens = max_output_tokens

    def _instructions(self, character_instructions: str) -> str:
        """서비스 공통 규칙과 캐릭터별 규칙을 높은 우선순위 지침으로 합친다."""

        return f"{self._system_prompt}\n\n{character_instructions}".strip()

    @staticmethod
    def _input(messages: Sequence[LLMMessage]) -> list[dict[str, str]]:
        """내부 메시지 객체를 Responses API가 받는 role/content dict로 바꾼다."""

        return [
            {"role": message.role, "content": message.content}
            for message in messages
        ]

    async def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> str:
        """전체 답변이 완성될 때까지 기다린 뒤 문자열 하나를 반환한다."""

        if self._client is None:
            raise LLMConfigurationError("OPENAI_API_KEY is missing")

        try:
            # 캐릭터 지침은 instructions, 대화 기록은 input 역할 배열로 분리한다.
            response = await self._client.responses.create(
                model=self._model,
                instructions=self._instructions(instructions),
                input=self._input(messages),
                max_output_tokens=self._max_output_tokens,
            )
        except OpenAIError as exc:
            # 라우터가 OpenAI SDK 세부 예외를 몰라도 되도록 공통 예외로 감싼다.
            raise LLMServiceError("OpenAI API request failed") from exc

        # output_text는 SDK가 여러 text output 조각을 합쳐 주는 편의 속성이다.
        reply = response.output_text.strip()
        if not reply:
            raise LLMServiceError("OpenAI API returned an empty response")
        return reply

    async def stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        instructions: str,
    ) -> AsyncGenerator[str, None]:
        """Responses API 이벤트에서 텍스트 delta만 골라 순서대로 전달한다."""

        if self._client is None:
            raise LLMConfigurationError("OPENAI_API_KEY is missing")

        upstream = None
        received_text = False
        try:
            # stream=True이면 완성 응답 대신 typed event의 비동기 스트림이 돌아온다.
            upstream = await self._client.responses.create(
                model=self._model,
                instructions=self._instructions(instructions),
                input=self._input(messages),
                max_output_tokens=self._max_output_tokens,
                stream=True,
            )
            async for event in upstream:
                # 생성 시작/완료 등 다른 이벤트는 숨기고 실제 화면용 텍스트만 내보낸다.
                if event.type == "response.output_text.delta":
                    received_text = True
                    yield event.delta
        except OpenAIError as exc:
            raise LLMServiceError("OpenAI API streaming request failed") from exc
        finally:
            # 클라이언트 연결 종료나 예외 상황에도 외부 HTTP 스트림을 닫는다.
            if upstream is not None:
                await upstream.close()

        if not received_text:
            raise LLMServiceError("OpenAI API returned an empty stream")


@lru_cache
def get_llm_provider() -> LLMProvider:
    """설정으로 OpenAI provider를 한 번만 만들고 재사용한다."""

    settings = get_settings()
    return OpenAILLMProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        system_prompt=settings.llm_system_prompt,
        max_output_tokens=settings.llm_max_output_tokens,
    )
