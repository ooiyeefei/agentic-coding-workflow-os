from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from atelier.llm import (
    CapabilityManifest,
    CapabilityRequirements,
    Cost,
    LLMAdapter,
    Message,
    Response,
    ToolCall,
    ToolDefinition,
    UnsupportedCapabilityError,
    Usage,
)
from atelier.personas import AgentResponse, Coder, Reviewer


class FakeAdapter(LLMAdapter):
    def __init__(self, manifest: CapabilityManifest, response: Response | None = None) -> None:
        super().__init__(manifest)
        self.calls: list[dict[str, Any]] = []
        self._response = response or Response(
            provider=manifest.provider,
            model=manifest.model,
            content="ok",
        )

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        required_capabilities: CapabilityRequirements | None = None,
    ) -> Response:
        self.ensure_supported(required_capabilities)
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "required_capabilities": required_capabilities,
            }
        )
        return self._response


def test_coder_routes_to_first_compatible_shipped_manifest() -> None:
    coder = Coder()

    assert coder.name == "coder"
    assert coder.llm_adapter_name == "claude-haiku-4-5"
    assert coder.required_capabilities.tool_use is True
    assert coder.required_capabilities.long_context == 128000


def test_reviewer_routes_to_reviewer_compatible_shipped_manifest() -> None:
    reviewer = Reviewer()

    assert reviewer.name == "reviewer"
    assert reviewer.llm_adapter_name == "gpt-5"
    assert reviewer.required_capabilities.tool_use is True
    assert reviewer.required_capabilities.code_execution is True
    assert reviewer.required_capabilities.structured_outputs is True


def test_reviewer_raises_when_manifests_do_not_satisfy_capabilities() -> None:
    with pytest.raises(UnsupportedCapabilityError):
        Reviewer(
            manifests=[
                make_manifest(
                    model="model-without-execution",
                    tool_use=True,
                    code_execution=False,
                    structured_outputs=False,
                )
            ]
        )


def test_coder_uses_phase0_fallback_sequence_without_skill_catalog(
    tmp_path: Path,
) -> None:
    coder = Coder(
        adapter=FakeAdapter(
            make_manifest(model="coder-model", tool_use=True, long_context=200000)
        ),
        skills_directory=tmp_path / "missing-skills",
    )

    assert [skill.source for skill in coder.skills] == ["fallback"] * 5
    assert coder.recommend_next_command("No artifacts exist yet.") == "/speckit.specify"
    assert (
        coder.recommend_next_command("# Feature Specification: Persona Library")
        == "/speckit.clarify"
    )
    assert (
        coder.recommend_next_command("# Implementation Plan: Persona Library")
        == "/speckit.tasks"
    )
    assert coder.recommend_next_command("# Tasks: Persona Library") == "/speckit.implement"


def test_coder_loads_catalog_skills_when_available(tmp_path: Path) -> None:
    skills_directory = tmp_path / "skills"
    skills_directory.mkdir()
    (skills_directory / "speckit.plan.md").write_text(
        "---\nname: speckit.plan\ndescription: Produce the plan.\n---\nPlan the feature.\n",
        encoding="utf-8",
    )

    coder = Coder(
        adapter=FakeAdapter(
            make_manifest(model="coder-model", tool_use=True, long_context=200000)
        ),
        skills_directory=skills_directory,
    )

    assert len(coder.skills) == 1
    assert coder.skills[0].source == "catalog"
    assert coder.skills[0].command == "/speckit.plan"


@pytest.mark.asyncio
async def test_coder_respond_returns_structured_agent_response(tmp_path: Path) -> None:
    adapter = FakeAdapter(
        make_manifest(model="coder-model", tool_use=True, long_context=200000),
        response=Response(
            provider="openai",
            model="coder-model",
            content="Next command: /speckit.implement",
            tool_calls=[ToolCall(id="call_1", name="persist", arguments={"ok": True})],
            stop_reason="completed",
            usage=Usage(input_tokens=13, output_tokens=21),
            cost=Cost(input_usd=0.001, output_usd=0.002),
        ),
    )
    coder = Coder(adapter=adapter, skills_directory=tmp_path / "missing")

    result = await coder.respond("# Tasks: Persona Library")

    assert isinstance(result, AgentResponse)
    assert result.persona == "coder"
    assert result.adapter_name == "coder-model"
    assert result.provider == "openai"
    assert result.model == "coder-model"
    assert result.tool_calls == [ToolCall(id="call_1", name="persist", arguments={"ok": True})]
    assert result.metadata["recommended_command"] == "/speckit.implement"
    assert adapter.calls[0]["messages"][0].role == "system"
    assert adapter.calls[0]["messages"][1].role == "user"


@pytest.mark.asyncio
async def test_reviewer_respond_returns_structured_agent_response() -> None:
    adapter = FakeAdapter(
        make_manifest(
            model="reviewer-model",
            tool_use=True,
            code_execution=True,
            structured_outputs=True,
        ),
        response=Response(
            provider="openai",
            model="reviewer-model",
            content="VERDICT: APPROVE",
            usage=Usage(input_tokens=8, output_tokens=5),
        ),
    )
    reviewer = Reviewer(adapter=adapter)

    result = await reviewer.review({"diff": "print('ok')"})

    assert isinstance(result, AgentResponse)
    assert result.persona == "reviewer"
    assert result.adapter_name == "reviewer-model"
    assert result.metadata["devil_advocate_mode"] is False
    assert adapter.calls[0]["required_capabilities"] == reviewer.required_capabilities


def test_reviewer_prompt_contains_execution_mandatory_language() -> None:
    reviewer = Reviewer()

    assert "you MUST execute" in reviewer.system_prompt
    assert "paste actual output" in reviewer.system_prompt
    assert "incomplete without execution evidence" in reviewer.system_prompt


def test_reviewer_devil_advocate_mode_appends_rejection_scaffold() -> None:
    reviewer = Reviewer()
    devil_reviewer = Reviewer(devil_advocate_mode=True)

    assert reviewer.devil_advocate_mode is False
    assert devil_reviewer.devil_advocate_mode is True
    assert "Reasons To Reject" not in reviewer.system_prompt
    assert "Reasons To Reject" in devil_reviewer.system_prompt
    assert devil_reviewer.system_prompt != reviewer.system_prompt


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
