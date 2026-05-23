"""Tool-specific wiring logic for `spanweave init --tool <name>`.

Each function wires auto-extraction hooks for a specific agent tool.
All operations are idempotent — running them twice does not break anything.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import click

_HOOK_COMMAND = "spanweave extract-latest --repo ."

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

    # Check if our command is already present anywhere in the nested hooks
    # arrays (idempotent). Each block carries its own "hooks" list.
    for block in stop_blocks:
        inner = block.get("hooks", []) if isinstance(block, dict) else []
        if any(h.get("command") == _HOOK_COMMAND for h in inner):
            click.echo(
                "✓ Claude Code Stop hook already wired. "
                "Decisions will be auto-extracted when sessions end."
            )
            return

    # Append our hook as a properly-shaped matcher block
    stop_blocks.append(
        {
            "matcher": "",
            "hooks": [{"type": "command", "command": _HOOK_COMMAND}],
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
