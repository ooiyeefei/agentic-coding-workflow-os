from __future__ import annotations

import click

from atelier.cli.commands.run import get_repo_from_context, load_run_record_for_cli
from atelier.cli.formatters import (
    build_help_epilog,
    echo_json,
    render_key_values,
    render_stage_tree,
)


@click.command(
    "show",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "This reads the stored run metadata and stage tree under .atelier/runs/<run_id>/.",
        ),
        examples=(
            "atelier run show run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo .",
            "atelier run show run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo . --json",
        ),
    ),
)
@click.argument("run_id")
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
@click.pass_context
def show_command(ctx: click.Context, run_id: str, json_output: bool) -> None:
    """Show the stored run tree and current workflow state for a run."""

    repo_path = get_repo_from_context(ctx)
    record = load_run_record_for_cli(repo_path, run_id)

    if json_output:
        echo_json(record.to_payload())
        return

    click.echo(
        render_key_values(
            (
                ("Run", record.run_id),
                ("Issue", record.issue_ref or "-"),
                ("Workflow", record.workflow),
                ("Status", record.status),
                ("Current stage", record.current_stage or "-"),
                ("Path", str(record.run_path)),
            )
        )
    )
    if record.waiting_reason:
        click.echo(f"Waiting reason : {record.waiting_reason}")
    if record.last_transition:
        click.echo(f"Last transition: {record.last_transition}")
    if record.last_transition_reason:
        click.echo(f"Transition note: {record.last_transition_reason}")
    click.echo("")
    click.echo("Stages")
    click.echo(render_stage_tree([stage.to_payload() for stage in record.stages]))
