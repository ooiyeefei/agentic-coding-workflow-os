from __future__ import annotations

import click

from atelier.cli.commands.run import get_repo_from_context, list_run_records_for_cli
from atelier.cli.formatters import build_help_epilog, echo_json, render_table


@click.command(
    "list",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Results are ordered newest-first based on the run directory names "
            "stored under .atelier/runs/.",
        ),
        examples=(
            "atelier run list --repo .",
            "atelier run list --repo . --json",
        ),
    ),
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
@click.pass_context
def list_command(ctx: click.Context, json_output: bool) -> None:
    """List recorded workflow runs and their current status."""

    repo_path = get_repo_from_context(ctx)
    records = list_run_records_for_cli(repo_path)

    if json_output:
        echo_json([record.to_payload() for record in records])
        return

    if not records:
        click.echo("No runs found.")
        return

    rows = [
        (
            record.run_id,
            record.status,
            record.current_stage or "-",
            record.issue_ref or "-",
        )
        for record in records
    ]
    click.echo(render_table(("RUN ID", "STATUS", "CURRENT STAGE", "ISSUE"), rows))
