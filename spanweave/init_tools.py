"""Tool-specific wiring logic for `spanweave init --tool <name>`.

Each function wires auto-extraction hooks for a specific agent tool.
All operations are idempotent — running them twice does not break anything.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import click

_EXTRACT_ARGS = "extract-latest --repo ."


def _resolve_hook_command(repo_root: Path) -> str:
    """Resolve a hook command that works in a bare /bin/sh (no venv, no uv).

    Claude Code fires Stop hooks in a minimal shell where neither the venv nor
    `uv` is on PATH, so a plain `spanweave ...` (or `uv run spanweave ...`)
    command fails with "not found". When a repo-local virtualenv is present
    (dev / uv-project install), point the hook at its entry-point binary via a
    repo-relative path — hooks run with cwd = project root (the same guarantee
    `--repo .` already relies on). Otherwise assume a global install on PATH.

    We deliberately avoid ``shutil.which("spanweave")``: when this runs inside
    ``uv run spanweave init``, the venv's binary is already on the process PATH,
    so ``which`` would falsely report a global install.
    """
    venv_bin = repo_root / ".venv" / "bin" / "spanweave"
    if venv_bin.exists():
        return f".venv/bin/spanweave {_EXTRACT_ARGS}"
    return f"spanweave {_EXTRACT_ARGS}"

_CODEX_SECTION = """\

## Session end protocol

Before ending your session, run:
```bash
spanweave extract-latest --repo .
```
This captures decisions from this session into `.spanweave/memory/pending/`.
"""

_RULES_CONTENT = """\
## Spanweave context

Before responding to substantive questions, check .spanweave/runs/ for context from prior sessions.

Before ending your session, run: spanweave extract-latest --repo .
"""


def wire_claude_code(repo_root: Path) -> None:
    """Wire a Claude Code Stop hook that runs extract-latest on session end.

    Creates or updates .claude/settings.json with a hooks.Stop entry.
    Preserves all existing content and is idempotent.
    """
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

    # Ensure hooks.Stop structure. Claude Code expects each Stop entry to be a
    # matcher-block: {"matcher": "", "hooks": [{"type": "command", ...}]}. The
    # matcher is empty because Stop has no tool to match against.
    if "hooks" not in data:
        data["hooks"] = {}
    hooks = cast(dict[str, Any], data["hooks"])
    if "Stop" not in hooks:
        hooks["Stop"] = []
    stop_blocks = cast(list[dict[str, Any]], hooks["Stop"])

    hook_command = _resolve_hook_command(repo_root)

    # Find any existing spanweave extract-latest hook, matching on the args
    # suffix so we recognize it regardless of how spanweave is invoked
    # (plain `spanweave`, `.venv/bin/spanweave`, `uv run spanweave`). This makes
    # the wiring idempotent AND self-healing: a stale/broken invocation from an
    # earlier version is upgraded in place rather than duplicated.
    for block in stop_blocks:
        if not isinstance(block, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
            continue
        for inner_hook in block.get("hooks", []):
            command = inner_hook.get("command", "")
            if not command.endswith(_EXTRACT_ARGS):
                continue
            if command == hook_command:
                click.echo(
                    "✓ Claude Code Stop hook already wired. "
                    "Decisions will be auto-extracted when sessions end."
                )
                return
            # Stale invocation (e.g. the pre-fix bare `spanweave` that fails in
            # the bare hook shell) — upgrade it in place.
            inner_hook["command"] = hook_command
            settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            click.echo(
                "✓ Claude Code Stop hook updated to a shell-resilient command "
                f"({hook_command})."
            )
            return

    # Append our hook as a properly-shaped matcher block
    stop_blocks.append(
        {
            "matcher": "",
            "hooks": [{"type": "command", "command": hook_command}],
        }
    )

    # Write back preserving formatting
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    click.echo(
        "✓ Claude Code Stop hook wired. "
        "Decisions will be auto-extracted when sessions end."
    )


def wire_codex(repo_root: Path) -> None:
    """Add extraction instruction to AGENTS.md for Codex.

    Appends a 'Session end protocol' section if not already present.
    Creates AGENTS.md if it doesn't exist.
    """
    agents_path = repo_root / "AGENTS.md"

    if agents_path.exists():
        content = agents_path.read_text(encoding="utf-8")
    else:
        content = "# Development Guidelines\n"

    # Check if already present (idempotent)
    if "spanweave extract-latest --repo ." in content:
        click.echo(
            "✓ Codex instruction already present in AGENTS.md. "
            "The agent will be prompted to extract on session end."
        )
        return

    # Append the section
    content = content.rstrip() + "\n" + _CODEX_SECTION
    agents_path.write_text(content, encoding="utf-8")

    click.echo(
        "✓ Codex instruction added to AGENTS.md. "
        "The agent will be prompted to extract on session end."
    )
    click.echo(
        "  Note: Codex has no native hooks — "
        "extraction depends on the agent following the instruction."
    )


def wire_cursor(repo_root: Path) -> None:
    """Create or update .cursorrules with Spanweave context and extraction instruction."""
    rules_path = repo_root / ".cursorrules"
    _wire_rules_file(rules_path, "Cursor")


def wire_windsurf(repo_root: Path) -> None:
    """Create or update .windsurfrules with Spanweave context and extraction instruction."""
    rules_path = repo_root / ".windsurfrules"
    _wire_rules_file(rules_path, "Windsurf")


def _wire_rules_file(rules_path: Path, tool_name: str) -> None:
    """Shared logic for cursor/windsurf rules file wiring."""
    if rules_path.exists():
        content = rules_path.read_text(encoding="utf-8")
    else:
        content = ""

    # Check if already present (idempotent)
    if "spanweave extract-latest --repo ." in content:
        click.echo(
            f"✓ {tool_name} rules already contain Spanweave instructions. "
            "Agent will be prompted to read context and extract on session end."
        )
        return

    # Append our content
    if content and not content.endswith("\n"):
        content += "\n"
    content += "\n" + _RULES_CONTENT
    rules_path.write_text(content, encoding="utf-8")

    click.echo(
        f"✓ {tool_name} rules updated. "
        "Agent will be prompted to read context and extract on session end."
    )


__all__ = ["wire_claude_code", "wire_codex", "wire_cursor", "wire_windsurf"]
