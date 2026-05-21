from __future__ import annotations

from pathlib import Path

import click

from spanweave.adapters import detect_active_adapter
from spanweave.cli.formatters import build_help_epilog, echo_json, pushd
from spanweave.session import resume


@click.command(
    "resume",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Prints a paste-ready prompt to stdout so it can be piped into another tool.",
            "Use 'spanweave run resume' for workflow gate approval; "
            "this command transfers context.",
            "If --agent is omitted, the tool is auto-detected from repo markers "
            "(.claude/, AGENTS.md, etc.).",
        ),
        examples=(
            "spanweave resume --run run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "spanweave resume --agent claude-code --run run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "spanweave resume --agent codex --run run_01ARZ3NDEKTSV4RRFFQ69G5FAV --json",
        ),
    ),
)
@click.option(
    "--agent",
    "target_agent",
    default=None,
    help="Target agent format: claude-code, codex, or generic. Auto-detected if omitted.",
)
@click.option("--run", "run_id", required=True, help="Run ID to resume.")
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .spanweave workspace.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
def resume_command(
    target_agent: str | None, run_id: str, repo: Path, json_output: bool
) -> None:
    """Generate a cross-tool resume prompt for an existing run."""

    repo_path = repo.resolve()

    resolved_agent = target_agent
    if resolved_agent is None:
        adapter = detect_active_adapter(repo_path)
        if adapter is None:
            raise click.ClickException(
                "Could not auto-detect agent tool. "
                "Pass --agent explicitly (claude-code, codex, generic)."
            )
        resolved_agent = adapter.tool_name

    try:
        with pushd(repo_path):
            prompt = resume(run_id, resolved_agent)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if json_output:
        echo_json(
            {
                "run_id": run_id,
                "agent": resolved_agent,
                "prompt": prompt,
            }
        )
        return

    click.echo(prompt, nl=False)


__all__ = ["resume_command"]
