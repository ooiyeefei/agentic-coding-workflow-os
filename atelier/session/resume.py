from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from atelier.adapters import ClaudeCodeAdapter, CodexAdapter, GenericAdapter, ToolAdapter
from atelier.compiler import (
    BudgetExceededError,
    Packet,
    PriorityTier,
    SampleDoc,
    Source,
    WorktreeRef,
    compile_packet,
)
from atelier.memory import Decision, MemoryRecord, RejectedAlternative, ReviewFinding, list_records
from atelier.util.paths import run_dir

_DEFAULT_SESSION_BUDGET = 12000


@dataclass(frozen=True)
class StageSummary:
    stage_id: str
    status: str
    path: Path


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    issue_ref: str
    workflow: str
    status: str
    current_stage: str | None
    waiting_reason: str | None
    stages: list[StageSummary]
    path: Path


def resume(run_id: str, target_agent: str) -> str:
    """Generate a paste-ready prompt for continuing a persisted run in another tool."""

    repo_root = Path.cwd()
    adapter = _adapter_for_target(target_agent, repo_root=repo_root)
    records = _load_memory_records(repo_root)
    packet = adapter.format_context_packet(run_id, "resume", records)
    compiled = _compile_session_packet(
        run_id=run_id,
        objective=(
            "Resume the Atelier run from its persisted state. Continue from the current "
            "stage, preserve completed work, and use pending stages as the execution plan."
        ),
        records=records,
        repo_root=repo_root,
        budget_tokens=_DEFAULT_SESSION_BUDGET,
    )
    return _join_sections(packet, "## Compiled Run Context\n\n" + compiled.body)


def _adapter_for_target(target_agent: str, *, repo_root: Path) -> ToolAdapter:
    normalized = target_agent.strip().casefold().replace("_", "-")
    if normalized in {"claude", "claude-code", "claudecode"}:
        return ClaudeCodeAdapter(repo_root=repo_root)
    if normalized in {"codex", "openai-codex"}:
        return CodexAdapter(repo_root=repo_root)
    if normalized in {"generic", "chatgpt", "gemini", "cowork"}:
        return GenericAdapter(repo_root=repo_root)
    raise ValueError(
        "unsupported target agent "
        f"{target_agent!r}; expected claude-code, codex, generic, chatgpt, gemini, or cowork"
    )


def _load_memory_records(repo_root: Path) -> list[MemoryRecord]:
    records = list_records(repo_root / ".atelier" / "memory")
    return sorted(
        records,
        key=lambda record: (
            _record_type_rank(record),
            record.timestamp,
            record.id,
        ),
        reverse=False,
    )


def _record_type_rank(record: MemoryRecord) -> int:
    if isinstance(record, Decision):
        return 0
    if isinstance(record, ReviewFinding):
        return 1
    if isinstance(record, RejectedAlternative):
        return 2
    return 3


def _compile_session_packet(
    *,
    run_id: str,
    objective: str,
    records: Sequence[MemoryRecord],
    repo_root: Path,
    budget_tokens: int,
) -> Packet:
    sources = _session_sources(run_id=run_id, records=records, repo_root=repo_root)
    try:
        return compile_packet(objective, sources, budget_tokens=budget_tokens)
    except BudgetExceededError:
        return compile_packet(
            objective,
            _must_have_sources(run_id, repo_root),
            budget_tokens=budget_tokens,
        )


def _session_sources(
    *,
    run_id: str,
    records: Sequence[MemoryRecord],
    repo_root: Path,
) -> list[Source]:
    sources: list[Source] = []
    summary = _load_run_summary(run_id, repo_root)
    sources.append(
        WorktreeRef(
            source_id=f"{run_id}:state",
            priority="must",
            title="Run State",
            content=_render_run_summary(summary),
            path=str(summary.path.relative_to(repo_root)),
        )
    )
    sources.extend(_run_artifact_sources(summary, repo_root))
    sources.extend(_memory_sources(records, run_id=run_id))
    return sources


def _must_have_sources(run_id: str, repo_root: Path) -> list[Source]:
    summary = _load_run_summary(run_id, repo_root)
    return [
        WorktreeRef(
            source_id=f"{run_id}:state",
            priority="must",
            title="Run State",
            content=_render_run_summary(summary),
            path=str(summary.path.relative_to(repo_root)),
        )
    ]


def _load_run_summary(run_id: str, repo_root: Path) -> RunSummary:
    path = repo_root / run_dir(run_id)
    if not path.is_dir():
        raise FileNotFoundError(f"run not found: {run_id}")

    metadata = _read_frontmatter_mapping(path / "run.md")
    state = _read_yaml_mapping(path / "workflow_state.yaml")
    stages = _stage_summaries(path)
    current_stage = next((stage.stage_id for stage in stages if stage.status == "current"), None)
    return RunSummary(
        run_id=run_id,
        issue_ref=str(metadata.get("issue_ref", "")).strip() or "unknown",
        workflow=str(state.get("workflow", "unknown")).strip() or "unknown",
        status=str(state.get("status", "unknown")).strip() or "unknown",
        current_stage=current_stage,
        waiting_reason=_optional_text(state.get("waiting_reason")),
        stages=stages,
        path=path,
    )


def _stage_summaries(run_path: Path) -> list[StageSummary]:
    stages_root = run_path / "stages"
    if not stages_root.is_dir():
        return []

    stages: list[StageSummary] = []
    current_marked = False
    for path in sorted(candidate for candidate in stages_root.iterdir() if candidate.is_dir()):
        if (path / ".complete").is_file():
            status = "completed"
        elif not current_marked:
            status = "current"
            current_marked = True
        else:
            status = "pending"
        stages.append(StageSummary(stage_id=path.name, status=status, path=path))
    return stages


def _render_run_summary(summary: RunSummary) -> str:
    completed = [stage.stage_id for stage in summary.stages if stage.status == "completed"]
    pending = [stage.stage_id for stage in summary.stages if stage.status == "pending"]
    current = summary.current_stage or "none"
    lines = [
        f"Run ID: {summary.run_id}",
        f"Issue: {summary.issue_ref}",
        f"Workflow: {summary.workflow}",
        f"Status: {summary.status}",
        f"Current stage: {current}",
        "Completed stages: " + (", ".join(completed) if completed else "none"),
        "Pending stages: " + (", ".join(pending) if pending else "none"),
        "Stages:",
        *[f"- {stage.stage_id}: {stage.status}" for stage in summary.stages],
    ]
    if summary.waiting_reason:
        lines.insert(5, f"Waiting reason: {summary.waiting_reason}")
    return "\n".join(lines)


def _run_artifact_sources(summary: RunSummary, repo_root: Path) -> list[Source]:
    sources: list[Source] = []
    for stage in summary.stages:
        sources.extend(_stage_artifact_sources(stage, repo_root))
    return sources


def _stage_artifact_sources(stage: StageSummary, repo_root: Path) -> Iterable[Source]:
    artifact_names = (
        "stage.md",
        "packet.md",
        "evidence.md",
        "evidence.json",
        "transcript.jsonl",
    )
    for name in artifact_names:
        path = stage.path / name
        source = _source_from_file(path, stage=stage, repo_root=repo_root)
        if source is not None:
            yield source

    for folder_name, title in (("decisions", "Stage Decisions"), ("findings", "Stage Findings")):
        folder = stage.path / folder_name
        if not folder.is_dir():
            continue
        for path in sorted(candidate for candidate in folder.rglob("*") if candidate.is_file()):
            source = _source_from_file(path, stage=stage, repo_root=repo_root, title_prefix=title)
            if source is not None:
                yield source


def _source_from_file(
    path: Path,
    *,
    stage: StageSummary,
    repo_root: Path,
    title_prefix: str | None = None,
) -> Source | None:
    if not path.is_file():
        return None
    content = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not content:
        return None

    relative = path.relative_to(repo_root)
    priority: PriorityTier = (
        "must" if path.name == "stage.md" or stage.status == "current" else "should"
    )
    title = title_prefix or f"{stage.stage_id} {path.name}"
    return WorktreeRef(
        source_id=relative.as_posix(),
        priority=priority,
        title=title,
        content=content,
        path=relative.as_posix(),
    )


def _memory_sources(records: Sequence[MemoryRecord], *, run_id: str) -> list[Source]:
    sources: list[Source] = []
    for record in records:
        source_run = "run" if record.run_id == run_id else "memory"
        priority: PriorityTier = (
            "must" if record.run_id == run_id and isinstance(record, Decision) else "should"
        )
        sources.append(
            SampleDoc(
                source_id=record.id,
                priority=priority,
                title=f"{source_run} {record.type}: {record.id}",
                content=_render_memory_record(record),
                path=_memory_record_path(record),
            )
        )
    return sources


def _memory_record_path(record: MemoryRecord) -> str | None:
    if "role-protocol" in record.tags and record.source == "atelier:session.prompt":
        return None
    return f".atelier/memory/{record.path_fragment.as_posix()}"


def _render_memory_record(record: MemoryRecord) -> str:
    details = [
        f"Type: {record.type}",
        f"Run: {record.run_id}",
        f"Stage: {record.stage_id}",
        f"Source: {record.source}",
    ]
    if _memory_record_path(record) is None:
        details.append("Persistence: in-memory session prompt")
    if record.related_issues:
        details.append("Issues: " + ", ".join(record.related_issues))
    if record.related_adrs:
        details.append("ADRs: " + ", ".join(record.related_adrs))
    if record.tags:
        details.append("Tags: " + ", ".join(record.tags))
    return "\n".join([*details, "", record.body.strip()])


def _read_yaml_mapping(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return cast(dict[str, object], payload)


def _read_frontmatter_mapping(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        return {}
    _, _, remainder = raw.partition("---\n")
    frontmatter_text, separator, _ = remainder.partition("\n---\n")
    if not separator:
        return {}
    payload = yaml.safe_load(frontmatter_text)
    if not isinstance(payload, dict):
        return {}
    return cast(dict[str, object], payload)


def _optional_text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _join_sections(*sections: str) -> str:
    return "\n\n".join(section.strip() for section in sections if section.strip()) + "\n"


__all__ = ["resume"]
