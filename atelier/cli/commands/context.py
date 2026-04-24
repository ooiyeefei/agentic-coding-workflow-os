from __future__ import annotations

from pathlib import Path

import click

from atelier.cli.formatters import build_help_epilog, echo_json, pushd
from atelier.compiler import estimate_tokens
from atelier.session import generate_context


@click.command(
    "context",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=("Generates standalone memory context; no run ID is required.",),
        examples=(
            "atelier context --for chatgpt --limit 4000",
            "atelier context --for gemini --limit 6000 --json",
        ),
    ),
)
@click.option(
    "--for",
    "target",
    default="generic",
    show_default=True,
    help="Destination tool or audience, for example chatgpt, gemini, cowork, or generic.",
)
@click.option(
    "--limit",
    "token_limit",
    default=4000,
    show_default=True,
    type=int,
    help="Maximum estimated token budget.",
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .atelier workspace.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
def context_command(target: str, token_limit: int, repo: Path, json_output: bool) -> None:
    """Generate standalone context from .atelier/memory."""

    repo_path = repo.resolve()
    try:
        with pushd(repo_path):
            context = generate_context(target, token_limit)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if json_output:
        echo_json(
            {
                "target": target,
                "token_limit": token_limit,
                "estimated_tokens": estimate_tokens(context),
                "context": context,
            }
        )
        return

    click.echo(context, nl=False)


__all__ = ["context_command"]
