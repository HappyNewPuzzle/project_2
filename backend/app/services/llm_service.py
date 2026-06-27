from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Protocol

from openai import AsyncOpenAI, OpenAIError

from app.core.config import get_settings


class LLMConfigurationError(RuntimeError):
    """Raised when the LLM provider is not configured."""


class LLMServiceError(RuntimeError):
    """Raised when the LLM provider request fails."""


class LLMProvider(Protocol):
    async def generate(self, message: str) -> str:
        """Generate one assistant response."""
        ...

    def stream(self, message: str) -> AsyncIterator[str]:
        """Yield assistant response text as it is generated."""
        ...


class OpenAILLMProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        system_prompt: str,
        max_output_tokens: int,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key) if api_key else None
        self._model = model
        self._system_prompt = system_prompt
        self._max_output_tokens = max_output_tokens

    async def generate(self, message: str) -> str:
        if self._client is None:
            raise LLMConfigurationError("OPENAI_API_KEY is missing")

        try:
            response = await self._client.responses.create(
                model=self._model,
                instructions=self._system_prompt,
                input=message,
                max_output_tokens=self._max_output_tokens,
            )
        except OpenAIError as exc:
            raise LLMServiceError("OpenAI API request failed") from exc

        reply = response.output_text.strip()
        if not reply:
            raise LLMServiceError("OpenAI API returned an empty response")
        return reply

    async def stream(self, message: str) -> AsyncIterator[str]:
        if self._client is None:
            raise LLMConfigurationError("OPENAI_API_KEY is missing")

        upstream = None
        received_text = False
        try:
            upstream = await self._client.responses.create(
                model=self._model,
                instructions=self._system_prompt,
                input=message,
                max_output_tokens=self._max_output_tokens,
                stream=True,
            )
            async for event in upstream:
                if event.type == "response.output_text.delta":
                    received_text = True
                    yield event.delta
        except OpenAIError as exc:
            raise LLMServiceError("OpenAI API streaming request failed") from exc
        finally:
            if upstream is not None:
                await upstream.close()

        if not received_text:
            raise LLMServiceError("OpenAI API returned an empty stream")


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    return OpenAILLMProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        system_prompt=settings.llm_system_prompt,
        max_output_tokens=settings.llm_max_output_tokens,
    )
