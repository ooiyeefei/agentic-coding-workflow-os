from __future__ import annotations

import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

from atelier.adapters import (
    ClaudeCodeAdapter,
    CodexAdapter,
    GenericAdapter,
    ToolAdapter,
    detect_active_adapter,
)
from atelier.llm import Message
from atelier.memory import MemoryRecord
from atelier.personas.base import AgentResponse, Persona

if TYPE_CHECKING:
    from atelier.workflow.stages import PersonaCallResult

PersonaFactory = Callable[[str], Persona]


def default_persona_factory(persona_name: str) -> Persona:
    normalized = persona_name.strip().casefold().replace("_", "-")
    if normalized == "coder":
        from atelier.personas.coder import Coder

        return Coder()
    if normalized == "reviewer":
        from atelier.personas.reviewer import Reviewer

        return Reviewer()
    if normalized == "uat":
        from atelier.personas.uat import UAT

        return UAT()
    raise ValueError(
        f"unknown persona {persona_name!r}; expected one of: coder, reviewer, uat"
    )


class AgentToolCaller:
    """PersonaCaller implementation that returns prompts for external agent tools."""

    produces_agent_tool_handoff = True

    def __init__(
        self,
        *,
        agent_tool: str | ToolAdapter | None = None,
        repo_root: str | Path | None = None,
        persona_factory: PersonaFactory = default_persona_factory,
        memory_records: Sequence[MemoryRecord] = (),
        output: IO[str] | None = None,
    ) -> None:
        self.repo_root = Path(repo_root or Path.cwd())
        self.agent_tool = self._resolve_tool(agent_tool)
        self.persona_factory = persona_factory
        self.memory_records = list(memory_records)
        self.output = output

    async def call(
        self,
        persona_name: str,
        context: str,
        *,
        skill: str,
        run_id: str,
    ) -> str:
        persona = self.persona_factory(persona_name)
        prompt = self._build_prompt(
            persona,
            context,
            persona_name=persona_name,
            skill=skill,
            run_id=run_id,
        )
        if not prompt.strip():
            raise ValueError("agent tool prompt must not be empty")

        print(prompt, end="", file=self.output or sys.stdout)
        return prompt

    def _build_prompt(
        self,
        persona: Persona,
        context: Any,
        *,
        persona_name: str,
        skill: str,
        run_id: str,
    ) -> str:
        tool_context = self.agent_tool.format_context_packet(
            run_id,
            persona_name,
            self.memory_records,
        ).strip()
        system_prompt = persona.system_prompt.strip()
        user_message = persona.build_user_message(context).strip()
        skill_name = skill.strip() or "unspecified"
        run_label = run_id.strip() or "unassigned"

        parts = [
            tool_context,
            "",
            "## Persona Stage Prompt",
            f"- Persona: {persona.name}",
            f"- Skill: {skill_name}",
            f"- Run ID: {run_label}",
            f"- Target agent tool: {self.agent_tool.tool_name}",
            "",
            "## System Prompt",
            system_prompt,
            "",
            "## Stage Request",
            user_message,
            "",
            "## Phase 0 Handoff",
            "- Execute this prompt in the target agent tool.",
            "- Return the agent tool output to Atelier when prompted.",
        ]
        return "\n".join(parts).strip() + "\n"

    def _resolve_tool(self, agent_tool: str | ToolAdapter | None) -> ToolAdapter:
        if isinstance(agent_tool, ToolAdapter):
            return agent_tool
        if agent_tool is None:
            return detect_active_adapter(self.repo_root) or GenericAdapter(
                repo_root=self.repo_root
            )

        normalized = agent_tool.strip().casefold().replace("_", "-")
        if normalized == "codex":
            return CodexAdapter(repo_root=self.repo_root)
        if normalized in {"claude", "claude-code"}:
            return ClaudeCodeAdapter(repo_root=self.repo_root)
        if normalized == "generic":
            return GenericAdapter(repo_root=self.repo_root)
        raise ValueError(
            f"unknown agent tool {agent_tool!r}; expected one of: codex, claude-code, generic"
        )


class DirectAPICaller:
    """PersonaCaller implementation that preserves direct LLM persona execution."""

    def __init__(
        self,
        *,
        persona_factory: PersonaFactory = default_persona_factory,
    ) -> None:
        self.persona_factory = persona_factory

    async def call(
        self,
        persona_name: str,
        context: str,
        *,
        skill: str,
        run_id: str,
    ) -> PersonaCallResult:
        from atelier.workflow.stages import PersonaCallResult

        response = await self.call_response(
            persona_name,
            context,
            skill=skill,
            run_id=run_id,
        )
        return PersonaCallResult(
            content=response.content,
            metadata=self._metadata_from_response(response),
        )

    async def call_response(
        self,
        persona_name: str,
        context: Any,
        *,
        skill: str,
        run_id: str,
    ) -> AgentResponse:
        persona = self.persona_factory(persona_name)
        with _temporary_run_id(persona, run_id):
            if persona.__class__.respond is Persona.respond:
                return await self._generate_direct_response(persona, context)
            return await persona.respond(context)

    async def _generate_direct_response(
        self,
        persona: Persona,
        context: Any,
    ) -> AgentResponse:
        resolved_run_id = persona.resolve_run_id(context)
        policy = persona.policy_engine if resolved_run_id is not None else None
        response = await persona.adapter.generate(
            messages=[
                Message(role="system", content=persona.system_prompt),
                Message(role="user", content=persona.build_user_message(context)),
            ],
            required_capabilities=persona.required_capabilities,
            run_id=resolved_run_id,
            policy=policy,
        )
        return persona.build_agent_response(
            response,
            metadata=persona.response_metadata(context),
        )

    def _metadata_from_response(self, response: AgentResponse) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "persona": response.persona,
            "adapter_name": response.adapter_name,
            "provider": response.provider,
            "model": response.model,
            "stop_reason": response.stop_reason,
            "usage": response.usage.model_dump(mode="json"),
            "cost": response.cost.model_dump(mode="json"),
            "tool_calls": [
                tool_call.model_dump(mode="json") for tool_call in response.tool_calls
            ],
        }
        metadata.update(response.metadata)
        return metadata


@contextmanager
def _temporary_run_id(persona: Persona, run_id: str) -> Iterator[None]:
    if not run_id.strip():
        yield
        return

    original = persona.run_id
    persona.run_id = run_id
    try:
        yield
    finally:
        persona.run_id = original


__all__ = [
    "AgentToolCaller",
    "DirectAPICaller",
    "PersonaFactory",
    "default_persona_factory",
]
