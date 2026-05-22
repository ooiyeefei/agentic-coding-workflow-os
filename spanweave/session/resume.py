from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from spanweave.adapters import ClaudeCodeAdapter, CodexAdapter, GenericAdapter, ToolAdapter
from spanweave.compiler import (
    BudgetExceededError,
    Packet,
    PriorityTier,
    SampleDoc,
    Source,
    WorktreeRef,
    compile_packet,
)
from spanweave.memory import (
    Decision,
    MemoryRecord,
    RejectedAlternative,
    ReviewFinding,
    WorkflowEvent,
    list_records,
)
from spanweave.util.paths import run_dir

_DEFAULT_SESSION_BUDGET = 12000
_DEFAULT_BRIEFING_STAGES = 3
_BRIEFING_BODY_BUDGET_CHARS = 1800
_BRIEFING_DROP_SECTION_HEADERS = (
    "Integration Rules",
    "Provenance",
    "Run Worktree",
)


@dataclass(frozen=True)
class StageSummary:
    stage_id: str
    status: str
    path: Path


@dataclass(frozen=True)
class StageBriefing:
    stage_id: str
    status: str
    body: str
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
    summary = _load_run_summary(run_id, repo_root)
    briefings = _stage_briefings(
        summary,
        repo_root,
        max_stages=_DEFAULT_BRIEFING_STAGES,
        max_chars=_BRIEFING_BODY_BUDGET_CHARS,
    )
    briefings_section = _render_stage_briefings_section(briefings)
    compiled = _compile_session_packet(
        run_id=run_id,
        objective=(
            "Resume the Spanweave run from its persisted state. Continue from the current "
            "stage, preserve completed work, and use pending stages as the execution plan."
        ),
        records=records,
        repo_root=repo_root,
        budget_tokens=_DEFAULT_SESSION_BUDGET,
        briefings=briefings,
    )
    sections = [packet]
    if briefings_section is not None:
        sections.append(briefings_section)
    sections.append("## Compiled Run Context\n\n" + compiled.body)
    return _join_sections(*sections)


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
    memory_root = repo_root / ".spanweave" / "memory"
    seen_ids: set[str] = set()
    all_records: list[MemoryRecord] = []

    # Read from all locations: legacy flat, shared/, and private/
    for subdir in (memory_root, memory_root / "shared", memory_root / "private"):
        if not subdir.is_dir():
            continue
        for record in list_records(subdir):
            if record.id not in seen_ids:
                seen_ids.add(record.id)
                all_records.append(record)

    return sorted(
        all_records,
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
    if isinstance(record, WorkflowEvent):
        return 4  # audit-trail, lowest priority
    return 3


def _compile_session_packet(
    *,
    run_id: str,
    objective: str,
    records: Sequence[MemoryRecord],
    repo_root: Path,
    budget_tokens: int,
    briefings: Sequence[StageBriefing] | None = None,
) -> Packet:
    sources = _session_sources(
        run_id=run_id,
        records=records,
        repo_root=repo_root,
        briefings=briefings,
    )
    try:
        return compile_packet(objective, sources, budget_tokens=budget_tokens)
    except BudgetExceededError:
        return compile_packet(
            objective,
            _must_have_sources(run_id, repo_root, briefings=briefings),
            budget_tokens=budget_tokens,
        )


def _session_sources(
    *,
    run_id: str,
    records: Sequence[MemoryRecord],
    repo_root: Path,
    briefings: Sequence[StageBriefing] | None = None,
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
    briefing_paths = {briefing.path.resolve() for briefing in briefings or ()}
    sources.extend(_briefing_sources(briefings or (), repo_root))
    sources.extend(
        _run_artifact_sources(summary, repo_root, exclude_paths=briefing_paths)
    )
    sources.extend(_memory_sources(records, run_id=run_id))
    return sources


def _must_have_sources(
    run_id: str,
    repo_root: Path,
    *,
    briefings: Sequence[StageBriefing] | None = None,
) -> list[Source]:
    summary = _load_run_summary(run_id, repo_root)
    sources: list[Source] = [
        WorktreeRef(
            source_id=f"{run_id}:state",
            priority="must",
            title="Run State",
            content=_render_run_summary(summary),
            path=str(summary.path.relative_to(repo_root)),
        )
    ]
    sources.extend(_briefing_sources(briefings or (), repo_root))
    return sources


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


def _run_artifact_sources(
    summary: RunSummary,
    repo_root: Path,
    *,
    exclude_paths: set[Path] | None = None,
) -> list[Source]:
    sources: list[Source] = []
    for stage in summary.stages:
        sources.extend(
            _stage_artifact_sources(stage, repo_root, exclude_paths=exclude_paths)
        )
    return sources


def _stage_artifact_sources(
    stage: StageSummary,
    repo_root: Path,
    *,
    exclude_paths: set[Path] | None = None,
) -> Iterable[Source]:
    excluded = exclude_paths or set()
    artifact_names = (
        "stage.md",
        "packet.md",
        "evidence.md",
        "evidence.json",
        "transcript.jsonl",
    )
    for name in artifact_names:
        path = stage.path / name
        if path.resolve() in excluded:
            continue
        source = _source_from_file(path, stage=stage, repo_root=repo_root)
        if source is not None:
            yield source

    for folder_name, title in (("decisions", "Stage Decisions"), ("findings", "Stage Findings")):
        folder = stage.path / folder_name
        if not folder.is_dir():
            continue
        for path in sorted(candidate for candidate in folder.rglob("*") if candidate.is_file()):
            if path.resolve() in excluded:
                continue
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
        # WorkflowEvent records are audit-trail; omit from resume context
        if isinstance(record, WorkflowEvent):
            continue
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
    if "role-protocol" in record.tags and record.source == "spanweave:session.prompt":
        return None
    return f".spanweave/memory/{record.path_fragment.as_posix()}"


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


def _stage_briefings(
    summary: RunSummary,
    repo_root: Path,
    *,
    max_stages: int,
    max_chars: int,
) -> list[StageBriefing]:
    """Pick the most-relevant N stages and emit a compact briefing for each.

    Files-first invariant: reads from each stage's `packet.md` directly. The
    selection prefers the current stage and the most recently completed
    stages, so a fresh agent inherits the substantive context that matters
    for resuming work.
    """
    if max_stages <= 0:
        return []

    selected = _pick_briefing_stages(summary.stages, max_stages)
    briefings: list[StageBriefing] = []
    for stage in selected:
        packet_path = stage.path / "packet.md"
        if not packet_path.is_file():
            continue
        body = _condense_packet_body(
            packet_path.read_text(encoding="utf-8", errors="ignore"),
            max_chars=max_chars,
        )
        if not body:
            continue
        briefings.append(
            StageBriefing(
                stage_id=stage.stage_id,
                status=stage.status,
                body=body,
                path=packet_path,
            )
        )
    return briefings


def _pick_briefing_stages(
    stages: Sequence[StageSummary], max_stages: int
) -> list[StageSummary]:
    """Pick stages that carry the most resume-relevant context.

    Always include the current stage (a resuming agent starts there).
    Then prefer the earliest completed stages — specify/clarify/plan
    typically encode the substantive decisions a fresh agent needs to
    answer "what was decided?" — over later mechanical stages.
    """
    if not stages:
        return []
    current = [stage for stage in stages if stage.status == "current"]
    completed = [stage for stage in stages if stage.status == "completed"]
    pending = [stage for stage in stages if stage.status == "pending"]

    ordered: list[StageSummary] = []
    seen_ids: set[str] = set()
    for stage in [*current, *completed, *pending]:
        if stage.stage_id in seen_ids:
            continue
        seen_ids.add(stage.stage_id)
        ordered.append(stage)
        if len(ordered) >= max_stages:
            break
    return sorted(ordered, key=lambda stage: stage.stage_id)


_PACKET_SECTION_HEADER = re.compile(
    r"^##\s+(?P<title>.+?)\s*$\n(?P<after>(?:\n)?_Source:[^\n]*\n)?",
    re.MULTILINE,
)
_BRIEFING_DROP_SOURCE_TOKENS = (
    "| integration-rules |",
    "| acceptance_gate |",
)


def _condense_packet_body(raw: str, *, max_chars: int) -> str:
    """Strip noise from a stage packet and bound it to a char budget.

    Removes sections that repeat across every stage packet (the
    integration-rules dump from AGENTS.md, the run-worktree path, and
    the trailing provenance footer) so the briefing surfaces the issue
    text, acceptance criteria, and clarified constraints — the
    substantive content a resuming agent needs.
    """
    sections = _split_packet_sections(raw)
    kept: list[str] = []
    for title, block in sections:
        if title is None:
            cleaned = block.strip()
            if cleaned:
                kept.append(cleaned)
            continue
        if any(token in title for token in _BRIEFING_DROP_SECTION_HEADERS):
            continue
        if any(token in block for token in _BRIEFING_DROP_SOURCE_TOKENS):
            continue
        kept.append(block.strip())
    condensed = "\n\n".join(part for part in kept if part)
    condensed = condensed.strip()
    if len(condensed) <= max_chars:
        return condensed
    truncated = condensed[: max(0, max_chars - 1)].rstrip()
    return truncated + "…"


def _split_packet_sections(raw: str) -> list[tuple[str | None, str]]:
    """Split a markdown packet into (header_title, block) pairs.

    Only ``## `` headings that are immediately followed by a ``_Source:``
    annotation are treated as real packet sections; ``##`` headings that
    appear inside an embedded body (e.g., the ``Active Technologies``
    sub-headings inside the integration-rules block) stay attached to
    their parent section. The first block carries ``None`` as its title.
    """
    sections: list[tuple[str | None, str]] = []
    matches = [
        match
        for match in _PACKET_SECTION_HEADER.finditer(raw)
        if match.group("after")
    ]
    if not matches:
        return [(None, raw)]
    if matches[0].start() > 0:
        sections.append((None, raw[: matches[0].start()]))
    for index, match in enumerate(matches):
        title = match.group("title").strip()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        block = raw[match.start() : end]
        sections.append((title, block))
    return sections


def _render_stage_briefings_section(
    briefings: Sequence[StageBriefing],
) -> str | None:
    if not briefings:
        return None
    parts = [
        "## Recent Stage Context",
        (
            "Condensed briefings from the most relevant stage packets so a "
            "fresh agent can answer 'what was decided in <stage>?' without "
            "re-reading every file."
        ),
    ]
    for briefing in briefings:
        relative = briefing.path
        try:
            relative = briefing.path.relative_to(Path.cwd())
        except ValueError:
            relative = briefing.path
        parts.append(
            f"### {briefing.stage_id} [{briefing.status}]\n"
            f"_Source: stage_packet | {briefing.stage_id} | {relative}_\n\n"
            f"{briefing.body}"
        )
    return "\n\n".join(parts)


def _briefing_sources(
    briefings: Sequence[StageBriefing], repo_root: Path
) -> list[Source]:
    sources: list[Source] = []
    for briefing in briefings:
        try:
            relative = briefing.path.relative_to(repo_root).as_posix()
        except ValueError:
            relative = briefing.path.as_posix()
        priority: PriorityTier = "must" if briefing.status == "current" else "should"
        sources.append(
            WorktreeRef(
                source_id=f"{briefing.stage_id}:briefing",
                priority=priority,
                title=f"{briefing.stage_id} briefing [{briefing.status}]",
                content=briefing.body,
                path=relative,
            )
        )
    return sources


__all__ = ["resume"]
