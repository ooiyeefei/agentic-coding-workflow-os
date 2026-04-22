from __future__ import annotations

from pathlib import Path

import click

from atelier.cli.formatters import build_help_epilog, echo_json


@click.command(
    "cleanup",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Cleanup prompts before removing worktrees unless you pass --yes.",
        ),
        examples=(
            "atelier cleanup run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo .",
            "atelier cleanup run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo . --yes --json",
        ),
    ),
)
@click.argument("run_id")
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root where the run worktree exists.",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip the interactive confirmation prompt.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
def cleanup_command(run_id: str, repo: Path, yes: bool, json_output: bool) -> None:
    """Remove worktrees associated with a run after confirmation."""

    from atelier.git.cleanup import cleanup_run_worktrees
    from atelier.git.errors import WorktreeError

    repo_path = repo.resolve()

    if not yes:
        click.confirm(f"Remove worktrees for run {run_id}?", abort=True)

    try:
        removed = cleanup_run_worktrees(run_id, confirm=True, repo_root=repo_path)
    except (ValueError, WorktreeError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload = {
        "run_id": run_id,
        "removed": [str(path) for path in removed],
        "removed_count": len(removed),
        "repo": str(repo_path),
    }

    if json_output:
        echo_json(payload)
        return

    if removed:
        click.echo(f"Removed {len(removed)} worktree(s) for {run_id}")
        for path in removed:
            click.echo(f"- {path}")
        return

    click.echo(f"No worktrees found for {run_id}")
