from __future__ import annotations

import click

from atelier import __version__
from atelier.cli.commands.cleanup import cleanup_command
from atelier.cli.commands.daemon import daemon_group
from atelier.cli.commands.grep import grep_command
from atelier.cli.commands.init import init_command
from atelier.cli.commands.run import run_command
from atelier.cli.formatters import build_help_epilog


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Human-readable output is the default. Add --json to supported commands "
            "for CI and scripts.",
        ),
        examples=(
            "atelier init --repo .",
            "atelier run --issue 42 --repo .",
            "atelier run list --repo . --json",
            "atelier run show run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo .",
            "atelier cleanup run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo .",
            "atelier daemon status --repo .",
            "atelier grep 'issue #42' --repo .",
        ),
    ),
    invoke_without_command=True,
)
@click.version_option(version=__version__, prog_name="atelier")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Atelier control plane for initializing a workspace, starting runs, and inspecting state."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


main.add_command(init_command)
main.add_command(run_command)
main.add_command(cleanup_command)
main.add_command(daemon_group)
main.add_command(grep_command)
