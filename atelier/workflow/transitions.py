from __future__ import annotations

from enum import StrEnum
from typing import NamedTuple

from atelier.evidence.schema import Verdict
from atelier.workflow.schema import (
    StageDefinition,
    WorkflowDefinition,
    parse_on_reject,
)


class TransitionKind(StrEnum):
    ADVANCE = "advance"
    RETRY = "retry"
    REVERT = "revert"
    HALT = "halt"
    DONE = "done"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_AGENT_TOOL = "waiting_agent_tool"
    COUNCIL = "council"


class Transition(NamedTuple):
    kind: TransitionKind
    next_stage_id: str | None = None
    reason: str = ""


def resolve_transition(
    workflow: WorkflowDefinition,
    stage: StageDefinition,
    verdict: Verdict,
    retry_count: int,
) -> Transition:
    if verdict == Verdict.APPROVED:
        return _advance_or_done(workflow, stage)

    if verdict == Verdict.NEEDS_REVISION:
        return _handle_needs_revision(workflow, stage, retry_count)

    return _handle_rejected(workflow, stage)


def _advance_or_done(workflow: WorkflowDefinition, stage: StageDefinition) -> Transition:
    idx = workflow.stage_index(stage.id)
    if idx + 1 >= len(workflow.stages):
        return Transition(TransitionKind.DONE, reason="all stages complete")
    next_stage = workflow.stages[idx + 1]
    return Transition(TransitionKind.ADVANCE, next_stage_id=next_stage.id, reason="approved")


def _handle_needs_revision(
    workflow: WorkflowDefinition,
    stage: StageDefinition,
    retry_count: int,
) -> Transition:
    if retry_count < stage.retry_max:
        return Transition(
            TransitionKind.RETRY,
            next_stage_id=stage.id,
            reason=f"retry {retry_count + 1}/{stage.retry_max}",
        )

    action, target = parse_on_reject(stage.on_reject)
    if action == "revise":
        return Transition(TransitionKind.COUNCIL, reason="retries exhausted, escalating to council")
    if action == "council":
        return Transition(TransitionKind.COUNCIL, reason="escalating to council")
    if action == "revert_to":
        assert target is not None
        workflow.stage_index(target)
        return Transition(
            TransitionKind.REVERT,
            next_stage_id=target,
            reason=f"reverting to {target}",
        )
    return Transition(TransitionKind.HALT, reason="retries exhausted, halting")


def _handle_rejected(workflow: WorkflowDefinition, stage: StageDefinition) -> Transition:
    action, target = parse_on_reject(stage.on_reject)
    if action == "revert_to":
        assert target is not None
        workflow.stage_index(target)
        return Transition(
            TransitionKind.REVERT,
            next_stage_id=target,
            reason=f"rejected, reverting to {target}",
        )
    if action == "council":
        return Transition(TransitionKind.COUNCIL, reason="rejected, escalating to council")
    return Transition(TransitionKind.HALT, reason="rejected")


__all__ = [
    "Transition",
    "TransitionKind",
    "resolve_transition",
]
