from pathlib import Path

import click

from .server import create_app


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .spanweave workspace.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Loopback host to bind for the local daemon.",
)
@click.option(
    "--port",
    default=8765,
    show_default=True,
    type=int,
    help="TCP port for the local daemon listener.",
)
@click.option(
    "--log-level",
    default="info",
    show_default=True,
    type=click.Choice(("critical", "error", "warning", "info", "debug"), case_sensitive=False),
    help="Uvicorn log level.",
)
def main(repo: Path, host: str, port: int, log_level: str) -> None:
    """Run the local Spanweave HTTP daemon."""

    import uvicorn

    app = create_app(repo_root=repo.resolve())
    uvicorn.run(app, host=host, port=port, log_level=log_level.lower())


if __name__ == "__main__":
    main()
