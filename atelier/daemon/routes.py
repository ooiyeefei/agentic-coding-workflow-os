from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import yaml
from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, StringConstraints
from sse_starlette.sse import EventSourceResponse

from atelier.audit import EventType
from atelier.audit import log as audit_log
from atelier.cli.commands.run import (
    RunRecord,
    RunRecordLoadError,
    load_run_record,
)
from atelier.cli.formatters import pushd
from atelier.rungraph.lock import run_lock
from atelier.util.fs import atomic_write
from atelier.util.paths import run_dir
from atelier.workflow.engine import AdvanceResult, RunStatus, WorkflowEngine
from atelier.workflow.loader import WorkflowNotFoundError

from .events import stream_run_events

if TYPE_CHECKING:
    from .server import DaemonConfig

router = APIRouter()
_LOG = logging.getLogger(__name__)

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_ref: NonEmptyText
    workflow: NonEmptyText = "speckit-loop"
    context: str = ""


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    run: dict[str, object]


def _daemon_config(request: Request) -> DaemonConfig:
    return request.app.state.daemon_config  # type: ignore[no-any-return]


def _workflow_engine(config: DaemonConfig) -> WorkflowEngine:
    return WorkflowEngine(
        deps=config.stage_executor_deps,
        user_workflows_dir=config.user_workflows_dir,
        defaults_workflows_dir=config.defaults_workflows_dir,
    )


def _normalize_issue_ref(issue_ref: str) -> str:
    stripped = issue_ref.strip()
    if stripped.isdigit():
        return f"issue #{stripped}"
    return stripped


def _load_run_record_or_error(repo_root: Path, run_id: str) -> RunRecord:
    try:
        return load_run_record(repo_root, run_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid run_id {run_id!r}",
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"run {run_id} not found",
        ) from exc
    except RunRecordLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


def _record_result_events(repo_root: Path, run_id: str, result: AdvanceResult) -> None:
    if result.stage_result is not None:
        audit_log(
            run_id,
            EventType.TOOL_CALL,
            {
                "tool_name": result.stage_result.stage_id,
                "result_summary": (
                    f"verdict={result.stage_result.verdict.value}; "
                    f"transition={result.transition.kind.value}"
                ),
                "success": True,
            },
            repo_root=repo_root,
        )

    if result.run_status in (RunStatus.WAITING_APPROVAL, RunStatus.WAITING_COUNCIL):
        record = load_run_record(repo_root, run_id)
        audit_log(
            run_id,
            EventType.GATE_ENTERED,
            {
                "gate_name": record.waiting_reason or result.transition.kind.value,
                "from_stage": _gate_from_stage(record, result),
                "to_stage": result.transition.next_stage_id or "",
                "verdict": result.transition.reason or result.run_status.value,
            },
            repo_root=repo_root,
        )


def _gate_from_stage(record: RunRecord, result: AdvanceResult) -> str:
    if result.stage_result is not None:
        return result.stage_result.stage_id
    return record.current_stage or ""


def _mark_run_failed(repo_root: Path, run_id: str, reason: str) -> None:
    with pushd(repo_root):
        state_path = run_dir(run_id) / "workflow_state.yaml"
        with run_lock(run_id):
            raw = state_path.read_text(encoding="utf-8")
            parsed = yaml.safe_load(raw)
            if not isinstance(parsed, dict):
                raise ValueError(f"invalid workflow state for run {run_id}")

            parsed["status"] = RunStatus.FAILED.value
            parsed["last_transition"] = "halt"
            parsed["last_transition_reason"] = reason
            parsed["retry_count"] = 0
            parsed["prior_feedback"] = ""
            parsed.pop("waiting_reason", None)
            parsed.pop("policy_approved", None)
            atomic_write(state_path, yaml.safe_dump(parsed, sort_keys=False))


async def _drive_run_until_blocked(config: DaemonConfig, run_id: str) -> None:
    try:
        with pushd(config.repo_root):
            engine = _workflow_engine(config)
            while True:
                result = await engine.advance(run_id)
                _record_result_events(config.repo_root, run_id, result)
                if result.run_status != RunStatus.RUNNING:
                    return
                await asyncio.sleep(0)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        _LOG.exception("daemon background run failed for %s", run_id)
        reason = f"daemon background execution failed: {exc}"
        _mark_run_failed(config.repo_root, run_id, reason)
        audit_log(
            run_id,
            EventType.TOOL_CALL,
            {
                "tool_name": "daemon-runner",
                "result_summary": reason,
                "success": False,
            },
            repo_root=config.repo_root,
        )


def _schedule_run_drive(request: Request, config: DaemonConfig, run_id: str) -> None:
    tasks: dict[str, asyncio.Task[None]] = request.app.state.run_tasks
    current = tasks.get(run_id)
    if current is not None and not current.done():
        return

    task = asyncio.create_task(_drive_run_until_blocked(config, run_id))
    tasks[run_id] = task

    def _cleanup(completed: asyncio.Task[None]) -> None:
        active = tasks.get(run_id)
        if active is completed:
            tasks.pop(run_id, None)

    task.add_done_callback(_cleanup)


@router.post("/runs", status_code=status.HTTP_201_CREATED)
async def create_run(payload: CreateRunRequest, request: Request) -> dict[str, object]:
    config = _daemon_config(request)
    engine = _workflow_engine(config)

    try:
        with pushd(config.repo_root):
            run_id = engine.start(
                issue_ref=_normalize_issue_ref(payload.issue_ref),
                workflow_name=payload.workflow,
                context=payload.context,
            )
    except WorkflowNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    if config.auto_advance_runs:
        _schedule_run_drive(request, config, run_id)

    return _load_run_record_or_error(config.repo_root, run_id).to_payload()


@router.get("/runs/{run_id}")
def get_run(run_id: str, request: Request) -> dict[str, object]:
    config = _daemon_config(request)
    return _load_run_record_or_error(config.repo_root, run_id).to_payload()


@router.get("/runs/{run_id}/events")
async def get_run_events(
    run_id: str,
    request: Request,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> EventSourceResponse:
    config = _daemon_config(request)
    _load_run_record_or_error(config.repo_root, run_id)
    return EventSourceResponse(
        stream_run_events(
            request=request,
            repo_root=config.repo_root,
            run_id=run_id,
            poll_interval=config.event_poll_interval,
            limit=limit,
        ),
        ping=15,
    )


@router.post("/runs/{run_id}/approve")
async def approve_run(run_id: str, request: Request) -> ApprovalResponse:
    config = _daemon_config(request)
    record = _load_run_record_or_error(config.repo_root, run_id)

    if record.status != "waiting_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"run {run_id} is {record.status}; only waiting_approval runs can be approved",
        )
    if record.waiting_reason != "gate":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="only completed gate waits can be approved over HTTP in Phase 0",
        )

    with pushd(config.repo_root):
        engine = _workflow_engine(config)
        result = await engine.resume(run_id, approved=True)

    _record_result_events(config.repo_root, run_id, result)
    if config.auto_advance_runs and result.run_status == RunStatus.RUNNING:
        _schedule_run_drive(request, config, run_id)

    updated = _load_run_record_or_error(config.repo_root, run_id).to_payload()
    return ApprovalResponse(approved=True, run=updated)


__all__ = ["router"]
