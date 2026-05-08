from __future__ import annotations

from typing import Any, cast

from anthropic import NOT_GIVEN, AsyncAnthropic
from anthropic.types import Message as AnthropicMessageResponse
from anthropic.types import TextBlock, ToolUseBlock

from spanweave.llm.adapter import (
    CostPolicy,
    JsonValue,
    LLMAdapter,
    LLMProviderError,
    Message,
    Response,
    ToolCall,
    ToolDefinition,
)
from spanweave.llm.capabilities import CapabilityManifest, CapabilityRequirements


class AnthropicAdapter(LLMAdapter):
    def __init__(
        self,
        manifest: CapabilityManifest,
        *,
        client: AsyncAnthropic | Any | None = None,
        api_key: str | None = None,
        max_output_tokens: int = 4096,
    ) -> None:
        super().__init__(manifest, max_output_tokens=max_output_tokens)
        self._client: Any = client or AsyncAnthropic(api_key=api_key)

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        required_capabilities: CapabilityRequirements | None = None,
        *,
        run_id: str | None = None,
        policy: CostPolicy | None = None,
    ) -> Response:
        self.ensure_supported(required_capabilities)
        self.enforce_cost_policy(messages, tools, run_id=run_id, policy=policy)

        system_prompt, anthropic_messages = self._serialize_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self.manifest.model,
            "max_tokens": self.max_output_tokens,
            "messages": anthropic_messages,
            "system": system_prompt if system_prompt else NOT_GIVEN,
            "tools": self._serialize_tools(tools) if tools else NOT_GIVEN,
        }

        try:
            provider_response = cast(
                AnthropicMessageResponse,
                await self._client.messages.create(**kwargs),
            )
        except Exception as exc:
            raise LLMProviderError(
                provider=self.manifest.provider,
                model=self.manifest.model,
                operation="generate",
                message=str(exc),
            ) from exc
        return self._normalize_response(provider_response)

    def _serialize_messages(self, messages: list[Message]) -> tuple[str, list[dict[str, Any]]]:
        system_parts: list[str] = []
        provider_messages: list[dict[str, Any]] = []
        text_replayed_tool_call_ids: set[str] = set()

        for message in messages:
            if message.role == "system":
                system_parts.append(message.content)
                continue

            if message.role == "user":
                provider_messages.append({"role": "user", "content": message.content})
                continue

            if message.role == "tool":
                if message.tool_call_id in text_replayed_tool_call_ids:
                    provider_messages.append(
                        {
                            "role": "user",
                            "content": self._render_tool_result_text(message),
                        }
                    )
                else:
                    provider_messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": message.tool_call_id,
                                    "content": message.content,
                                }
                            ],
                        }
                    )
                continue

            if message.tool_calls:
                blocks: list[dict[str, Any]] = []
                if message.content:
                    blocks.append({"type": "text", "text": message.content})
                for tool_call in message.tool_calls:
                    tool_input = self._normalize_tool_input(tool_call.arguments)
                    if tool_input is None:
                        text_replayed_tool_call_ids.add(tool_call.id)
                        blocks.append(
                            {
                                "type": "text",
                                "text": self._render_tool_call_text(tool_call),
                            }
                        )
                    else:
                        blocks.append(
                            {
                                "type": "tool_use",
                                "id": tool_call.id,
                                "name": tool_call.name,
                                "input": tool_input,
                            }
                        )
                provider_messages.append({"role": "assistant", "content": blocks})
            else:
                provider_messages.append({"role": "assistant", "content": message.content})

        return "\n\n".join(system_parts), provider_messages

    def _serialize_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for tool in tools:
            payload: dict[str, Any] = {
                "name": tool.name,
                "input_schema": tool.input_schema,
            }
            if tool.description:
                payload["description"] = tool.description
            serialized.append(payload)
        return serialized

    def _normalize_response(self, provider_response: AnthropicMessageResponse) -> Response:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in provider_response.content:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
            elif isinstance(block, ToolUseBlock):
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        usage = provider_response.usage
        return self.build_response(
            response_id=provider_response.id,
            content="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=getattr(provider_response, "stop_reason", None),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )

    def _normalize_tool_input(self, arguments: JsonValue) -> dict[str, Any] | None:
        if isinstance(arguments, dict):
            return arguments
        return None

    def _render_tool_call_text(self, tool_call: ToolCall) -> str:
        rendered_arguments = self._render_tool_call_arguments(tool_call)
        return (
            f"Replayed tool call {tool_call.name} "
            f"(id={tool_call.id}) with non-object arguments: {rendered_arguments}"
        )

    def _render_tool_result_text(self, message: Message) -> str:
        return f"Tool result for {message.tool_call_id}: {message.content}"

    def _render_tool_call_arguments(self, tool_call: ToolCall) -> str:
        if tool_call.raw_arguments is not None:
            return tool_call.raw_arguments
        return str(tool_call.arguments)
