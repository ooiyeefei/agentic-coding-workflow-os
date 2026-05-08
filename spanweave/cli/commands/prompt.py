from __future__ import annotations

from pathlib import Path

import click

from spanweave.cli.formatters import build_help_epilog, echo_json, pushd
from spanweave.session import generate_prompt


@click.command(
    "prompt",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=("Prints a fresh role-specific prompt to stdout for copy/paste or piping.",),
        examples=(
            "spanweave prompt --role coder --agent codex --run run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "spanweave prompt --role reviewer --agent claude-code "
            "--run run_01ARZ3NDEKTSV4RRFFQ69G5FAV --json",
        ),
    ),
)
@click.option(
    "--role",
    default="coder",
    show_default=True,
    help="Role prompt to generate: coder or reviewer.",
)
@click.option(
    "--agent",
    "target_agent",
    default="generic",
    show_default=True,
    help="Target agent format: claude-code, codex, or generic.",
)
@click.option("--run", "run_id", required=True, help="Run ID to prompt from.")
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .spanweave workspace.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
def prompt_command(
    role: str,
    target_agent: str,
    run_id: str,
    repo: Path,
    json_output: bool,
) -> None:
    """Generate a role-specific prompt for a run."""

    repo_path = repo.resolve()
    try:
        with pushd(repo_path):
            prompt = generate_prompt(run_id, role, target_agent)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if json_output:
        echo_json(
            {
                "run_id": run_id,
                "role": role,
                "agent": target_agent,
                "prompt": prompt,
            }
        )
        return

    click.echo(prompt, nl=False)


__all__ = ["prompt_command"]
