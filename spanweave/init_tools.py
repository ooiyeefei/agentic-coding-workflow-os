"""Tool-specific wiring logic for `spanweave init --tool <name>`.

Each function wires auto-extraction hooks for a specific agent tool.
All operations are idempotent — running them twice does not break anything.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import click

# Full args for the SessionEnd-hook command. `--detach` makes the hook a fast
# launcher (spawns extraction, returns in <1s) so a slow quality model never
# trips the hook timeout.
_EXTRACT_ARGS = "extract-latest --repo . --detach"
# Stable substring present in BOTH the current and the pre-`--detach` hook
# forms. Matching on this (not the full args) lets a re-run upgrade an older
# hook in place instead of appending a duplicate.
_EXTRACT_RECOGNIZE = "extract-latest --repo ."

# Claude Code hook event name. SessionEnd fires once when a session terminates
# (window close, /clear, exit) — the right point to capture decisions. The
# older `Stop` event fires after every assistant turn, which would re-extract
# repeatedly during a long session and waste cycles. Migration: any existing
# Stop entry pointing at extract-latest is moved to SessionEnd on re-init.
_HOOK_EVENT = "SessionEnd"
_LEGACY_HOOK_EVENT = "Stop"


def _resolve_hook_command(repo_root: Path) -> str:
    """Resolve a hook command that works in a bare /bin/sh (no venv, no uv).

    Claude Code fires SessionEnd hooks in a minimal shell where neither the
    venv nor `uv` is on PATH, so a plain `spanweave ...` (or `uv run spanweave
    ...`) command fails with "not found". When a repo-local virtualenv is
    present (dev / uv-project install), point the hook at its entry-point
    binary via a repo-relative path — hooks run with cwd = project root (the
    same guarantee `--repo .` already relies on). Otherwise assume a global
    install on PATH.

    We deliberately avoid ``shutil.which("spanweave")``: when this runs inside
    ``uv run spanweave init``, the venv's binary is already on the process PATH,
    so ``which`` would falsely report a global install.
    """
    venv_bin = repo_root / ".venv" / "bin" / "spanweave"
    if venv_bin.exists():
        return f".venv/bin/spanweave {_EXTRACT_ARGS}"
    return f"spanweave {_EXTRACT_ARGS}"

# Read-pointer: tells a tool where to LOAD prior context on session start.
# Points at .spanweave/memory/ — records captured from any prior session in any
# tool, plus the shared/ subtree promoted for team visibility. Each record type
# lives in its own subdir; the pointer enumerates them so a fresh agent doesn't
# silently skip findings, reflections, or rejected alternatives.
_READ_POINTER_HEADING = "## Load Spanweave context on session start"
_READ_POINTER = """\
## Load Spanweave context on session start

Before substantive work on this project, load prior context from
`.spanweave/memory/`. Each record type has its own subdir; load all of them, and
also the matching `shared/` copy (records a teammate promoted for team
visibility):

- `.spanweave/memory/decisions/` and `.spanweave/memory/shared/decisions/` — \
choices made and the reasoning behind them.
- `.spanweave/memory/findings/` and `.spanweave/memory/shared/findings/` — \
non-obvious facts discovered about the code or system.
- `.spanweave/memory/reflections/` and `.spanweave/memory/shared/reflections/` — \
post-hoc lessons about what worked or didn't.
- `.spanweave/memory/rejected_alternatives/` and \
`.spanweave/memory/shared/rejected_alternatives/` — options considered and \
ruled out, with the reason (so you don't re-propose them).

This is cross-tool memory: another agent (Claude Code, Codex, Cursor) may have
worked here before you. Build on what's already recorded instead of re-deriving
it.
"""

# Write-pointer: tells a tool to CAPTURE this session's decisions on exit.
# (Claude Code does this automatically via a SessionEnd hook, so it gets the
# read-pointer only; Codex/Cursor/Windsurf have no native hooks and rely on the
# agent following this instruction.)
_WRITE_POINTER_HEADING = "## Capture decisions on session end"
_WRITE_POINTER = """\
## Capture decisions on session end

Before ending your session, run:
```bash
spanweave extract-latest --repo .
```
This captures this session's decisions into `.spanweave/memory/pending/` for review.
"""


def _ensure_sections(path: Path, sections: list[tuple[str, str]]) -> list[str]:
    """Append any sections whose heading marker is not already in the file.

    ``sections`` is a list of ``(heading_marker, section_text)``. A section is
    appended only when its heading is absent — making this idempotent AND
    migration-friendly: a repo that already has one section but not another
    gets only the missing one added, and existing user content is never
    rewritten. Returns the headings that were added.
    """
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    added: list[str] = []
    for heading, body in sections:
        if heading in content:
            continue
        content = content.rstrip("\n")
        content = f"{content}\n\n{body}" if content else body
        added.append(heading)
    if added:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not content.endswith("\n"):
            content += "\n"
        path.write_text(content, encoding="utf-8")
    return added


def wire_claude_code(repo_root: Path) -> None:
    """Wire a Claude Code SessionEnd hook that runs extract-latest on session end.

    Creates or updates .claude/settings.json with a hooks.SessionEnd entry (the
    automatic *capture* mechanism), and ensures CLAUDE.md carries the
    *read-pointer* so a fresh Claude Code session loads prior context.
    Preserves all existing content and is idempotent. Migrates any legacy
    hooks.Stop entry (which fired per-turn) to hooks.SessionEnd in place,
    keeping the matcher block + command intact.
    """
    # Read side: ensure CLAUDE.md tells the agent to load .spanweave/ context.
    # (The SessionEnd hook below is the write/capture side.)
    if _ensure_sections(repo_root / "CLAUDE.md", [(_READ_POINTER_HEADING, _READ_POINTER)]):
        click.echo("✓ Added Spanweave context-load instruction to CLAUDE.md.")

    claude_dir = repo_root / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    settings_path = claude_dir / "settings.json"

    # Read existing or start fresh
    data: dict[str, Any]
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            data = {}
    else:
        data = {}

    # Ensure hooks.SessionEnd structure. Claude Code expects each entry to be a
    # matcher-block: {"matcher": "", "hooks": [{"type": "command", ...}]}. The
    # matcher is empty because SessionEnd has no tool to match against.
    if "hooks" not in data:
        data["hooks"] = {}
    hooks = cast(dict[str, Any], data["hooks"])

    # Migrate: move any legacy Stop entry whose inner command targets
    # extract-latest into SessionEnd. SessionEnd fires once per session-end
    # (close/exit/clear) — what we always meant — while Stop fires after every
    # assistant turn and would re-extract repeatedly. Migration preserves the
    # matcher block + inner hook intact; non-spanweave entries are left under
    # Stop untouched so we don't break unrelated hooks.
    _migrate_legacy_stop_to_session_end(hooks)

    if _HOOK_EVENT not in hooks:
        hooks[_HOOK_EVENT] = []
    event_blocks = cast(list[dict[str, Any]], hooks[_HOOK_EVENT])

    hook_command = _resolve_hook_command(repo_root)

    # Find any existing spanweave extract-latest hook, matching on the args
    # suffix so we recognize it regardless of how spanweave is invoked
    # (plain `spanweave`, `.venv/bin/spanweave`, `uv run spanweave`). This makes
    # the wiring idempotent AND self-healing: a stale/broken invocation from an
    # earlier version is upgraded in place rather than duplicated.
    for block in event_blocks:
        if not isinstance(block, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
            continue
        for inner_hook in block.get("hooks", []):
            command = inner_hook.get("command", "")
            if _EXTRACT_RECOGNIZE not in command:
                continue
            if command == hook_command:
                # If we migrated a legacy Stop entry that already had the right
                # command, persist that move; otherwise this is a no-op write
                # that keeps idempotency clean.
                settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
                click.echo(
                    f"✓ Claude Code {_HOOK_EVENT} hook already wired. "
                    "Decisions will be auto-extracted when sessions end."
                )
                return
            # Stale invocation (e.g. the pre-fix bare `spanweave` that fails in
            # the bare hook shell) — upgrade it in place.
            inner_hook["command"] = hook_command
            settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            click.echo(
                f"✓ Claude Code {_HOOK_EVENT} hook updated to a shell-resilient "
                f"command ({hook_command})."
            )
            return

    # Append our hook as a properly-shaped matcher block
    event_blocks.append(
        {
            "matcher": "",
            "hooks": [{"type": "command", "command": hook_command}],
        }
    )

    # Write back preserving formatting
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    click.echo(
        f"✓ Claude Code {_HOOK_EVENT} hook wired. "
        "Decisions will be auto-extracted when sessions end."
    )


def _migrate_legacy_stop_to_session_end(hooks: dict[str, Any]) -> None:
    """Move any legacy hooks.Stop spanweave entry to hooks.SessionEnd.

    Earlier spanweave releases wired the capture command under ``hooks.Stop``,
    which fires after every assistant turn. The correct event is ``SessionEnd``
    (fires once when a session terminates). This helper migrates any matcher-
    block under ``Stop`` whose inner ``hooks`` array contains a spanweave
    extract-latest command into ``SessionEnd``.

    Migration policy (preserves unrelated hooks):
    - If a Stop matcher-block contains ONLY the spanweave hook, the whole block
      moves to SessionEnd.
    - If a Stop matcher-block also contains OTHER inner hooks (e.g. a
      user-owned shell command, or a different tool's wiring), only the
      spanweave inner hook is split out and moved — the rest stay under Stop
      so we never silently drop a hook a user added themselves.
    - If Stop ends up empty after migration, the empty list is left in place
      (minimal-diff; existing settings.json shape is preserved).
    """
    legacy_raw = hooks.get(_LEGACY_HOOK_EVENT)
    if not isinstance(legacy_raw, list) or not legacy_raw:
        return
    legacy = cast(list[dict[str, Any]], legacy_raw)

    moved_inner_hooks: list[dict[str, Any]] = []
    blocks_to_drop: list[int] = []

    for idx, block in enumerate(legacy):
        if not isinstance(block, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
            continue
        inner_hooks_raw = block.get("hooks", [])
        if not isinstance(inner_hooks_raw, list):
            continue
        inner_hooks = cast(list[dict[str, Any]], inner_hooks_raw)
        spanweave_inner: list[dict[str, Any]] = []
        other_inner: list[dict[str, Any]] = []
        for inner in inner_hooks:
            if not isinstance(inner, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
                other_inner.append(inner)
                continue
            command = inner.get("command", "")
            if isinstance(command, str) and _EXTRACT_RECOGNIZE in command:
                spanweave_inner.append(inner)
            else:
                other_inner.append(inner)
        if not spanweave_inner:
            continue
        moved_inner_hooks.extend(spanweave_inner)
        if other_inner:
            # Block had a mix — leave non-spanweave hooks under Stop intact.
            block["hooks"] = other_inner
        else:
            # Block was spanweave-only — drop it from Stop entirely.
            blocks_to_drop.append(idx)

    if not moved_inner_hooks:
        return

    # Apply Stop-side drops in reverse so indices stay valid.
    for idx in reversed(blocks_to_drop):
        del legacy[idx]

    session_end_raw = hooks.setdefault(_HOOK_EVENT, [])
    if not isinstance(session_end_raw, list):
        # Legacy/garbled shape — replace with a fresh list rather than crash.
        session_end_raw = []
        hooks[_HOOK_EVENT] = session_end_raw
    session_end_blocks = cast(list[dict[str, Any]], session_end_raw)
    session_end_blocks.append(
        {
            "matcher": "",
            "hooks": moved_inner_hooks,
        }
    )


def wire_codex(repo_root: Path) -> None:
    """Wire AGENTS.md for Codex: read-pointer (load context) + write-pointer.

    Codex auto-reads AGENTS.md natively, so both the load-context and
    capture-on-end instructions go there. Creates AGENTS.md if missing.
    Idempotent and migration-friendly (adds only missing sections).
    """
    agents_path = repo_root / "AGENTS.md"
    added = _ensure_sections(
        agents_path,
        [(_READ_POINTER_HEADING, _READ_POINTER), (_WRITE_POINTER_HEADING, _WRITE_POINTER)],
    )
    if added:
        click.echo(
            "✓ Codex: wired AGENTS.md to load .spanweave/ context on start and "
            "capture decisions on session end."
        )
    else:
        click.echo("✓ Codex: AGENTS.md already has the Spanweave context + capture sections.")
    click.echo(
        "  Note: Codex has no native hooks — capture on end depends on the agent "
        "following the AGENTS.md instruction."
    )


def wire_cursor(repo_root: Path) -> None:
    """Create or update .cursorrules with Spanweave read + capture instructions."""
    _wire_rules_file(repo_root / ".cursorrules", "Cursor")


def wire_windsurf(repo_root: Path) -> None:
    """Create or update .windsurfrules with Spanweave read + capture instructions."""
    _wire_rules_file(repo_root / ".windsurfrules", "Windsurf")


def _wire_rules_file(rules_path: Path, tool_name: str) -> None:
    """Shared logic for cursor/windsurf rules-file wiring (read + write pointers)."""
    added = _ensure_sections(
        rules_path,
        [(_READ_POINTER_HEADING, _READ_POINTER), (_WRITE_POINTER_HEADING, _WRITE_POINTER)],
    )
    if added:
        click.echo(
            f"✓ {tool_name}: wired {rules_path.name} to load .spanweave/ context on "
            "start and capture decisions on session end."
        )
    else:
        click.echo(
            f"✓ {tool_name}: {rules_path.name} already has the Spanweave "
            "context + capture sections."
        )


__all__ = ["wire_claude_code", "wire_codex", "wire_cursor", "wire_windsurf"]
