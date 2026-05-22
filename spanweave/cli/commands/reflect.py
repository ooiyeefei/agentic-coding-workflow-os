"""CLI command: spanweave reflect — synthesize lessons from accumulated decisions."""

from __future__ import annotations

from pathlib import Path

import click

from spanweave.cli.formatters import build_help_epilog


@click.command(
    "reflect",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Requires Ollama running locally with the specified model pulled.",
            "Reflections are staged to .spanweave/memory/pending/reflections/.",
            "Uses thinking mode for deeper reasoning about patterns.",
        ),
        examples=(
            "spanweave reflect --repo .",
            "spanweave reflect --model gemma4:e4b",
            "spanweave reflect --min-decisions 5",
        ),
    ),
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .spanweave workspace.",
)
@click.option(
    "--model",
    default="gemma4:e4b",
    show_default=True,
    help="Model for reflection (benefits from thinking/reasoning).",
)
@click.option(
    "--min-decisions",
    default=3,
    show_default=True,
    help="Minimum decisions needed to reflect.",
)
def reflect_command(repo: Path, model: str, min_decisions: int) -> None:
    """Synthesize lessons from accumulated decisions.

    Reads recent decisions and uses a local model to derive a higher-order
    insight. The reflection is staged to .spanweave/memory/pending/reflections/
    for review via `spanweave review`.
    """
    from spanweave.learning.ollama_client import OllamaNotAvailableError
    from spanweave.learning.reflector import (
        _gather_recent_decisions,
        reflect_on_decisions,
        stage_reflection,
    )

    repo_path = repo.resolve()

    # Check how many decisions are available before calling the model
    decisions = _gather_recent_decisions(repo_path, max_count=20)
    click.echo(f"Reading {len(decisions)} recent decisions...")

    if len(decisions) < min_decisions:
        click.echo(
            f"Not enough decisions to reflect on (need at least {min_decisions})."
        )
        return

    click.echo(f"Reflecting with {model} (thinking mode enabled)...")

    try:
        reflection = reflect_on_decisions(
            repo_root=repo_path,
            model=model,
            min_decisions=min_decisions,
        )
    except OllamaNotAvailableError as exc:
        raise click.ClickException(str(exc)) from exc

    if reflection is None:
        click.echo("Could not synthesize a reflection from the available decisions.")
        return

    # Stage the reflection
    staged_path = stage_reflection(reflection, repo_root=repo_path)

    # Display the result
    lesson = reflection.get("lesson", "")
    supporting = reflection.get("supporting_decisions", [])
    confidence = reflection.get("confidence", 0.0)

    click.echo("")
    click.echo("Reflection synthesized:")
    click.echo(f'  Lesson: "{lesson}"')
    if supporting:
        click.echo(f"  Supporting: {', '.join(supporting)}")
    click.echo(f"  Confidence: {confidence:.2f}")
    click.echo("")
    click.echo(f"Staged to: {staged_path.relative_to(repo_path)}")
    click.echo("Review with: spanweave review")


__all__ = ["reflect_command"]
