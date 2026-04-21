from __future__ import annotations

import asyncio
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from atelier.evidence.schema import Verdict
from atelier.policy.engine import PolicyEngine
from atelier.rungraph.lock import run_lock
from atelier.rungraph.tree import create_run, create_stage, mark_stage_complete
from atelier.util.fs import atomic_write
from atelier.util.paths import run_dir
from atelier.workflow.loader import load_workflow
from atelier.workflow.schema import GateType, WorkflowDefinition
from atelier.workflow.stages import StageExecutorDeps, StageResult, execute_stage
from atelier.workflow.transitions import (
    Transition,
    TransitionKind,
    resolve_transition,
)

_STATE_FILE = "workflow_state.yaml"

# Process-wide lock registry — shared across all WorkflowEngine instances.
_ASYNC_RUN_LOCKS: dict[str, asyncio.Lock] = {}


def _get_async_lock(run_id: str) -> asyncio.Lock:
    try:
        return _ASYNC_RUN_LOCKS[run_id]
    except KeyError:
        lock = asyncio.Lock()
        return _ASYNC_RUN_LOCKS.setdefault(run_id, lock)


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_COUNCIL = "waiting_council"


class AdvanceResult:
    def __init__(
        self,
        *,
        transition: Transition,
        stage_result: StageResult | None = None,
        run_status: RunStatus,
    ) -> None:
        self.transition = transition
        self.stage_result = stage_result
        self.run_status = run_status

    @property
    def is_done(self) -> bool:
        return self.run_status in (RunStatus.COMPLETED, RunStatus.FAILED)


class WorkflowEngine:
    def __init__(
        self,
        *,
        deps: StageExecutorDeps,
        policy_engine: PolicyEngine | None = None,
        user_workflows_dir: Path | None = None,
        defaults_workflows_dir: Path | None = None,
    ) -> None:
        self._deps = deps
        self._policy = policy_engine if policy_engine is not None else PolicyEngine()
        self._user_workflows_dir = user_workflows_dir
        self._defaults_workflows_dir = defaults_workflows_dir

    def _load(self, name: str) -> WorkflowDefinition:
        return load_workflow(
            name,
            user_dir=self._user_workflows_dir,
            defaults_dir=self._defaults_workflows_dir,
        )

    def start(
        self,
        issue_ref: str,
        workflow_name: str = "speckit-loop",
        context: str = "",
    ) -> str:
        workflow = self._load(workflow_name)
        run_id = create_run(issue_ref)
        first_stage = workflow.stages[0]
        create_stage(run_id, first_stage.id)

        state: dict[str, Any] = {
            "workflow": workflow_name,
            "cursor": 0,
            "status": RunStatus.RUNNING.value,
            "retry_count": 0,
            "context": context,
            "prior_feedback": "",
        }
        _write_state(run_id, state)
        return run_id

    async def advance(self, run_id: str) -> AdvanceResult:
        lock = _get_async_lock(run_id)
        contended = lock.locked()
        async with lock:
            with run_lock(run_id):
                if contended:
                    return _snapshot_result(run_id)
                return await self._advance_impl(run_id)

    async def resume(self, run_id: str, *, approved: bool = False) -> AdvanceResult:
        lock = _get_async_lock(run_id)
        contended = lock.locked()
        async with lock:
            with run_lock(run_id):
                if contended:
                    return _snapshot_result(run_id)
                return await self._resume_impl(run_id, approved=approved)

    # ------------------------------------------------------------------
    # Internal — callers must hold both locks
    # ------------------------------------------------------------------

    async def _advance_impl(self, run_id: str) -> AdvanceResult:
        state = _read_state(run_id)
        status = state["status"]

        if status in (RunStatus.COMPLETED.value, RunStatus.FAILED.value):
            return _terminal_result(status)
        if status in (RunStatus.WAITING_APPROVAL.value, RunStatus.WAITING_COUNCIL.value):
            return _waiting_result(state)

        workflow = self._load(state["workflow"])
        cursor: int = state["cursor"]

        if cursor >= len(workflow.stages):
            state["status"] = RunStatus.COMPLETED.value
            _write_state(run_id, state)
            return AdvanceResult(
                transition=Transition(TransitionKind.DONE, reason="all stages complete"),
                run_status=RunStatus.COMPLETED,
            )

        stage_def = workflow.stages[cursor]

        # Policy pre-execution gate
        if self._needs_policy_approval(stage_def) and not state.get("policy_approved"):
            state["status"] = RunStatus.WAITING_APPROVAL.value
            state["waiting_reason"] = "policy"
            _write_state(run_id, state)
            return AdvanceResult(
                transition=Transition(
                    TransitionKind.WAITING_APPROVAL,
                    reason=f"policy requires approval for stage {stage_def.id!r}",
                ),
                run_status=RunStatus.WAITING_APPROVAL,
            )

        # Execute
        current_stage_id = _current_stage_id(run_id, stage_def)
        retry_count: int = state.get("retry_count", 0)

        result = await execute_stage(
            run_id=run_id,
            stage_id=current_stage_id,
            stage_def=stage_def,
            deps=self._deps,
            context=state.get("context", ""),
            retry_count=retry_count,
            prior_feedback=state.get("prior_feedback", ""),
        )

        # Approval gate post-execution block
        if stage_def.gate_type == GateType.APPROVAL:
            state["status"] = RunStatus.WAITING_APPROVAL.value
            state["waiting_reason"] = "gate"
            _write_state(run_id, state)
            return AdvanceResult(
                transition=Transition(
                    TransitionKind.WAITING_APPROVAL,
                    reason="awaiting gate approval",
                ),
                stage_result=result,
                run_status=RunStatus.WAITING_APPROVAL,
            )

        return self._apply_transition(
            run_id, state, workflow, stage_def, current_stage_id, result, retry_count,
        )

    async def _resume_impl(self, run_id: str, *, approved: bool) -> AdvanceResult:
        state = _read_state(run_id)
        status = state["status"]

        if status in (RunStatus.COMPLETED.value, RunStatus.FAILED.value):
            return _terminal_result(status)

        if status == RunStatus.WAITING_APPROVAL.value:
            if not approved:
                return _waiting_result(state)
            return await self._handle_approval(run_id, state)

        if status == RunStatus.WAITING_COUNCIL.value:
            if not approved:
                return _waiting_result(state)
            state["status"] = RunStatus.RUNNING.value
            state.pop("waiting_reason", None)
            _clear_transient_state(state)
            _write_state(run_id, state)

        return await self._advance_impl(run_id)

    async def _handle_approval(self, run_id: str, state: dict[str, Any]) -> AdvanceResult:
        waiting_reason = state.get("waiting_reason", "")

        if waiting_reason == "policy":
            state["policy_approved"] = True
            state["status"] = RunStatus.RUNNING.value
            state.pop("waiting_reason", None)
            _write_state(run_id, state)
            return await self._advance_impl(run_id)

        # Gate approval — stage already executed, advance cursor
        workflow = self._load(state["workflow"])
        cursor: int = state["cursor"]
        stage_def = workflow.stages[cursor]
        current_stage_id = _current_stage_id(run_id, stage_def)

        mark_stage_complete(run_id, current_stage_id)

        if cursor + 1 >= len(workflow.stages):
            state["cursor"] = cursor + 1
            state["status"] = RunStatus.COMPLETED.value
            state["last_transition"] = TransitionKind.DONE.value
            state["last_transition_reason"] = "all stages complete"
            _clear_transient_state(state)
            _write_state(run_id, state)
            return AdvanceResult(
                transition=Transition(TransitionKind.DONE, reason="all stages complete"),
                run_status=RunStatus.COMPLETED,
            )

        next_stage = workflow.stages[cursor + 1]
        create_stage(run_id, next_stage.id)
        state["cursor"] = cursor + 1
        state["status"] = RunStatus.RUNNING.value
        state["last_transition"] = TransitionKind.ADVANCE.value
        state["last_transition_reason"] = "gate approval accepted"
        _clear_transient_state(state)
        _write_state(run_id, state)
        return AdvanceResult(
            transition=Transition(
                TransitionKind.ADVANCE,
                next_stage_id=next_stage.id,
                reason="gate approval accepted",
            ),
            run_status=RunStatus.RUNNING,
        )

    def _apply_transition(
        self,
        run_id: str,
        state: dict[str, Any],
        workflow: WorkflowDefinition,
        stage_def: Any,
        current_stage_id: str,
        result: StageResult,
        retry_count: int,
    ) -> AdvanceResult:
        transition = resolve_transition(workflow, stage_def, result.verdict, retry_count)

        if transition.kind in (TransitionKind.ADVANCE, TransitionKind.DONE):
            mark_stage_complete(run_id, current_stage_id)
            cursor: int = state["cursor"]
            state["cursor"] = cursor + 1
            if transition.kind == TransitionKind.DONE:
                state["status"] = RunStatus.COMPLETED.value
            else:
                state["status"] = RunStatus.RUNNING.value
                next_stage_def = workflow.stages[state["cursor"]]
                create_stage(run_id, next_stage_def.id)
            _clear_transient_state(state)

        elif transition.kind == TransitionKind.RETRY:
            state["retry_count"] = retry_count + 1
            state["prior_feedback"] = result.reviewer_feedback

        elif transition.kind == TransitionKind.REVERT:
            mark_stage_complete(run_id, current_stage_id)
            assert transition.next_stage_id is not None
            target_idx = workflow.stage_index(transition.next_stage_id)
            state["cursor"] = target_idx
            create_stage(run_id, workflow.stages[target_idx].id)
            _clear_transient_state(state)

        elif transition.kind == TransitionKind.HALT:
            state["status"] = RunStatus.FAILED.value

        elif transition.kind == TransitionKind.COUNCIL:
            state["status"] = RunStatus.WAITING_COUNCIL.value

        state["last_transition"] = transition.kind.value
        state["last_transition_reason"] = transition.reason
        _write_state(run_id, state)

        return AdvanceResult(
            transition=transition,
            stage_result=result,
            run_status=RunStatus(state["status"]),
        )

    def _needs_policy_approval(self, stage_def: Any) -> bool:
        return (
            self._policy.requires_approval(stage_def.id)
            or self._policy.requires_approval(stage_def.skill)
        )


# ------------------------------------------------------------------
# State helpers
# ------------------------------------------------------------------

def _write_state(run_id: str, state: dict[str, Any]) -> None:
    state_path = run_dir(run_id) / _STATE_FILE
    content = yaml.safe_dump(state, sort_keys=False)
    atomic_write(state_path, content)


def _read_state(run_id: str) -> dict[str, Any]:
    state_path = run_dir(run_id) / _STATE_FILE
    if not state_path.is_file():
        raise FileNotFoundError(f"workflow state not found for run {run_id}")
    raw = state_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict):
        raise ValueError(f"invalid workflow state for run {run_id}")
    return parsed


def _current_stage_id(run_id: str, stage_def: Any) -> str:
    stages_path = run_dir(run_id) / "stages"
    if not stages_path.exists():
        return create_stage(run_id, stage_def.id)
    dirs = sorted(
        p.name for p in stages_path.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )
    return dirs[-1] if dirs else create_stage(run_id, stage_def.id)


def _clear_transient_state(state: dict[str, Any]) -> None:
    state["retry_count"] = 0
    state["prior_feedback"] = ""
    state.pop("waiting_reason", None)
    state.pop("policy_approved", None)


def _terminal_result(status: str) -> AdvanceResult:
    kind = TransitionKind.DONE if status == RunStatus.COMPLETED.value else TransitionKind.HALT
    return AdvanceResult(
        transition=Transition(kind, reason=f"run already {status}"),
        run_status=RunStatus(status),
    )


def _waiting_result(state: dict[str, Any]) -> AdvanceResult:
    status = RunStatus(state["status"])
    reason = state.get("waiting_reason", "awaiting action")
    kind = (
        TransitionKind.WAITING_APPROVAL
        if status == RunStatus.WAITING_APPROVAL
        else TransitionKind.COUNCIL
    )
    return AdvanceResult(
        transition=Transition(kind, reason=reason),
        run_status=status,
    )


def _snapshot_result(run_id: str) -> AdvanceResult:
    state = _read_state(run_id)
    status = RunStatus(state["status"])
    if status in (RunStatus.COMPLETED, RunStatus.FAILED):
        return _terminal_result(status.value)
    if status in (RunStatus.WAITING_APPROVAL, RunStatus.WAITING_COUNCIL):
        return _waiting_result(state)
    kind = TransitionKind(state["last_transition"]) if "last_transition" in state else TransitionKind.ADVANCE
    reason = state.get("last_transition_reason", "concurrent advance already completed")
    return AdvanceResult(
        transition=Transition(kind, reason=reason),
        run_status=status,
    )


__all__ = [
    "AdvanceResult",
    "RunStatus",
    "WorkflowEngine",
]
