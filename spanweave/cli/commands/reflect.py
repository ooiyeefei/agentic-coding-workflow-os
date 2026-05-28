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
    default=None,
    help=(
        "Model for reflection (benefits from reasoning). Defaults by hardware: "
        "gemma4:e4b on GPU, qwen2.5:1.5b on CPU-only."
    ),
)
@click.option(
    "--min-decisions",
    default=3,
    show_default=True,
    help="Minimum decisions needed to reflect.",
)
def reflect_command(repo: Path, model: str | None, min_decisions: int) -> None:
    """Synthesize lessons from accumulated decisions.

    Reads recent decisions and uses a local model to derive a higher-order
    insight. The reflection is staged to .spanweave/memory/pending/reflections/
    for review via `spanweave review`.
    """
    from spanweave.learning.ollama_client import OllamaNotAvailableError, default_model
    from spanweave.learning.reflector import (
        _gather_recent_decisions,  # pyright: ignore[reportPrivateUsage]
        reflect_on_decisions,
        stage_reflection,
    )

    repo_path = repo.resolve()
    if model is None:
        model = default_model()

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
        # An unavailable/slow local model is a user-environment state, not a
        # spanweave failure, so exit 0 (not 1). Print the exception's own
        # message: it distinguishes "not running" from "running but too slow".
        click.echo(str(exc), err=True)
        return

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
