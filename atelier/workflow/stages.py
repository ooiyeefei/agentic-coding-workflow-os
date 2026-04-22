from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from atelier.evidence.schema import EvidencePack, Verdict
from atelier.workflow.schema import GateType, StageDefinition


class StageResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stage_id: str
    verdict: Verdict
    evidence: EvidencePack
    agent_content: str = ""
    retry_count: int = Field(default=0, ge=0)
    reviewer_feedback: str = ""


def _metadata_dict() -> dict[str, Any]:
    return {}


@dataclass(frozen=True)
class PersonaCallResult:
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=_metadata_dict)

    def evidence_pack(self) -> EvidencePack | None:
        candidate = self.metadata.get("evidence_pack")
        if isinstance(candidate, EvidencePack):
            return candidate
        if isinstance(candidate, dict):
            return EvidencePack.model_validate(candidate)
        return None


def _coerce_persona_result(value: str | PersonaCallResult) -> PersonaCallResult:
    if isinstance(value, PersonaCallResult):
        return value
    return PersonaCallResult(content=value)


@runtime_checkable
class PersonaCaller(Protocol):
    async def call(
        self, persona_name: str, context: str, *, skill: str, run_id: str
    ) -> str | PersonaCallResult: ...


@runtime_checkable
class ReviewerCaller(Protocol):
    async def review(self, content: str, *, run_id: str) -> tuple[Verdict, str]: ...


@runtime_checkable
class EvidenceWriter(Protocol):
    def write(
        self,
        run_id: str,
        stage_id: str,
        verdict: Verdict,
        persona_result: PersonaCallResult,
    ) -> EvidencePack: ...


class StageExecutorDeps(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    persona_caller: Any
    reviewer_caller: Any
    evidence_writer: Any


async def execute_stage(
    *,
    run_id: str,
    stage_id: str,
    stage_def: StageDefinition,
    deps: StageExecutorDeps,
    context: str,
    retry_count: int = 0,
    prior_feedback: str = "",
) -> StageResult:
    full_context = context
    if prior_feedback:
        full_context = f"{context}\n\n## Prior Review Feedback\n{prior_feedback}"

    persona_result = _coerce_persona_result(await deps.persona_caller.call(
        stage_def.persona, full_context, skill=stage_def.skill, run_id=run_id
    ))
    agent_content = persona_result.content
    persona_evidence = persona_result.evidence_pack()

    if stage_def.gate_type == GateType.REVIEW:
        verdict, reviewer_feedback = await deps.reviewer_caller.review(
            agent_content, run_id=run_id
        )
    elif persona_evidence is not None:
        verdict = persona_evidence.verdict
        reviewer_feedback = ""
    else:
        verdict = Verdict.APPROVED
        reviewer_feedback = ""

    evidence = deps.evidence_writer.write(run_id, stage_id, verdict, persona_result)

    return StageResult(
        stage_id=stage_id,
        verdict=verdict,
        evidence=evidence,
        agent_content=agent_content,
        retry_count=retry_count,
        reviewer_feedback=reviewer_feedback,
    )


__all__ = [
    "EvidenceWriter",
    "PersonaCaller",
    "PersonaCallResult",
    "ReviewerCaller",
    "StageExecutorDeps",
    "StageResult",
    "execute_stage",
]
