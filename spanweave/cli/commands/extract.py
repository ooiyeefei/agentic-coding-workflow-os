"""CLI command: spanweave extract — extract decisions from a session transcript."""

from __future__ import annotations

from pathlib import Path

import click

from spanweave.cli.formatters import build_help_epilog


@click.command(
    "extract",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Requires Ollama running locally with the specified model pulled.",
            "Extracted decisions are staged to .spanweave/memory/pending/decisions/.",
        ),
        examples=(
            "spanweave extract --session transcript.jsonl",
            "spanweave extract --session session.jsonl --model qwen2.5:1.5b",
            "spanweave extract --session session.jsonl --repo /path/to/project",
        ),
    ),
)
@click.option(
    "--session",
    "session_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to session JSONL file.",
)
@click.option(
    "--model",
    default="qwen2.5:1.5b",
    show_default=True,
    help="Ollama model for extraction.",
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .spanweave workspace.",
)
def extract_command(session_path: Path, model: str, repo: Path) -> None:
    """Extract decisions from a coding session transcript."""
    from spanweave.learning.extractor import OllamaNotAvailableError, extract_from_session

    repo_path = repo.resolve()
    transcript_path = session_path.resolve()

    try:
        decisions = extract_from_session(
            transcript_path,
            model=model,
            repo_root=repo_path,
        )
    except OllamaNotAvailableError as exc:
        raise click.ClickException(str(exc)) from exc
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    if not decisions:
        click.echo("No decisions extracted from session.")
        return

    click.echo(f"Extracted {len(decisions)} decision(s) from session.")
    click.echo("Pending decisions staged to .spanweave/memory/pending/decisions/")
    click.echo("Run `spanweave review` to confirm or dismiss them.")


__all__ = ["extract_command"]
