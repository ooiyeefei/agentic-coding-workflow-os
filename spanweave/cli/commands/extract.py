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
            "spanweave extract --session session.jsonl --model gemma4:e4b",
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
    default=None,
    help=(
        "Ollama model for extraction. Defaults by hardware: gemma4:e4b on GPU, "
        "qwen2.5:1.5b on CPU-only. Override with any pulled model."
    ),
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .spanweave workspace.",
)
def extract_command(session_path: Path, model: str | None, repo: Path) -> None:
    """Extract decisions from a coding session transcript."""
    from spanweave.learning.extractor import OllamaNotAvailableError, extract_from_session
    from spanweave.learning.ollama_client import default_model

    repo_path = repo.resolve()
    transcript_path = session_path.resolve()
    if model is None:
        model = default_model()
        click.echo(f"Using model: {model} (auto-selected by hardware)", err=True)

    try:
        decisions = extract_from_session(
            transcript_path,
            model=model,
            repo_root=repo_path,
        )
    except OllamaNotAvailableError as exc:
        # An unavailable/slow local model is a user-environment state, not a
        # spanweave failure, so exit 0 (not 1) — exit 1 makes scripts/CI treat
        # it as a crash. Print the exception's own message: it distinguishes
        # "not running" (install/pull) from "running but too slow" (try a
        # smaller model) so the guidance is accurate either way.
        click.echo(str(exc), err=True)
        return
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    if not decisions:
        click.echo("No decisions extracted from session.")
        return

    click.echo(f"Extracted {len(decisions)} decision(s) from session.")
    click.echo("Pending decisions staged to .spanweave/memory/pending/decisions/")
    click.echo("Run `spanweave review` to confirm or dismiss them.")


__all__ = ["extract_command"]
