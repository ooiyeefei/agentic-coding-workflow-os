from __future__ import annotations

from pathlib import Path

from spanweave.memory import Decision, MemoryRecord
from spanweave.util.ulid import new_stage_id

from .resume import (
    _DEFAULT_SESSION_BUDGET,
    _adapter_for_target,
    _compile_session_packet,
    _join_sections,
    _load_memory_records,
)

_ROLE_PROTOCOLS = {
    "coder": (
        "Implementation-focused protocol",
        (
            "Act as the Coder agent. Inspect the existing implementation before editing, "
            "make the smallest coherent changes that satisfy the run objective, preserve "
            "captured decisions, and verify with targeted tests before reporting completion."
        ),
    ),
    "reviewer": (
        "Review-focused protocol",
        (
            "Act as the Reviewer agent. Execution is mandatory: inspect the diff and relevant "
            "files directly, run or request the concrete verification commands needed for the "
            "risk level, lead with findings ordered by severity, and call out missing tests."
        ),
    ),
}


def generate_prompt(run_id: str, role: str, target_agent: str) -> str:
    """Generate a role-specific prompt for a run and target tool."""

    repo_root = Path.cwd()
    normalized_role = _normalize_role(role)
    adapter = _adapter_for_target(target_agent, repo_root=repo_root)
    records = _with_role_protocol(_load_memory_records(repo_root), run_id, normalized_role)
    packet = adapter.format_context_packet(run_id, normalized_role, records)
    title, body = _ROLE_PROTOCOLS[normalized_role]
    compiled = _compile_session_packet(
        run_id=run_id,
        objective=(
            f"Generate a fresh {normalized_role} prompt for this Spanweave run. "
            "Use the role protocol as the top-level behavior contract."
        ),
        records=records,
        repo_root=repo_root,
        budget_tokens=_DEFAULT_SESSION_BUDGET,
    )
    role_section = f"## {title}\n\n{body}"
    return _join_sections(role_section, packet, "## Compiled Run Context\n\n" + compiled.body)


def _normalize_role(role: str) -> str:
    normalized = role.strip().casefold().replace("_", "-")
    if normalized not in _ROLE_PROTOCOLS:
        supported = ", ".join(sorted(_ROLE_PROTOCOLS))
        raise ValueError(f"unsupported role {role!r}; expected one of: {supported}")
    return normalized


def _with_role_protocol(
    records: list[MemoryRecord],
    run_id: str,
    role: str,
) -> list[MemoryRecord]:
    title, body = _ROLE_PROTOCOLS[role]
    protocol = Decision(
        run_id=run_id,
        stage_id=new_stage_id(),
        tags=["session-continuity", role, "role-protocol"],
        source="spanweave:session.prompt",
        body=f"{title}: {body}",
    )
    return [protocol, *records]


__all__ = ["generate_prompt"]
