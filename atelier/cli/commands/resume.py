from __future__ import annotations

from pathlib import Path

import click

from atelier.cli.formatters import build_help_epilog, echo_json, pushd
from atelier.session import resume


@click.command(
    "resume",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Prints a paste-ready prompt to stdout so it can be piped into another tool.",
            "Use 'atelier run resume' for workflow gate approval; this command transfers context.",
        ),
        examples=(
            "atelier resume --agent claude-code --run run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "atelier resume --agent codex --run run_01ARZ3NDEKTSV4RRFFQ69G5FAV --json",
        ),
    ),
)
@click.option(
    "--agent",
    "target_agent",
    default="generic",
    show_default=True,
    help="Target agent format: claude-code, codex, or generic.",
)
@click.option("--run", "run_id", required=True, help="Run ID to resume.")
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .atelier workspace.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
def resume_command(target_agent: str, run_id: str, repo: Path, json_output: bool) -> None:
    """Generate a cross-tool resume prompt for an existing run."""

    repo_path = repo.resolve()
    try:
        with pushd(repo_path):
            prompt = resume(run_id, target_agent)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if json_output:
        echo_json(
            {
                "run_id": run_id,
                "agent": target_agent,
                "prompt": prompt,
            }
        )
        return

    click.echo(prompt, nl=False)


__all__ = ["resume_command"]
