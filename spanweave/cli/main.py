from __future__ import annotations

import click

from spanweave import __version__
from spanweave.cli.commands.extract import extract_command
from spanweave.cli.commands.extract_latest import extract_latest_command
from spanweave.cli.commands.grep import grep_command
from spanweave.cli.commands.harvest import harvest_command
from spanweave.cli.commands.init import init_command
from spanweave.cli.commands.promote import promote_command
from spanweave.cli.commands.reflect import reflect_command
from spanweave.cli.commands.review import review_command
from spanweave.cli.commands.skill_feedback import skill_feedback_group
from spanweave.cli.formatters import build_help_epilog


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Spanweave is ambient cross-tool memory for AI coding agents. "
            "Decisions are captured to .spanweave/memory/ and auto-loaded by each tool "
            "via its convention file (CLAUDE.md, AGENTS.md, .cursorrules).",
            "Human-readable output is the default. Add --json to supported commands "
            "for CI and scripts.",
        ),
        examples=(
            "spanweave init --tool claude-code --repo .",
            "spanweave extract-latest --repo .",
            "spanweave review --repo .",
            "spanweave reflect --repo .",
            "spanweave promote decision_<id> --repo .",
            "spanweave grep 'pattern' --repo .",
            "spanweave skill-feedback derive --entry path/to/outcome.json",
        ),
    ),
    invoke_without_command=True,
)
@click.version_option(version=__version__, prog_name="spanweave")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Spanweave: ambient cross-tool memory for AI coding agents."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


main.add_command(init_command)
main.add_command(extract_command)
main.add_command(extract_latest_command)
main.add_command(reflect_command)
main.add_command(promote_command)
main.add_command(review_command)
main.add_command(grep_command)
main.add_command(harvest_command)
main.add_command(skill_feedback_group)
