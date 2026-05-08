from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from spanweave.adapters import ClaudeCodeAdapter, CodexAdapter
from spanweave.llm import (
    CapabilityManifest,
    CapabilityRequirements,
    LLMAdapter,
    Message,
    Response,
    ToolDefinition,
)
from spanweave.llm.adapter import CostPolicy
from spanweave.personas import AgentToolCaller, Coder, DirectAPICaller
from spanweave.util.paths import run_dir
from spanweave.workflow import WorkflowEngine, default_stage_executor_deps
from spanweave.workflow.engine import RunStatus, _read_state
from spanweave.workflow.stages import PersonaCallResult
from spanweave.workflow.transitions import TransitionKind


class FakeAdapter(LLMAdapter):
    def __init__(self, manifest: CapabilityManifest, response: Response | None = None) -> None:
        super().__init__(manifest)
        self.calls: list[dict[str, Any]] = []
        self._response = response or Response(
            provider=manifest.provider,
            model=manifest.model,
            content="direct response",
        )

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        required_capabilities: CapabilityRequirements | None = None,
        *,
        run_id: str | None = None,
        policy: CostPolicy | None = None,
    ) -> Response:
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "required_capabilities": required_capabilities,
                "run_id": run_id,
                "policy": policy,
            }
        )
        return self._response


@pytest.mark.asyncio
async def test_agent_tool_caller_generates_codex_prompt_without_api_call(
    tmp_path: Path,
    fixed_run_id: str,
) -> None:
    coder, adapter = _coder(tmp_path)
    output = StringIO()
    caller = AgentToolCaller(
        agent_tool=CodexAdapter(repo_root=tmp_path),
        persona_factory=lambda _name: coder,
        output=output,
    )

    prompt = await caller.call(
        "coder",
        "Implement issue #53.",
        skill="speckit.specify",
        run_id=fixed_run_id,
    )

    assert prompt == output.getvalue()
    assert "# AGENTS.md Context Packet" in prompt
    assert "Persona Stage Prompt" in prompt
    assert "Skill: speckit.specify" in prompt
    assert f"Run ID: {fixed_run_id}" in prompt
    assert "Target agent tool: codex" in prompt
    assert "Context packet:\nImplement issue #53." in prompt
    assert "Recommended next command: /speckit.specify" in prompt
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_agent_tool_caller_generates_claude_code_prompt(
    tmp_path: Path,
    fixed_run_id: str,
) -> None:
    coder, _adapter = _coder(tmp_path)
    caller = AgentToolCaller(
        agent_tool=ClaudeCodeAdapter(repo_root=tmp_path),
        persona_factory=lambda _name: coder,
        output=StringIO(),
    )

    prompt = await caller.call(
        "coder",
        "# Tasks: Persona Rework",
        skill="speckit.implement",
        run_id=fixed_run_id,
    )

    assert "# CLAUDE.md Context Packet" in prompt
    assert "Review relevant files in `.claude/rules/`" in prompt
    assert "Target agent tool: claude-code" in prompt
    assert "Recommended next command: /speckit.implement" in prompt


@pytest.mark.asyncio
async def test_direct_api_caller_wraps_existing_persona_response(
    tmp_path: Path,
    fixed_run_id: str,
) -> None:
    coder, adapter = _coder(tmp_path)
    caller = DirectAPICaller(persona_factory=lambda _name: coder)

    result = await caller.call(
        "coder",
        "# Tasks: Persona Rework",
        skill="speckit.implement",
        run_id=fixed_run_id,
    )

    assert isinstance(result, PersonaCallResult)
    assert result.content == "direct response"
    assert result.metadata["recommended_command"] == "/speckit.implement"
    assert result.metadata["provider"] == "openai"
    assert adapter.calls[0]["run_id"] == fixed_run_id
    assert adapter.calls[0]["policy"] is not None


@pytest.mark.asyncio
async def test_persona_respond_via_tool_returns_prompt(
    tmp_path: Path,
    fixed_run_id: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    coder, adapter = _coder(tmp_path)

    prompt = await coder.respond_via_tool(
        "codex",
        "Create the feature spec.",
        skill="speckit.specify",
        run_id=fixed_run_id,
    )

    captured = capsys.readouterr()
    assert captured.out == prompt
    assert "# AGENTS.md Context Packet" in prompt
    assert "Create the feature spec." in prompt
    assert adapter.calls == []


def test_workflow_default_deps_use_agent_tool_caller(tmp_path: Path) -> None:
    deps = default_stage_executor_deps(agent_tool="generic", repo_root=tmp_path)
    engine = WorkflowEngine(agent_tool="generic", repo_root=tmp_path)

    assert isinstance(deps.persona_caller, AgentToolCaller)
    assert isinstance(engine._deps.persona_caller, AgentToolCaller)


@pytest.mark.asyncio
async def test_workflow_waits_for_agent_tool_output_before_completing_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    engine = WorkflowEngine(agent_tool="generic", repo_root=tmp_path)
    run_id = engine.start("issue #53", context="Persona rework")

    handoff = await engine.advance(run_id)

    assert handoff.run_status == RunStatus.WAITING_AGENT_TOOL
    assert handoff.transition.kind == TransitionKind.WAITING_AGENT_TOOL
    assert handoff.stage_result is None
    waiting_state = _read_state(run_id)
    assert waiting_state["cursor"] == 0
    assert waiting_state["waiting_reason"] == "agent_tool"
    assert "Persona Stage Prompt" in waiting_state["agent_tool_prompt"]
    handoff_stage_id = waiting_state["agent_tool_stage_id"]
    assert not (run_dir(run_id) / "stages" / handoff_stage_id / ".complete").exists()

    resumed = await engine.resume(run_id, agent_output="Agent tool completed the spec.")

    assert resumed.run_status == RunStatus.RUNNING
    assert resumed.stage_result is not None
    assert resumed.stage_result.agent_content == "Agent tool completed the spec."
    resumed_state = _read_state(run_id)
    assert resumed_state["cursor"] == 1
    assert resumed_state["status"] == RunStatus.RUNNING.value
    assert "agent_tool_prompt" not in resumed_state
    assert (run_dir(run_id) / "stages" / handoff_stage_id / ".complete").is_file()


@pytest.mark.asyncio
async def test_agent_tool_output_respects_approval_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    workflow_dir = tmp_path / "workflows"
    workflow_dir.mkdir()
    (workflow_dir / "approval-handoff.yaml").write_text(
        (
            "name: approval-handoff\n"
            "version: '1.0.0'\n"
            "stages:\n"
            "  - id: approval-stage\n"
            "    persona: coder\n"
            "    skill: speckit.review\n"
            "    gate_type: approval\n"
        ),
        encoding="utf-8",
    )
    engine = WorkflowEngine(
        agent_tool="generic",
        repo_root=tmp_path,
        user_workflows_dir=workflow_dir,
    )
    run_id = engine.start("issue #53", workflow_name="approval-handoff")

    handoff = await engine.advance(run_id)
    assert handoff.run_status == RunStatus.WAITING_AGENT_TOOL
    handoff_stage_id = _read_state(run_id)["agent_tool_stage_id"]

    blocked = await engine.resume(run_id, agent_output="Agent tool completed approval work.")

    assert blocked.run_status == RunStatus.WAITING_APPROVAL
    assert blocked.transition.kind == TransitionKind.WAITING_APPROVAL
    assert blocked.stage_result is not None
    blocked_state = _read_state(run_id)
    assert blocked_state["cursor"] == 0
    assert blocked_state["status"] == RunStatus.WAITING_APPROVAL.value
    assert blocked_state["waiting_reason"] == "gate"
    assert "agent_tool_prompt" not in blocked_state
    assert not (run_dir(run_id) / "stages" / handoff_stage_id / ".complete").exists()

    approved = await engine.resume(run_id, approved=True)
    assert approved.run_status == RunStatus.COMPLETED
    assert (run_dir(run_id) / "stages" / handoff_stage_id / ".complete").is_file()


def _coder(tmp_path: Path) -> tuple[Coder, FakeAdapter]:
    adapter = FakeAdapter(make_manifest(model="coder-model", long_context=200000))
    return (
        Coder(
            adapter=adapter,
            skills_directory=tmp_path / "missing-skills",
        ),
        adapter,
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
