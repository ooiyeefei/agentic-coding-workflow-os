import click

from atelier import __version__


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.version_option(version=__version__, prog_name="atelier")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Atelier CLI scaffold. Workflow commands arrive in later worktrees."""
    if ctx.invoked_subcommand is None:
        click.echo(
            "Atelier CLI scaffold is installed. "
            "Use --help to inspect the placeholder entrypoint."
        )


@main.command("about")
def about_command() -> None:
    """Show the scaffold status."""
    click.echo(
        "Atelier package foundation is ready. "
        "Workflow, daemon, and personas land in later worktrees."
    )


@main.command("daemon")
def daemon_command() -> None:
    """Show the daemon placeholder."""
    click.echo("Atelier daemon placeholder. HTTP/SSE support lands in W16.")
