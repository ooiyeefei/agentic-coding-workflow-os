# pyright: reportPrivateUsage=false
"""Integration coverage for the W29 Persona Rework caller wiring.

The architectural reframe split the single ``Persona.respond()`` path into two
explicit callers:

* ``AgentToolCaller`` — used for MAIN workflow stages. Generates a paste-ready
  prompt for an external agent tool (Claude Code, Codex, etc.) and waits for
  the user (or paste-back daemon) to feed the agent tool's output back.
* ``DirectAPICaller`` — kept for AUXILIARY calls only. Council tiebreaker and
  ADR prose synthesis still call LLM APIs directly because they live entirely
  inside Atelier's process.

These tests verify the workflow engine wires the right caller for each role
and — crucially — that NO LLM API call is made during the main stage path.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from atelier.adapters import ClaudeCodeAdapter, CodexAdapter, GenericAdapter
from atelier.llm import (
    CapabilityManifest,
    CapabilityRequirements,
    LLMAdapter,
    Message,
    Response,
    ToolDefinition,
)
from atelier.llm.adapter import CostPolicy
from atelier.personas import AgentToolCaller, Coder, DirectAPICaller, Reviewer
from atelier.workflow import (
    RunStatus,
    WorkflowEngine,
    default_stage_executor_deps,
    load_workflow,
)
from atelier.workflow.engine import _DirectReviewerCaller, _is_agent_tool_handoff_caller
from atelier.workflow.transitions import TransitionKind

_MAIN_STAGE_IDS: frozenset[str] = frozenset(
    [
        "specify",
        "clarify",
        "plan",
        "tasks",
        "implement",
        "uat",
        "rebase-analyze",
        "cleanup",
    ]
)


class _RecordingAdapter(LLMAdapter):
    """Adapter that records every API call so we can prove main stages skip it."""

    def __init__(self, manifest: CapabilityManifest) -> None:
        super().__init__(manifest)
        self.calls: list[dict[str, Any]] = []

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
        return Response(
            provider=self.manifest.provider,
            model=self.manifest.model,
            content="recorded direct response",
            stop_reason="completed",
        )


def _manifest() -> CapabilityManifest:
    return CapabilityManifest.model_validate(
        {
            "provider": "openai",
            "model": "test-model",
            "offers": {
                "tool_use": True,
                "parallel_tool_use": True,
                "long_context": 200000,
                "code_execution": True,
                "structured_outputs": True,
            },
            "cost_per_mtok_in": 1.0,
            "cost_per_mtok_out": 1.0,
        }
    )


def test_speckit_loop_main_stages_match_documented_set() -> None:
    """Sanity check: speckit-loop.yaml's stages are the expected main stages."""

    workflow = load_workflow("speckit-loop")
    stage_ids = {stage.id for stage in workflow.stages}
    assert stage_ids == _MAIN_STAGE_IDS, (
        f"speckit-loop stages drifted from the documented main stage set: "
        f"got {sorted(stage_ids)}"
    )


def test_default_engine_wires_agent_tool_caller_for_persona_role(
    tmp_path: Path,
) -> None:
    """The default workflow engine routes persona calls through the agent tool layer."""

    deps = default_stage_executor_deps(agent_tool="generic", repo_root=tmp_path)
    engine = WorkflowEngine(agent_tool="generic", repo_root=tmp_path)

    assert isinstance(deps.persona_caller, AgentToolCaller)
    assert isinstance(engine._deps.persona_caller, AgentToolCaller)
    assert _is_agent_tool_handoff_caller(deps.persona_caller) is True
    assert _is_agent_tool_handoff_caller(engine._deps.persona_caller) is True


def test_default_engine_wires_direct_api_caller_for_auxiliary_review(
    tmp_path: Path,
) -> None:
    """Reviewer calls still use the DirectAPICaller path — LLM-driven verdicts."""

    deps = default_stage_executor_deps(agent_tool="generic", repo_root=tmp_path)
    reviewer_caller = deps.reviewer_caller

    assert isinstance(reviewer_caller, _DirectReviewerCaller)
    assert isinstance(reviewer_caller._caller, DirectAPICaller)
    # The auxiliary caller flag must NOT be set — it should NOT short-circuit.
    assert _is_agent_tool_handoff_caller(reviewer_caller) is False
    assert _is_agent_tool_handoff_caller(reviewer_caller._caller) is False


@pytest.mark.parametrize(
    "agent_tool, expected_adapter_cls, expected_packet_marker",
    [
        ("claude-code", ClaudeCodeAdapter, "# CLAUDE.md Context Packet"),
        ("codex", CodexAdapter, "# AGENTS.md Context Packet"),
        ("generic", GenericAdapter, "# Tool Context Packet"),
    ],
)
@pytest.mark.asyncio
async def test_agent_tool_caller_emits_tool_specific_packet_without_llm_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixed_run_id: str,
    agent_tool: str,
    expected_adapter_cls: type,
    expected_packet_marker: str,
) -> None:
    """Each main-stage agent tool produces a tool-specific paste-ready prompt.

    Crucially: the persona's underlying LLM adapter must NOT be invoked.
    """

    monkeypatch.chdir(tmp_path)

    adapter = _RecordingAdapter(_manifest())
    persona = Coder(adapter=adapter, skills_directory=tmp_path / "missing-skills")
    output = StringIO()
    caller = AgentToolCaller(
        agent_tool=agent_tool,
        persona_factory=lambda _name: persona,
        output=output,
        repo_root=tmp_path,
    )

    prompt = await caller.call(
        "coder",
        "Implement the workflow phase 0 hygiene.",
        skill="speckit.implement",
        run_id=fixed_run_id,
    )

    assert isinstance(caller.agent_tool, expected_adapter_cls)
    assert prompt == output.getvalue()
    assert expected_packet_marker in prompt
    assert f"Run ID: {fixed_run_id}" in prompt
    assert "## Phase 0 Handoff" in prompt
    assert "Execute this prompt in the target agent tool." in prompt
    # The cardinal rule: no API call during the agent tool handoff.
    assert adapter.calls == [], (
        "AgentToolCaller must not invoke the underlying LLM adapter — "
        "it only generates the prompt string."
    )


@pytest.mark.asyncio
async def test_direct_api_caller_invokes_underlying_adapter_for_council_path(
    tmp_path: Path,
    fixed_run_id: str,
) -> None:
    """DirectAPICaller drives the LLM adapter; that's its purpose."""

    adapter = _RecordingAdapter(_manifest())
    persona = Reviewer(adapter=adapter)
    caller = DirectAPICaller(persona_factory=lambda _name: persona)

    result = await caller.call(
        "reviewer",
        "Council tiebreaker arbitration request.",
        skill="review",
        run_id=fixed_run_id,
    )

    assert result.content == "recorded direct response"
    assert len(adapter.calls) == 1, (
        "DirectAPICaller must invoke the underlying adapter exactly once "
        "for an auxiliary call."
    )
    assert adapter.calls[0]["run_id"] == fixed_run_id


@pytest.mark.asyncio
async def test_main_stage_advance_records_zero_llm_calls_through_persona_caller(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: starting a real workflow advance generates a prompt, no API calls.

    The engine must transition into ``WAITING_AGENT_TOOL`` rather than completing
    the stage by calling an LLM. This is the cardinal post-reframe behavior.
    """

    monkeypatch.chdir(tmp_path)

    # Spy adapter that fails the test if the engine ever calls it for a main stage.
    spy_adapter = _RecordingAdapter(_manifest())

    # Wire a custom AgentToolCaller that uses our spy adapter as the persona
    # backing — proving even when an adapter is available, the main path
    # doesn't reach for it.
    persona = Coder(adapter=spy_adapter, skills_directory=tmp_path / "missing-skills")
    caller = AgentToolCaller(
        agent_tool="generic",
        persona_factory=lambda _name: persona,
        output=StringIO(),
        repo_root=tmp_path,
    )
    deps = default_stage_executor_deps(agent_tool="generic", repo_root=tmp_path)
    deps = deps.model_copy(update={"persona_caller": caller})
    engine = WorkflowEngine(deps=deps, repo_root=tmp_path)

    run_id = engine.start("issue #24", context="Phase 0 hygiene followup")
    handoff = await engine.advance(run_id)

    assert handoff.run_status == RunStatus.WAITING_AGENT_TOOL, (
        "main stage advance must wait for an external agent tool, not call "
        "the LLM directly"
    )
    assert handoff.transition.kind == TransitionKind.WAITING_AGENT_TOOL
    assert spy_adapter.calls == [], (
        "main stage advance must not invoke the LLM API"
    )


@pytest.mark.asyncio
async def test_resume_with_agent_output_advances_without_llm_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resume after agent tool paste-back must finalize without an LLM API call.

    The reviewer caller IS allowed to invoke the LLM (DirectAPICaller path),
    but the persona side must remain silent.
    """

    monkeypatch.chdir(tmp_path)

    persona_adapter = _RecordingAdapter(_manifest())
    persona = Coder(
        adapter=persona_adapter,
        skills_directory=tmp_path / "missing-skills",
    )
    persona_caller = AgentToolCaller(
        agent_tool="generic",
        persona_factory=lambda _name: persona,
        output=StringIO(),
        repo_root=tmp_path,
    )
    deps = default_stage_executor_deps(agent_tool="generic", repo_root=tmp_path)
    deps = deps.model_copy(update={"persona_caller": persona_caller})
    engine = WorkflowEngine(deps=deps, repo_root=tmp_path)

    run_id = engine.start("issue #24", context="Phase 0 hygiene followup")
    handoff = await engine.advance(run_id)
    assert handoff.run_status == RunStatus.WAITING_AGENT_TOOL

    # Simulate the user pasting the Claude Code output back via the CLI.
    resumed = await engine.resume(
        run_id,
        agent_output="Spec drafted, all acceptance checks identified.",
    )

    # The first stage in speckit-loop is `specify` with gate_type=auto, so the
    # resume should advance straight to the next stage's WAITING_AGENT_TOOL.
    assert resumed.run_status in {RunStatus.WAITING_AGENT_TOOL, RunStatus.RUNNING}
    # Persona-side adapter still untouched.
    assert persona_adapter.calls == [], (
        "agent-tool resume path must not invoke the persona's LLM adapter"
    )
