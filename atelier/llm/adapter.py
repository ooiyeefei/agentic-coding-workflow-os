from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atelier.llm.capabilities import (
    CapabilityManifest,
    CapabilityRequirements,
    UnsupportedCapabilityError,
)

JsonValue: TypeAlias = dict[str, Any] | list[Any] | str | int | float | bool | None


def _json_object() -> dict[str, Any]:
    return {}


def _tool_call_list() -> list[ToolCall]:
    return []


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    arguments: JsonValue = None
    raw_arguments: str | None = None


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=_json_object)
    strict: bool = True


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=_tool_call_list)

    @model_validator(mode="after")
    def validate_message_shape(self) -> Message:
        if self.role == "tool" and not self.tool_call_id:
            raise ValueError("tool messages require tool_call_id")
        if self.role != "assistant" and self.tool_calls:
            raise ValueError("tool_calls are only valid on assistant messages")
        return self


class Usage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int | None = None

    @model_validator(mode="after")
    def populate_total_tokens(self) -> Usage:
        if self.total_tokens is None:
            self.total_tokens = self.input_tokens + self.output_tokens
        return self


class Cost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_usd: float = 0.0
    output_usd: float = 0.0
    total_usd: float | None = None

    @model_validator(mode="after")
    def populate_total_cost(self) -> Cost:
        if self.total_usd is None:
            self.total_usd = self.input_usd + self.output_usd
        return self


class Response(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    provider: str
    model: str
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=_tool_call_list)
    stop_reason: str | None = None
    usage: Usage = Field(default_factory=Usage)
    cost: Cost = Field(default_factory=Cost)


class LLMError(RuntimeError):
    """Base error for the LLM adapter layer."""


class LLMProviderError(LLMError):
    def __init__(
        self,
        *,
        provider: str,
        model: str,
        operation: str,
        message: str,
    ) -> None:
        self.provider = provider
        self.model = model
        self.operation = operation
        super().__init__(
            f"{provider} adapter failed during {operation} for model {model}: {message}"
        )


class LLMConfigurationError(LLMError):
    """Raised when a manifest makes claims unsupported by the current adapter contract."""


class LLMAdapter(ABC):
    def __init__(self, manifest: CapabilityManifest, *, max_output_tokens: int = 4096) -> None:
        self.manifest = manifest
        self.max_output_tokens = max_output_tokens

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        required_capabilities: CapabilityRequirements | None = None,
    ) -> Response:
        """Generate a normalized provider response."""

    def ensure_supported(
        self, required_capabilities: CapabilityRequirements | None = None
    ) -> None:
        requirements = required_capabilities or CapabilityRequirements()
        missing = self.manifest.missing_capabilities(requirements)
        if missing:
            raise UnsupportedCapabilityError(
                requirements=requirements,
                failures={self.manifest.model: missing},
            )

    def build_response(
        self,
        *,
        response_id: str | None,
        content: str,
        tool_calls: list[ToolCall],
        stop_reason: str | None,
        input_tokens: int,
        output_tokens: int,
    ) -> Response:
        usage = Usage(input_tokens=input_tokens, output_tokens=output_tokens)
        input_cost = self.manifest.cost_per_mtok_in * usage.input_tokens / 1_000_000
        output_cost = self.manifest.cost_per_mtok_out * usage.output_tokens / 1_000_000
        cost = Cost(input_usd=input_cost, output_usd=output_cost)
        return Response(
            id=response_id,
            provider=self.manifest.provider,
            model=self.manifest.model,
            content=content,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage=usage,
            cost=cost,
        )
