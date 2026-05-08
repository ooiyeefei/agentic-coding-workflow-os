from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from anthropic.types import Message as AnthropicMessage
from openai.types.responses import Response as OpenAIResponse
from spanweave.defaults import DEFAULT_MODELS_DIR
from spanweave.llm.adapter import (
    LLMProviderError,
    Message,
    ToolCall,
    ToolDefinition,
)
from spanweave.llm.anthropic import AnthropicAdapter
from spanweave.llm.capabilities import (
    CapabilityManifest,
    CapabilityRequirements,
    UnsupportedCapabilityError,
    load_capability_manifests,
    route_persona_to_model,
)
from spanweave.llm.openai import OpenAIAdapter
from spanweave.policy import CostCapExceeded


def test_route_persona_to_model_matches_required_capabilities() -> None:
    requirements = CapabilityRequirements(tool_use=True, long_context=128000)
    incompatible = make_manifest(model="model-no-tools", tool_use=False, long_context=200000)
    compatible = make_manifest(model="model-compatible", tool_use=True, long_context=200000)

    selected = route_persona_to_model(requirements, [incompatible, compatible])

    assert selected.model == "model-compatible"


def test_route_persona_to_model_raises_on_unsupported_capability() -> None:
    requirements = CapabilityRequirements(tool_use=True)
    incompatible = make_manifest(model="model-no-tools", tool_use=False)

    with pytest.raises(UnsupportedCapabilityError) as exc_info:
        route_persona_to_model(requirements, [incompatible])

    assert "tool_use=True" in str(exc_info.value)
    assert "model-no-tools" in str(exc_info.value)


def test_load_capability_manifests_reads_default_yaml_files() -> None:
    manifests = load_capability_manifests(DEFAULT_MODELS_DIR)

    assert {manifest.model for manifest in manifests} == {
        "claude-haiku-4-5",
        "claude-opus-4-7",
        "claude-sonnet-4-6",
        "gpt-4o-mini",
        "gpt-5",
    }


def test_shipped_manifests_include_reviewer_compatible_model() -> None:
    manifests = load_capability_manifests(DEFAULT_MODELS_DIR)

    selected = route_persona_to_model(
        CapabilityRequirements(
            tool_use=True,
            code_execution=True,
            structured_outputs=True,
        ),
        manifests,
    )

    assert selected.model == "gpt-5"


def test_adapter_allows_capability_claims_used_for_persona_routing() -> None:
    adapter = OpenAIAdapter(
        make_manifest(
            provider="openai",
            model="openai-reviewer",
            code_execution=True,
            structured_outputs=True,
        ),
        client=SimpleNamespace(responses=SimpleNamespace(create=AsyncMock())),
    )

    assert adapter.manifest.offers.code_execution is True
    assert adapter.manifest.offers.structured_outputs is True


@pytest.mark.asyncio
async def test_openai_preserves_malformed_tool_arguments_on_roundtrip() -> None:
    provider_response = OpenAIResponse.model_validate(
        {
            "id": "resp_roundtrip",
            "created_at": 0,
            "model": "ignored-provider-model",
            "object": "response",
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
            "status": "completed",
            "output": [],
            "usage": {
                "input_tokens": 1,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens": 1,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": 2,
            },
        }
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(return_value=provider_response))
    )
    adapter = OpenAIAdapter(
        make_manifest(provider="openai", model="openai-roundtrip"),
        client=client,
    )
    messages = [
        Message(
            role="assistant",
            tool_calls=[
                ToolCall(
                    id="call_bad",
                    name="lookup",
                    arguments="{oops",
                    raw_arguments="{oops",
                )
            ],
        )
    ]

    await adapter.generate(messages=messages)
    kwargs = client.responses.create.await_args.kwargs

    assert kwargs["input"][0]["arguments"] == "{oops"


@pytest.mark.asyncio
async def test_anthropic_replays_non_object_tool_arguments_as_text() -> None:
    provider_response = AnthropicMessage.model_validate(
        {
            "id": "msg_roundtrip",
            "type": "message",
            "role": "assistant",
            "model": "ignored-provider-model",
            "content": [{"type": "text", "text": "ok", "citations": []}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    )
    client = SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock(return_value=provider_response))
    )
    adapter = AnthropicAdapter(
        make_manifest(provider="anthropic", model="anthropic-roundtrip"),
        client=client,
    )
    messages = [
        Message(
            role="assistant",
            tool_calls=[ToolCall(id="call_list", name="lookup", arguments=["SF"])],
        ),
        Message(role="tool", tool_call_id="call_list", content="tool result"),
    ]

    await adapter.generate(messages=messages)
    kwargs = client.messages.create.await_args.kwargs
    serialized = kwargs["messages"]

    assert serialized[0]["role"] == "assistant"
    assert serialized[0]["content"][0]["type"] == "text"
    assert "non-object arguments" in serialized[0]["content"][0]["text"]
    assert serialized[1] == {"role": "user", "content": "Tool result for call_list: tool result"}


@pytest.mark.asyncio
async def test_anthropic_adapter_normalizes_response_and_cost() -> None:
    manifest = make_manifest(
        provider="anthropic",
        model="anthropic-test-model",
        tool_use=True,
        parallel_tool_use=True,
        long_context=200000,
        cost_per_mtok_in=2.0,
        cost_per_mtok_out=6.0,
    )
    provider_response = AnthropicMessage.model_validate(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "ignored-provider-model",
            "content": [
                {"type": "text", "text": "anthropic output", "citations": []},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "lookup",
                    "input": {"city": "SF"},
                },
            ],
            "usage": {"input_tokens": 1000, "output_tokens": 500},
            "stop_reason": "tool_use",
        }
    )
    client = SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock(return_value=provider_response))
    )
    adapter = AnthropicAdapter(manifest, client=client)

    response = await adapter.generate(
        messages=[
            Message(role="system", content="system prompt"),
            Message(role="user", content="hello"),
        ],
        tools=[
            ToolDefinition(
                name="lookup",
                description="Lookup by city",
                input_schema={"type": "object", "properties": {"city": {"type": "string"}}},
            )
        ],
        required_capabilities=CapabilityRequirements(tool_use=True),
    )

    assert response.provider == "anthropic"
    assert response.model == "anthropic-test-model"
    assert response.content == "anthropic output"
    assert response.tool_calls == [ToolCall(id="toolu_1", name="lookup", arguments={"city": "SF"})]
    assert response.stop_reason == "tool_use"
    assert response.usage.input_tokens == 1000
    assert response.usage.output_tokens == 500
    assert response.usage.total_tokens == 1500
    assert_close(response.cost.input_usd, 0.002)
    assert_close(response.cost.output_usd, 0.003)
    assert response.cost.total_usd is not None
    assert_close(response.cost.total_usd, 0.005)

    kwargs = client.messages.create.await_args.kwargs
    assert kwargs["model"] == "anthropic-test-model"
    assert kwargs["system"] == "system prompt"
    assert kwargs["tools"][0]["name"] == "lookup"


@pytest.mark.asyncio
async def test_openai_adapter_normalizes_response_and_cost() -> None:
    manifest = make_manifest(
        provider="openai",
        model="openai-test-model",
        tool_use=True,
        parallel_tool_use=True,
        long_context=200000,
        cost_per_mtok_in=1.5,
        cost_per_mtok_out=4.0,
    )
    provider_response = OpenAIResponse.model_validate(
        {
            "id": "resp_1",
            "created_at": 0,
            "model": "ignored-provider-model",
            "object": "response",
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
            "status": "completed",
            "output": [
                {
                    "id": "msg_1",
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {"type": "output_text", "text": "openai output", "annotations": []}
                    ],
                },
                {
                    "id": "fc_1",
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "lookup",
                    "arguments": '{"city": "SF"}',
                    "status": "completed",
                },
            ],
            "usage": {
                "input_tokens": 2000,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens": 500,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": 2500,
            },
        }
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(return_value=provider_response))
    )
    adapter = OpenAIAdapter(manifest, client=client)

    response = await adapter.generate(
        messages=[Message(role="user", content="hello")],
        tools=[
            ToolDefinition(
                name="lookup",
                description="Lookup by city",
                input_schema={"type": "object", "properties": {"city": {"type": "string"}}},
            )
        ],
        required_capabilities=CapabilityRequirements(tool_use=True),
    )

    assert response.provider == "openai"
    assert response.model == "openai-test-model"
    assert response.content == "openai output"
    assert response.tool_calls == [ToolCall(id="call_1", name="lookup", arguments={"city": "SF"})]
    assert response.stop_reason == "completed"
    assert response.usage.input_tokens == 2000
    assert response.usage.output_tokens == 500
    assert response.usage.total_tokens == 2500
    assert_close(response.cost.input_usd, 0.003)
    assert_close(response.cost.output_usd, 0.002)
    assert response.cost.total_usd is not None
    assert_close(response.cost.total_usd, 0.005)

    kwargs = client.responses.create.await_args.kwargs
    assert kwargs["model"] == "openai-test-model"
    assert kwargs["parallel_tool_calls"] is True
    assert kwargs["tools"][0]["name"] == "lookup"


@pytest.mark.asyncio
async def test_adapter_rejects_unsupported_capability_before_provider_call() -> None:
    manifest = make_manifest(provider="openai", model="openai-no-tools", tool_use=False)
    client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock()))
    adapter = OpenAIAdapter(manifest, client=client)

    with pytest.raises(UnsupportedCapabilityError):
        await adapter.generate(
            messages=[Message(role="user", content="hello")],
            required_capabilities=CapabilityRequirements(tool_use=True),
        )

    client.responses.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_openai_adapter_checks_policy_before_provider_call(fixed_run_id: str) -> None:
    manifest = make_manifest(provider="openai", model="openai-cost-check")
    client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock()))
    adapter = OpenAIAdapter(manifest, client=client)
    policy = RejectingPolicy()

    with pytest.raises(CostCapExceeded):
        await adapter.generate(
            messages=[Message(role="user", content="hello")],
            run_id=fixed_run_id,
            policy=policy,
        )

    assert policy.calls[0]["run_id"] == fixed_run_id
    client.responses.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_anthropic_adapter_checks_policy_before_provider_call(fixed_run_id: str) -> None:
    manifest = make_manifest(provider="anthropic", model="anthropic-cost-check")
    client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    adapter = AnthropicAdapter(manifest, client=client)
    policy = RejectingPolicy()

    with pytest.raises(CostCapExceeded):
        await adapter.generate(
            messages=[Message(role="user", content="hello")],
            run_id=fixed_run_id,
            policy=policy,
        )

    assert policy.calls[0]["run_id"] == fixed_run_id
    client.messages.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_anthropic_adapter_wraps_provider_errors() -> None:
    manifest = make_manifest(provider="anthropic", model="anthropic-provider-error")
    client = SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("anthropic boom")))
    )
    adapter = AnthropicAdapter(manifest, client=client)

    with pytest.raises(LLMProviderError) as exc_info:
        await adapter.generate(messages=[Message(role="user", content="hello")])

    assert "anthropic-provider-error" in str(exc_info.value)
    assert exc_info.value.provider == "anthropic"
    assert isinstance(exc_info.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_openai_adapter_wraps_provider_errors() -> None:
    manifest = make_manifest(provider="openai", model="openai-provider-error")
    client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("openai boom")))
    )
    adapter = OpenAIAdapter(manifest, client=client)

    with pytest.raises(LLMProviderError) as exc_info:
        await adapter.generate(messages=[Message(role="user", content="hello")])

    assert "openai-provider-error" in str(exc_info.value)
    assert exc_info.value.provider == "openai"
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def assert_close(actual: float, expected: float) -> None:
    assert abs(actual - expected) < 1e-12


class RejectingPolicy:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def check_cost(self, run_id: str, proposed_cost: Decimal | float | int | str) -> bool:
        self.calls.append({"run_id": run_id, "proposed_cost": proposed_cost})
        raise CostCapExceeded(
            scope="run",
            cap_usd=Decimal("5.00"),
            current_total_usd=Decimal("4.99"),
            proposed_cost_usd=Decimal("0.02"),
            projected_total_usd=Decimal("5.01"),
        )


def make_manifest(
    *,
    provider: str = "openai",
    model: str = "test-model",
    tool_use: bool = True,
    parallel_tool_use: bool = False,
    long_context: int = 0,
    code_execution: bool = False,
    structured_outputs: bool = False,
    cost_per_mtok_in: float = 1.0,
    cost_per_mtok_out: float = 1.0,
) -> CapabilityManifest:
    return CapabilityManifest.model_validate(
        {
            "provider": provider,
            "model": model,
            "offers": {
                "tool_use": tool_use,
                "parallel_tool_use": parallel_tool_use,
                "long_context": long_context,
                "code_execution": code_execution,
                "structured_outputs": structured_outputs,
            },
            "cost_per_mtok_in": cost_per_mtok_in,
            "cost_per_mtok_out": cost_per_mtok_out,
        }
    )
