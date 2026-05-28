from __future__ import annotations

from pathlib import Path

import click

from spanweave.cli.formatters import build_help_epilog, echo_json
from spanweave.sharing import default_sharing_yaml

_README_CONTENT = (
    "# Spanweave Workspace\n\n"
    "This directory stores ambient memory captured from your AI coding sessions.\n"
    "Decisions live as markdown files under `memory/` and are auto-loaded by each\n"
    "agent tool on session start via its convention file (CLAUDE.md, AGENTS.md, .cursorrules).\n"
)


def _ensure_directory(path: Path) -> bool:
    if path.exists():
        return False
    path.mkdir(parents=True, exist_ok=True)
    return True


def _write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


@click.command(
    "init",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "This command is idempotent and does not overwrite existing workspace files.",
            "Use --tool to wire auto-extraction hooks for specific agent tools.",
        ),
        examples=(
            "spanweave init --repo .",
            "spanweave init --repo /path/to/repo --json",
            "spanweave init --tool claude-code --repo .",
            "spanweave init --tool codex --tool cursor --repo .",
        ),
    ),
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root where .spanweave/ should be scaffolded.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
@click.option(
    "--tool",
    "tools",
    multiple=True,
    type=click.Choice(["claude-code", "codex", "cursor", "windsurf"], case_sensitive=False),
    help="Wire auto-extraction hooks for specific tools.",
)
def init_command(repo: Path, json_output: bool, tools: tuple[str, ...]) -> None:
    """Scaffold the local .spanweave workspace in the target repository."""

    repo_path = repo.resolve()
    spanweave_root = repo_path / ".spanweave"

    created_dirs: list[str] = []
    created_files: list[str] = []

    for directory in (
        spanweave_root,
        spanweave_root / "memory" / "decisions",
        spanweave_root / "memory" / "findings",
        spanweave_root / "memory" / "rejected_alternatives",
        spanweave_root / "memory" / "skill_outcomes",
        spanweave_root / "memory" / "pending" / "decisions",
        spanweave_root / "memory" / "pending" / "reflections",
        spanweave_root / "memory" / "private" / "decisions",
        spanweave_root / "memory" / "private" / "findings",
        spanweave_root / "memory" / "private" / "reflections",
        spanweave_root / "memory" / "shared" / "decisions",
        spanweave_root / "memory" / "shared" / "findings",
    ):
        if _ensure_directory(directory):
            created_dirs.append(str(directory.relative_to(repo_path)))

    if _write_if_missing(spanweave_root / "README.md", _README_CONTENT):
        created_files.append(".spanweave/README.md")

    if _write_if_missing(spanweave_root / "sharing.yaml", default_sharing_yaml()):
        created_files.append(".spanweave/sharing.yaml")

    payload = {
        "repo": str(repo_path),
        "spanweave_root": str(spanweave_root),
        "created_dirs": created_dirs,
        "created_files": created_files,
        "changed": bool(created_dirs or created_files),
    }

    if json_output:
        echo_json(payload)
        return

    if payload["changed"]:
        click.echo(f"Initialized Spanweave workspace at {spanweave_root}")
        for path in [*created_dirs, *created_files]:
            click.echo(f"- {path}")
    else:
        click.echo(f"Spanweave workspace already initialized at {spanweave_root}")

    # Wire tool-specific hooks if requested
    if tools:
        from spanweave.init_tools import wire_claude_code, wire_codex, wire_cursor, wire_windsurf

        tool_handlers = {
            "claude-code": wire_claude_code,
            "codex": wire_codex,
            "cursor": wire_cursor,
            "windsurf": wire_windsurf,
        }
        for tool in tools:
            handler = tool_handlers[tool.lower()]
            handler(repo_path)
