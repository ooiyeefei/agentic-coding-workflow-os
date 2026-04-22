from __future__ import annotations

import json
from abc import ABC
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any, cast

import frontmatter
from pydantic import BaseModel, ConfigDict, Field

from atelier.defaults import (
    DEFAULT_MODELS_DIR,
    DEFAULT_PERSONAS_DIR,
)
from atelier.defaults import (
    DEFAULT_SKILLS_DIR as BUNDLED_SKILLS_DIR,
)
from atelier.llm import (
    AnthropicAdapter,
    CapabilityManifest,
    CapabilityRequirements,
    Cost,
    LLMAdapter,
    Message,
    OpenAIAdapter,
    Response,
    ToolCall,
    Usage,
    load_capability_manifests,
    route_persona_to_model,
)
from atelier.llm.adapter import CostPolicy, JsonValue
from atelier.policy import PolicyEngine

DEFAULT_MODEL_DIR = DEFAULT_MODELS_DIR
DEFAULT_PERSONA_DIR = DEFAULT_PERSONAS_DIR
DEFAULT_SKILLS_DIR = BUNDLED_SKILLS_DIR

AdapterFactory = Callable[[CapabilityManifest], LLMAdapter]


def _tool_call_list() -> list[ToolCall]:
    return []


class PersonaDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    llm_adapter_name: str = "first-compatible"
    required_capabilities: CapabilityRequirements = Field(
        default_factory=CapabilityRequirements
    )
    system_prompt: str


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona: str
    adapter_name: str
    provider: str
    model: str
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=_tool_call_list)
    stop_reason: str | None = None
    usage: Usage = Field(default_factory=Usage)
    cost: Cost = Field(default_factory=Cost)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


def load_persona_definition(path: str | Path) -> PersonaDefinition:
    prompt_path = Path(path)
    post = frontmatter.load(str(prompt_path))
    prompt_body = post.content.strip()
    if not prompt_body:
        raise ValueError(f"Persona prompt {prompt_path} must contain a markdown body")

    payload = dict(post.metadata)
    payload["system_prompt"] = prompt_body
    return PersonaDefinition.model_validate(payload)


def build_default_adapter(manifest: CapabilityManifest) -> LLMAdapter:
    if manifest.provider == "anthropic":
        return AnthropicAdapter(manifest)
    if manifest.provider == "openai":
        return OpenAIAdapter(manifest)
    raise ValueError(f"Unsupported provider for persona adapter binding: {manifest.provider}")


class Persona(ABC):
    prompt_filename: str

    def __init__(
        self,
        *,
        adapter: LLMAdapter | None = None,
        manifests: Iterable[CapabilityManifest] | None = None,
        prompt_path: str | Path | None = None,
        model_directory: str | Path = DEFAULT_MODEL_DIR,
        adapter_factory: AdapterFactory = build_default_adapter,
        policy_engine: CostPolicy | None = None,
        run_id: str | None = None,
    ) -> None:
        definition = load_persona_definition(prompt_path or self.default_prompt_path())
        self.definition = definition
        self.name = definition.name
        self.required_capabilities = definition.required_capabilities

        if adapter is not None:
            selection_pool = [adapter.manifest]
        elif manifests is not None:
            selection_pool = list(manifests)
        else:
            selection_pool = load_capability_manifests(model_directory)
        self.manifest = route_persona_to_model(self.required_capabilities, selection_pool)
        self.llm_adapter_name = self.manifest.model
        self._adapter = adapter
        self._adapter_factory = adapter_factory
        self.policy_engine = policy_engine or PolicyEngine()
        self.run_id = run_id
        self.system_prompt = self.render_system_prompt()

    @classmethod
    def default_prompt_path(cls) -> Path:
        return DEFAULT_PERSONA_DIR / cls.prompt_filename

    def render_system_prompt(self) -> str:
        return self.definition.system_prompt

    def build_user_message(self, context_packet: Any) -> str:
        rendered_packet = self.render_context_packet(context_packet)
        return f"Context packet:\n{rendered_packet}"

    def response_metadata(self, context_packet: Any) -> dict[str, JsonValue]:
        return {}

    async def respond(self, context_packet: Any) -> AgentResponse:
        resolved_run_id = self._resolve_run_id(context_packet)
        policy = self.policy_engine if resolved_run_id is not None else None
        response = await self.adapter.generate(
            messages=[
                Message(role="system", content=self.system_prompt),
                Message(role="user", content=self.build_user_message(context_packet)),
            ],
            required_capabilities=self.required_capabilities,
            run_id=resolved_run_id,
            policy=policy,
        )
        return self._build_agent_response(response, metadata=self.response_metadata(context_packet))

    @property
    def adapter(self) -> LLMAdapter:
        if self._adapter is None:
            self._adapter = self._adapter_factory(self.manifest)
        return self._adapter

    def render_context_packet(self, context_packet: Any) -> str:
        if isinstance(context_packet, str):
            return context_packet
        if isinstance(context_packet, BaseModel):
            return context_packet.model_dump_json(indent=2)
        try:
            return json.dumps(context_packet, indent=2, sort_keys=True)
        except TypeError:
            return str(context_packet)

    def _resolve_run_id(self, context_packet: Any) -> str | None:
        if self.run_id is not None and self.run_id.strip():
            return self.run_id
        if isinstance(context_packet, BaseModel):
            payload = cast("dict[str, object]", context_packet.model_dump(mode="python"))
            candidate = payload.get("run_id")
        elif isinstance(context_packet, Mapping):
            payload = cast("Mapping[str, object]", context_packet)
            candidate = payload.get("run_id")
        else:
            candidate = getattr(context_packet, "run_id", None)
        if isinstance(candidate, str) and candidate.strip():
            return candidate
        return None

    def _build_agent_response(
        self,
        response: Response,
        *,
        metadata: dict[str, JsonValue],
    ) -> AgentResponse:
        return AgentResponse(
            persona=self.name,
            adapter_name=self.llm_adapter_name,
            provider=response.provider,
            model=response.model,
            content=response.content,
            tool_calls=response.tool_calls,
            stop_reason=response.stop_reason,
            usage=response.usage,
            cost=response.cost,
            metadata=metadata,
        )
