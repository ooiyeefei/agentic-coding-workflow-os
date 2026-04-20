from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any, cast

from openai import NOT_GIVEN, AsyncOpenAI
from openai.types.responses import Response as OpenAIResponse
from openai.types.responses import ResponseFunctionToolCall

from atelier.llm.adapter import (
    JsonValue,
    LLMAdapter,
    LLMProviderError,
    Message,
    Response,
    ToolCall,
    ToolDefinition,
)
from atelier.llm.capabilities import CapabilityManifest, CapabilityRequirements


class OpenAIAdapter(LLMAdapter):
    def __init__(
        self,
        manifest: CapabilityManifest,
        *,
        client: AsyncOpenAI | Any | None = None,
        api_key: str | None = None,
        max_output_tokens: int = 4096,
    ) -> None:
        super().__init__(manifest, max_output_tokens=max_output_tokens)
        self._client: Any = client or AsyncOpenAI(api_key=api_key)

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        required_capabilities: CapabilityRequirements | None = None,
    ) -> Response:
        self.ensure_supported(required_capabilities)

        kwargs: dict[str, Any] = {
            "model": self.manifest.model,
            "input": self._serialize_messages(messages),
            "max_output_tokens": self.max_output_tokens,
            "tools": self._serialize_tools(tools) if tools else NOT_GIVEN,
            "parallel_tool_calls": (
                True if tools and self.manifest.offers.parallel_tool_use else NOT_GIVEN
            ),
        }

        try:
            provider_response = cast(
                OpenAIResponse,
                await self._client.responses.create(**kwargs),
            )
        except Exception as exc:
            raise LLMProviderError(
                provider=self.manifest.provider,
                model=self.manifest.model,
                operation="generate",
                message=str(exc),
            ) from exc
        return self._normalize_response(provider_response)

    def _serialize_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []

        for message in messages:
            if message.role == "tool":
                serialized.append(
                    {
                        "type": "function_call_output",
                        "call_id": message.tool_call_id,
                        "output": message.content,
                    }
                )
                continue

            if message.content:
                serialized.append(
                    {
                        "type": "message",
                        "role": message.role,
                        "content": message.content,
                    }
                )

            if message.role == "assistant":
                for tool_call in message.tool_calls:
                    serialized.append(
                        {
                            "type": "function_call",
                            "call_id": tool_call.id,
                            "name": tool_call.name,
                            "arguments": self._serialize_tool_arguments(tool_call),
                        }
                    )

        return serialized

    def _serialize_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for tool in tools:
            payload: dict[str, Any] = {
                "type": "function",
                "name": tool.name,
                "parameters": tool.input_schema,
                "strict": tool.strict,
            }
            if tool.description:
                payload["description"] = tool.description
            serialized.append(payload)
        return serialized

    def _normalize_response(self, provider_response: OpenAIResponse) -> Response:
        tool_calls: list[ToolCall] = []
        for item in provider_response.output:
            if not isinstance(item, ResponseFunctionToolCall):
                continue
            parsed_arguments, raw_arguments = self._parse_tool_arguments(item.arguments)
            tool_calls.append(
                ToolCall(
                    id=item.call_id,
                    name=item.name,
                    arguments=parsed_arguments,
                    raw_arguments=raw_arguments,
                )
            )

        usage = provider_response.usage
        return self.build_response(
            response_id=provider_response.id,
            content=provider_response.output_text,
            tool_calls=tool_calls,
            stop_reason=getattr(provider_response, "status", None),
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
        )

    def _parse_tool_arguments(self, raw_arguments: str) -> tuple[JsonValue, str | None]:
        try:
            return cast(JsonValue, json.loads(raw_arguments)), None
        except JSONDecodeError:
            return raw_arguments, raw_arguments

    def _serialize_tool_arguments(self, tool_call: ToolCall) -> str:
        if tool_call.raw_arguments is not None:
            return tool_call.raw_arguments
        return json.dumps(tool_call.arguments)
