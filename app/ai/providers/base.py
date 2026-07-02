from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    role: MessageRole
    content: str
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class CompletionResponse:
    content: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = ""
    finish_reason: str = "stop"
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class EmbeddingResponse:
    embeddings: list[list[float]]
    usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = ""


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]


class AIProvider(ABC):
    """Abstract interface every AI provider must implement."""

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[ToolDefinition] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> CompletionResponse:
        """Generate a completion for the given messages."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream a completion token by token."""
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> EmbeddingResponse:
        """Generate embeddings for a list of texts."""
        ...

    @abstractmethod
    async def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def embedding_dimensions(self) -> int:
        ...
