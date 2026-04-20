import click


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """Atelier daemon scaffold. The FastAPI/SSE implementation lands in W16."""
    click.echo("Atelier daemon scaffold is installed. FastAPI/SSE implementation lands in W16.")


if __name__ == "__main__":
    main()

