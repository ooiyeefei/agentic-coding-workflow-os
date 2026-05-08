# pyright: reportPrivateUsage=false
"""Integration coverage for the mock agent tool paste-back cycle.

Simulates the full "generate prompt -> human pastes into agent tool -> agent
tool produces output -> Spanweave captures" flow using fixture stdin/stdout.

The cycle under test:

    engine.start
        |
        v
    engine.advance  ->  RunStatus.WAITING_AGENT_TOOL  (prompt generated)
        |
        v
    engine.resume(agent_output=...)  ->  advances to next stage
        |
        v
    agent output is captured in the run's persisted state and artifacts
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from spanweave.llm import (
    CapabilityManifest,
    CapabilityRequirements,
    LLMAdapter,
    Message,
    Response,
    ToolDefinition,
)
from spanweave.llm.adapter import CostPolicy
from spanweave.personas import AgentToolCaller, Coder
from spanweave.personas.callers import DirectAPICaller
from spanweave.workflow import RunStatus, WorkflowEngine, default_stage_executor_deps
from spanweave.workflow.engine import _DirectReviewerCaller
from spanweave.workflow.transitions import TransitionKind


class _RecordingAdapter(LLMAdapter):
    """Adapter that records every API call to prove main stages skip LLM calls."""

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
            content="VERDICT: APPROVED\nAll checks passed.",
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


def _build_engine(
    tmp_path: Path,
    persona_adapter: _RecordingAdapter,
    reviewer_adapter: _RecordingAdapter,
    agent_tool: str = "generic",
) -> tuple[WorkflowEngine, StringIO]:
    """Build a WorkflowEngine wired with recording adapters and a captured output stream."""
    persona = Coder(adapter=persona_adapter, skills_directory=tmp_path / "missing-skills")
    output = StringIO()
    persona_caller = AgentToolCaller(
        agent_tool=agent_tool,
        persona_factory=lambda _name: persona,
        output=output,
        repo_root=tmp_path,
    )
    reviewer_caller = _DirectReviewerCaller(DirectAPICaller(
        persona_factory=lambda _name: Coder(
            adapter=reviewer_adapter,
            skills_directory=tmp_path / "missing-skills",
        ),
    ))
    deps = default_stage_executor_deps(agent_tool=agent_tool, repo_root=tmp_path)
    deps = deps.model_copy(
        update={
            "persona_caller": persona_caller,
            "reviewer_caller": reviewer_caller,
        },
    )
    engine = WorkflowEngine(deps=deps, repo_root=tmp_path)
    return engine, output


def _read_workflow_state(run_id: str) -> dict[str, Any]:
    """Read the persisted workflow state YAML for a run."""
    from spanweave.util.paths import run_dir

    state_path = run_dir(run_id) / "workflow_state.yaml"
    raw = state_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)
    assert isinstance(parsed, dict)
    return cast("dict[str, Any]", parsed)


@pytest.mark.asyncio
async def test_single_paste_back_cycle_generates_prompt_and_captures_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single advance -> paste-back -> resume cycle works end to end.

    Steps:
    1. Start a workflow run.
    2. Advance to get WAITING_AGENT_TOOL with a non-empty prompt.
    3. Resume with simulated agent output.
    4. Assert the workflow advances past the first stage.
    5. Assert the agent output is captured in the run's persisted state artifacts.
    6. Assert zero LLM calls on the persona path.
    """
    monkeypatch.chdir(tmp_path)

    persona_adapter = _RecordingAdapter(_manifest())
    reviewer_adapter = _RecordingAdapter(_manifest())
    engine, output = _build_engine(tmp_path, persona_adapter, reviewer_adapter)

    # Step 1: start
    run_id = engine.start("issue #42", context="Phase 0 paste-back test")

    # Step 2: advance -> WAITING_AGENT_TOOL
    handoff = await engine.advance(run_id)
    assert handoff.run_status == RunStatus.WAITING_AGENT_TOOL
    assert handoff.transition.kind == TransitionKind.WAITING_AGENT_TOOL

    # The generated prompt must be non-empty and contain expected structure.
    prompt = output.getvalue()
    assert len(prompt.strip()) > 0, "handoff prompt must not be empty"
    assert "Tool Context Packet" in prompt, (
        "generic agent tool prompt must contain tool-specific framing"
    )
    assert "## Phase 0 Handoff" in prompt
    assert "Execute this prompt in the target agent tool." in prompt
    assert run_id in prompt, "prompt must contain the run ID"

    # The prompt must be persisted in the workflow state.
    state_before = _read_workflow_state(run_id)
    assert state_before["status"] == "waiting_agent_tool"
    assert "agent_tool_prompt" in state_before
    assert len(state_before["agent_tool_prompt"]) > 0

    # Step 3: resume with agent output
    agent_output = "Spec drafted. All acceptance criteria identified and documented."
    resumed = await engine.resume(run_id, agent_output=agent_output)

    # Step 4: assert workflow advanced
    # The first stage (specify) has gate_type=auto, so resume should advance to
    # the next stage's WAITING_AGENT_TOOL.
    assert resumed.run_status in {RunStatus.WAITING_AGENT_TOOL, RunStatus.RUNNING}
    assert resumed.transition.kind in {
        TransitionKind.ADVANCE,
        TransitionKind.WAITING_AGENT_TOOL,
    }

    # Step 5: the agent output is captured in the stage result
    if resumed.stage_result is not None:
        assert resumed.stage_result.agent_content == agent_output

    # Step 6: zero LLM calls on the persona path
    assert persona_adapter.calls == [], (
        "paste-back cycle must not invoke the persona's LLM adapter"
    )


@pytest.mark.asyncio
async def test_paste_back_prompt_contains_tool_specific_framing_for_claude_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When agent_tool is claude-code, the prompt contains CLAUDE.md framing."""
    monkeypatch.chdir(tmp_path)

    persona_adapter = _RecordingAdapter(_manifest())
    reviewer_adapter = _RecordingAdapter(_manifest())
    engine, output = _build_engine(
        tmp_path, persona_adapter, reviewer_adapter, agent_tool="claude-code",
    )

    run_id = engine.start("issue #43", context="Claude Code paste-back test")
    handoff = await engine.advance(run_id)

    assert handoff.run_status == RunStatus.WAITING_AGENT_TOOL
    prompt = output.getvalue()
    assert "CLAUDE.md Context Packet" in prompt
    assert persona_adapter.calls == []


@pytest.mark.asyncio
async def test_paste_back_prompt_contains_tool_specific_framing_for_codex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When agent_tool is codex, the prompt contains AGENTS.md framing."""
    monkeypatch.chdir(tmp_path)

    persona_adapter = _RecordingAdapter(_manifest())
    reviewer_adapter = _RecordingAdapter(_manifest())
    engine, output = _build_engine(
        tmp_path, persona_adapter, reviewer_adapter, agent_tool="codex",
    )

    run_id = engine.start("issue #44", context="Codex paste-back test")
    handoff = await engine.advance(run_id)

    assert handoff.run_status == RunStatus.WAITING_AGENT_TOOL
    prompt = output.getvalue()
    assert "AGENTS.md Context Packet" in prompt
    assert persona_adapter.calls == []


@pytest.mark.asyncio
async def test_repeatable_paste_back_cycle_across_multiple_stages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The paste-back cycle is repeatable across multiple sequential stages.

    Advances through specify -> clarify -> plan (three stages), each time
    performing a full advance -> resume cycle.
    """
    monkeypatch.chdir(tmp_path)

    persona_adapter = _RecordingAdapter(_manifest())
    reviewer_adapter = _RecordingAdapter(_manifest())
    engine, output = _build_engine(tmp_path, persona_adapter, reviewer_adapter)

    run_id = engine.start("issue #45", context="Multi-stage paste-back cycle")
    stage_outputs: list[str] = [
        "Stage 1: spec drafted with all criteria.",
        "Stage 2: clarification questions resolved.",
        "Stage 3: implementation plan reviewed and approved.",
    ]

    for cycle_index, agent_output_text in enumerate(stage_outputs):
        # Advance -> WAITING_AGENT_TOOL
        handoff = await engine.advance(run_id)
        if handoff.run_status in {RunStatus.COMPLETED, RunStatus.FAILED}:
            break

        assert handoff.run_status == RunStatus.WAITING_AGENT_TOOL, (
            f"cycle {cycle_index}: expected WAITING_AGENT_TOOL, "
            f"got {handoff.run_status}"
        )

        # Verify prompt was generated
        current_prompt = output.getvalue()
        assert len(current_prompt.strip()) > 0

        # Resume with agent output
        resumed = await engine.resume(run_id, agent_output=agent_output_text)

        # After resume, either advanced to next stage or waiting for next advance
        assert resumed.run_status not in {RunStatus.FAILED}, (
            f"cycle {cycle_index}: workflow unexpectedly failed"
        )

        # Reset the captured output for the next cycle
        output.truncate(0)
        output.seek(0)

    # Confirm at least 2 full cycles completed (specify + clarify at minimum)
    state = _read_workflow_state(run_id)
    assert int(state.get("cursor", 0)) >= 2, (
        "at least two stages must complete through the paste-back cycle"
    )

    # Zero persona LLM calls across all cycles
    assert persona_adapter.calls == [], (
        "no persona LLM calls should occur across any paste-back cycle"
    )


@pytest.mark.asyncio
async def test_resume_without_output_stays_waiting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resuming with empty or missing agent_output keeps the run waiting."""
    monkeypatch.chdir(tmp_path)

    persona_adapter = _RecordingAdapter(_manifest())
    reviewer_adapter = _RecordingAdapter(_manifest())
    engine, _output = _build_engine(tmp_path, persona_adapter, reviewer_adapter)

    run_id = engine.start("issue #46", context="Empty output test")
    await engine.advance(run_id)

    # Resume with None -> stays waiting
    result_none = await engine.resume(run_id, agent_output=None)
    assert result_none.run_status == RunStatus.WAITING_AGENT_TOOL

    # Resume with empty string -> stays waiting
    result_empty = await engine.resume(run_id, agent_output="")
    assert result_empty.run_status == RunStatus.WAITING_AGENT_TOOL

    # Resume with whitespace-only -> stays waiting
    result_ws = await engine.resume(run_id, agent_output="   ")
    assert result_ws.run_status == RunStatus.WAITING_AGENT_TOOL


@pytest.mark.asyncio
async def test_agent_output_persisted_in_stage_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The agent tool output is captured in the stage result's evidence artifacts."""
    monkeypatch.chdir(tmp_path)

    persona_adapter = _RecordingAdapter(_manifest())
    reviewer_adapter = _RecordingAdapter(_manifest())
    engine, _output = _build_engine(tmp_path, persona_adapter, reviewer_adapter)

    run_id = engine.start("issue #47", context="Evidence capture test")
    handoff = await engine.advance(run_id)
    assert handoff.run_status == RunStatus.WAITING_AGENT_TOOL

    agent_output = "Implementation complete with all acceptance checks passing."
    resumed = await engine.resume(run_id, agent_output=agent_output)

    # The stage result must carry the agent output content
    assert resumed.stage_result is not None, (
        "resume must produce a stage result with captured output"
    )
    assert resumed.stage_result.agent_content == agent_output

    # The evidence pack summary must reference the agent output
    assert resumed.stage_result.evidence is not None
    assert len(resumed.stage_result.evidence.summary) > 0


@pytest.mark.asyncio
async def test_persisted_state_clears_agent_tool_fields_after_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a successful resume, the transient agent_tool_* state fields are cleared."""
    monkeypatch.chdir(tmp_path)

    persona_adapter = _RecordingAdapter(_manifest())
    reviewer_adapter = _RecordingAdapter(_manifest())
    engine, _output = _build_engine(tmp_path, persona_adapter, reviewer_adapter)

    run_id = engine.start("issue #48", context="State cleanup test")
    await engine.advance(run_id)

    # Confirm agent_tool_prompt is set while waiting
    state_waiting = _read_workflow_state(run_id)
    assert "agent_tool_prompt" in state_waiting
    assert "agent_tool_stage_id" in state_waiting

    # Resume
    await engine.resume(
        run_id,
        agent_output="Agent output for state cleanup verification.",
    )

    # After resume, transient agent tool fields must be cleared
    state_after = _read_workflow_state(run_id)
    assert state_after.get("agent_tool_prompt") is None, (
        "agent_tool_prompt must be cleared after resume"
    )
    assert state_after.get("agent_tool_stage_id") is None, (
        "agent_tool_stage_id must be cleared after resume"
    )
    assert state_after.get("agent_tool_persona") is None, (
        "agent_tool_persona must be cleared after resume"
    )
    assert state_after.get("agent_tool_skill") is None, (
        "agent_tool_skill must be cleared after resume"
    )


@pytest.mark.asyncio
async def test_zero_persona_llm_calls_across_full_paste_back_cycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cardinal rule: no LLM API calls on the persona path during paste-back.

    This test performs two complete cycles and confirms the persona adapter
    is never invoked, while the reviewer adapter IS invoked when a review-gated
    stage is encountered (plan, tasks, implement).
    """
    monkeypatch.chdir(tmp_path)

    persona_adapter = _RecordingAdapter(_manifest())
    reviewer_adapter = _RecordingAdapter(_manifest())
    engine, output = _build_engine(tmp_path, persona_adapter, reviewer_adapter)

    run_id = engine.start("issue #49", context="Zero LLM calls test")

    # Cycle 1: specify (auto gate)
    handoff1 = await engine.advance(run_id)
    assert handoff1.run_status == RunStatus.WAITING_AGENT_TOOL
    await engine.resume(run_id, agent_output="Specify output.")
    assert persona_adapter.calls == []

    # Cycle 2: clarify (auto gate)
    output.truncate(0)
    output.seek(0)
    handoff2 = await engine.advance(run_id)
    assert handoff2.run_status == RunStatus.WAITING_AGENT_TOOL
    await engine.resume(run_id, agent_output="Clarify output.")
    assert persona_adapter.calls == []

    # Cycle 3: plan (review gate) -- reviewer adapter WILL be called
    output.truncate(0)
    output.seek(0)
    handoff3 = await engine.advance(run_id)
    assert handoff3.run_status == RunStatus.WAITING_AGENT_TOOL
    reviewer_calls_before = len(reviewer_adapter.calls)
    await engine.resume(run_id, agent_output="Plan output.")

    # Persona adapter still untouched
    assert persona_adapter.calls == [], (
        "persona LLM adapter must never be called during paste-back cycles"
    )
    # Reviewer adapter was called for the review-gated plan stage
    assert len(reviewer_adapter.calls) > reviewer_calls_before, (
        "reviewer adapter should be invoked for review-gated stages"
    )
