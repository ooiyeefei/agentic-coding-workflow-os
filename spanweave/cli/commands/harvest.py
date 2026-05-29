"""CLI command: spanweave harvest — import coding agents' native memory.

Reads each coding agent's own memory store (Claude Code's typed records, Codex's
prose summaries) and imports it into the shared ``.spanweave/memory/`` layer,
tagged with a ``source: native-<tool>`` provenance field so every tool can build
on what the others remembered.
"""

from __future__ import annotations

from pathlib import Path

import click

from spanweave.cli.formatters import build_help_epilog
from spanweave.harvest import SUPPORTED_TOOLS, available_tools, harvest_tool


@click.command(
    "harvest",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Reads each tool's NATIVE memory: Claude Code's typed records under "
            "~/.claude/projects/<encoded-cwd>/memory/, Codex's prose summaries "
            "under ~/.codex/memories/.",
            "Records are staged to .spanweave/memory/pending/ with "
            "source: native-claude / native-codex; run `spanweave review` next.",
            "Repeated runs are idempotent — already-imported memory is skipped.",
        ),
        examples=(
            "spanweave harvest --repo .",
            "spanweave harvest --tool claude-code --repo .",
            "spanweave harvest -t claude-code -t codex --repo .",
        ),
    ),
)
@click.option(
    "--tool",
    "-t",
    "tools",
    type=click.Choice(SUPPORTED_TOOLS),
    multiple=True,
    help="Tool whose native memory to harvest (repeatable). Defaults to all available.",
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .spanweave workspace.",
)
def harvest_command(tools: tuple[str, ...], repo: Path) -> None:
    """Import native memory from coding agents into .spanweave/memory/pending/."""
    repo_path = repo.resolve()

    selected = list(tools) if tools else available_tools(repo_path)

    if not selected:
        click.echo(
            "No native memory found for any supported tool "
            f"({', '.join(SUPPORTED_TOOLS)}). Nothing to harvest."
        )
        return

    pending_dir = repo_path / ".spanweave" / "memory" / "pending"
    total = 0
    for tool in selected:
        result = harvest_tool(tool, repo_path)
        total += result.count
        if not result.store_present:
            click.echo(f"No {tool} native memory found — skipped.")
        else:
            click.echo(
                f"Harvested {result.count} record(s) from {tool} native memory "
                f"→ {pending_dir}"
            )

    click.echo(f"Done. {total} record(s) staged for review in {pending_dir}.")
    if total:
        click.echo("Run `spanweave review` to confirm or dismiss them.")


__all__ = ["harvest_command"]
