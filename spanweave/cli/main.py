from __future__ import annotations

import click

from spanweave import __version__
from spanweave.cli.commands.cleanup import cleanup_command
from spanweave.cli.commands.context import context_command
from spanweave.cli.commands.daemon import daemon_group
from spanweave.cli.commands.extract import extract_command
from spanweave.cli.commands.extract_latest import extract_latest_command
from spanweave.cli.commands.grep import grep_command
from spanweave.cli.commands.ingest import ingest_command
from spanweave.cli.commands.init import init_command
from spanweave.cli.commands.promote import promote_command
from spanweave.cli.commands.prompt import prompt_command
from spanweave.cli.commands.reflect import reflect_command
from spanweave.cli.commands.resume import resume_command
from spanweave.cli.commands.review import review_command
from spanweave.cli.commands.run import run_command
from spanweave.cli.commands.skill_feedback import skill_feedback_group
from spanweave.cli.formatters import build_help_epilog


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Human-readable output is the default. Add --json to supported commands "
            "for CI and scripts.",
        ),
        examples=(
            "spanweave init --repo .",
            "spanweave run --issue 42 --repo .",
            "spanweave run list --repo . --json",
            "spanweave run show run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo .",
            "spanweave cleanup run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo .",
            "spanweave resume --agent claude-code --run run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "spanweave prompt --role coder --agent codex --run run_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            "spanweave context --for chatgpt --limit 4000",
            "spanweave ingest --from transcript.md --tool generic",
            "spanweave daemon status --repo .",
            "spanweave grep 'issue #42' --repo .",
            "spanweave skill_feedback derive --entry path/to/outcome.json",
        ),
    ),
    invoke_without_command=True,
)
@click.version_option(version=__version__, prog_name="spanweave")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Spanweave control plane for initializing a workspace, starting runs, and inspecting state."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


main.add_command(init_command)
main.add_command(run_command)
main.add_command(cleanup_command)
main.add_command(resume_command)
main.add_command(prompt_command)
main.add_command(context_command)
main.add_command(ingest_command)
main.add_command(extract_command)
main.add_command(extract_latest_command)
main.add_command(reflect_command)
main.add_command(promote_command)
main.add_command(review_command)
main.add_command(daemon_group)
main.add_command(grep_command)
main.add_command(skill_feedback_group)
