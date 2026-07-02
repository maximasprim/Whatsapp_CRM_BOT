from __future__ import annotations

from typing import Any, AsyncIterator

from openai import AsyncOpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.ai.providers.base import (
    AIProvider,
    CompletionResponse,
    EmbeddingResponse,
    Message,
    MessageRole,
    ToolDefinition,
    TokenUsage,
)
from app.core.config import settings
from app.core.exceptions import AIProviderException, AIRateLimitException
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider(AIProvider):
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            max_retries=0,  # We handle retries via tenacity
        )
        self._model = settings.OPENAI_MODEL
        self._embedding_model = settings.OPENAI_EMBEDDING_MODEL

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def embedding_dimensions(self) -> int:
        return settings.OPENAI_EMBEDDING_DIMENSIONS

    def _build_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        result = []
        for msg in messages:
            m: dict[str, Any] = {"role": msg.role.value, "content": msg.content}
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            result.append(m)
        return result

    def _build_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        reraise=True,
    )
    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[ToolDefinition] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> CompletionResponse:
        try:
            kwargs: dict[str, Any] = {
                "model": self._model,
                "messages": self._build_messages(messages),
                "temperature": temperature if temperature is not None else settings.AI_TEMPERATURE,
                "max_tokens": max_tokens or settings.AI_MAX_TOKENS,
            }
            if tools:
                kwargs["tools"] = self._build_tools(tools)
                kwargs["tool_choice"] = "auto"
            if response_format:
                kwargs["response_format"] = response_format

            response = await self._client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
            )
            tool_calls = None
            if choice.message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ]
            return CompletionResponse(
                content=choice.message.content or "",
                usage=usage,
                model=response.model,
                finish_reason=choice.finish_reason or "stop",
                tool_calls=tool_calls,
            )
        except RateLimitError as exc:
            raise AIRateLimitException(str(exc)) from exc
        except Exception as exc:
            logger.error("OpenAI completion error", error=str(exc))
            raise AIProviderException(f"OpenAI error: {exc}") from exc

    async def stream(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        try:
            async with self._client.chat.completions.stream(
                model=self._model,
                messages=self._build_messages(messages),
                temperature=temperature if temperature is not None else settings.AI_TEMPERATURE,
                max_tokens=max_tokens or settings.AI_MAX_TOKENS,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except RateLimitError as exc:
            raise AIRateLimitException(str(exc)) from exc
        except Exception as exc:
            raise AIProviderException(f"OpenAI streaming error: {exc}") from exc

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(settings.AI_MAX_RETRIES),
        reraise=True,
    )
    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        try:
            response = await self._client.embeddings.create(
                model=self._embedding_model,
                input=texts,
                dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS,
            )
            embeddings = [item.embedding for item in response.data]
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                total_tokens=response.usage.total_tokens,
            )
            return EmbeddingResponse(
                embeddings=embeddings, usage=usage, model=self._embedding_model
            )
        except Exception as exc:
            raise AIProviderException(f"OpenAI embedding error: {exc}") from exc

    async def embed_single(self, text: str) -> list[float]:
        response = await self.embed([text])
        return response.embeddings[0]
