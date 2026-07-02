from __future__ import annotations

import json
from typing import Any, AsyncIterator

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
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


class GeminiProvider(AIProvider):
    def __init__(self) -> None:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._model_name = settings.GEMINI_MODEL
        self._embedding_model = settings.GEMINI_EMBEDDING_MODEL
        self._model = genai.GenerativeModel(self._model_name)

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def embedding_dimensions(self) -> int:
        return settings.GEMINI_EMBEDDING_DIMENSIONS

    def _convert_messages(
        self, messages: list[Message]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Split out system instruction and convert messages to Gemini format."""
        system_instruction: str | None = None
        history: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_instruction = msg.content
            elif msg.role == MessageRole.USER:
                history.append({"role": "user", "parts": [msg.content]})
            elif msg.role == MessageRole.ASSISTANT:
                history.append({"role": "model", "parts": [msg.content]})

        return system_instruction, history

    def _build_tool_config(
        self, tools: list[ToolDefinition]
    ) -> list[genai.protos.Tool]:
        function_declarations = []
        for tool in tools:
            function_declarations.append(
                genai.protos.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            k: genai.protos.Schema(
                                type=genai.protos.Type.STRING,
                                description=v.get("description", ""),
                            )
                            for k, v in tool.parameters.get("properties", {}).items()
                        },
                        required=tool.parameters.get("required", []),
                    ),
                )
            )
        return [genai.protos.Tool(function_declarations=function_declarations)]

    @retry(
        retry=retry_if_exception_type(ResourceExhausted),
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
            system_instruction, history = self._convert_messages(messages)
            model = genai.GenerativeModel(
                self._model_name,
                system_instruction=system_instruction,
            )
            generation_config = genai.GenerationConfig(
                temperature=temperature if temperature is not None else settings.AI_TEMPERATURE,
                max_output_tokens=max_tokens or settings.AI_MAX_TOKENS,
            )
            gemini_tools = self._build_tool_config(tools) if tools else None

            if not history:
                response = await model.generate_content_async(
                    "",
                    generation_config=generation_config,
                    tools=gemini_tools,
                )
            else:
                # Use the last user message as current content
                *prior, last = history
                chat = model.start_chat(history=prior)
                response = await chat.send_message_async(
                    last["parts"][0],
                    generation_config=generation_config,
                    tools=gemini_tools,
                )

            content = ""
            tool_calls = None
            if response.candidates:
                candidate = response.candidates[0]
                for part in candidate.content.parts:
                    if hasattr(part, "text") and part.text:
                        content += part.text
                    elif hasattr(part, "function_call") and part.function_call:
                        if tool_calls is None:
                            tool_calls = []
                        tool_calls.append(
                            {
                                "id": f"call_{part.function_call.name}",
                                "type": "function",
                                "function": {
                                    "name": part.function_call.name,
                                    "arguments": json.dumps(
                                        dict(part.function_call.args)
                                    ),
                                },
                            }
                        )

            usage = TokenUsage()
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage.prompt_tokens = response.usage_metadata.prompt_token_count or 0
                usage.completion_tokens = (
                    response.usage_metadata.candidates_token_count or 0
                )
                usage.total_tokens = response.usage_metadata.total_token_count or 0

            return CompletionResponse(
                content=content,
                usage=usage,
                model=self._model_name,
                finish_reason="stop",
                tool_calls=tool_calls,
            )
        except ResourceExhausted as exc:
            raise AIRateLimitException(str(exc)) from exc
        except Exception as exc:
            logger.error("Gemini completion error", error=str(exc))
            raise AIProviderException(f"Gemini error: {exc}") from exc

    async def stream(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        try:
            system_instruction, history = self._convert_messages(messages)
            model = genai.GenerativeModel(
                self._model_name,
                system_instruction=system_instruction,
            )
            generation_config = genai.GenerationConfig(
                temperature=temperature if temperature is not None else settings.AI_TEMPERATURE,
                max_output_tokens=max_tokens or settings.AI_MAX_TOKENS,
            )
            *prior, last = history if history else [None, {"parts": [""]}]
            chat = model.start_chat(history=prior)
            async for chunk in await chat.send_message_async(
                last["parts"][0],
                generation_config=generation_config,
                stream=True,
            ):
                if chunk.text:
                    yield chunk.text
        except ResourceExhausted as exc:
            raise AIRateLimitException(str(exc)) from exc
        except Exception as exc:
            raise AIProviderException(f"Gemini streaming error: {exc}") from exc

    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        try:
            embeddings = []
            total_tokens = 0
            for text in texts:
                result = genai.embed_content(
                    model=self._embedding_model,
                    content=text,
                    task_type="retrieval_document",
                )
                embeddings.append(result["embedding"])
            return EmbeddingResponse(
                embeddings=embeddings,
                usage=TokenUsage(total_tokens=total_tokens),
                model=self._embedding_model,
            )
        except Exception as exc:
            raise AIProviderException(f"Gemini embedding error: {exc}") from exc

    async def embed_single(self, text: str) -> list[float]:
        response = await self.embed([text])
        return response.embeddings[0]
