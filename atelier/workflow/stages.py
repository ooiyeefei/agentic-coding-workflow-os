from __future__ import annotations

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


@runtime_checkable
class PersonaCaller(Protocol):
    async def call(
        self, persona_name: str, context: str, *, skill: str, run_id: str
    ) -> str: ...


@runtime_checkable
class ReviewerCaller(Protocol):
    async def review(self, content: str, *, run_id: str) -> tuple[Verdict, str]: ...


@runtime_checkable
class EvidenceWriter(Protocol):
    def write(
        self, run_id: str, stage_id: str, verdict: Verdict, content: str
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

    agent_content = await deps.persona_caller.call(
        stage_def.persona, full_context, skill=stage_def.skill, run_id=run_id
    )

    if stage_def.gate_type == GateType.REVIEW:
        verdict, reviewer_feedback = await deps.reviewer_caller.review(
            agent_content, run_id=run_id
        )
    else:
        verdict = Verdict.APPROVED
        reviewer_feedback = ""

    evidence = deps.evidence_writer.write(run_id, stage_id, verdict, agent_content)

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
    "ReviewerCaller",
    "StageExecutorDeps",
    "StageResult",
    "execute_stage",
]
