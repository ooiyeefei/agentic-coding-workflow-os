from __future__ import annotations

from pathlib import Path

import click

from atelier.cli.formatters import build_help_epilog, echo_json, pushd
from atelier.session import ingest_transcript


@click.command(
    "ingest",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=("Extracted records are written to .atelier/memory/ as typed markdown records.",),
        examples=(
            "atelier ingest --from transcript.md --tool generic",
            "atelier ingest --from rollout.jsonl --tool codex --json",
        ),
    ),
)
@click.option(
    "--from",
    "source_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Transcript file to ingest.",
)
@click.option(
    "--tool",
    "source_tool",
    default="generic",
    show_default=True,
    help="Transcript source format: generic, codex, or claude-code.",
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .atelier workspace.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON.")
def ingest_command(source_path: Path, source_tool: str, repo: Path, json_output: bool) -> None:
    """Ingest a transcript into durable Atelier memory."""

    repo_path = repo.resolve()
    transcript_path = source_path.resolve()
    try:
        with pushd(repo_path):
            records = ingest_transcript(transcript_path, source_tool)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload = {
        "path": str(transcript_path),
        "tool": source_tool,
        "record_count": len(records),
        "records": [record.model_dump(mode="json") for record in records],
    }
    if json_output:
        echo_json(payload)
        return

    click.echo(f"Ingested {len(records)} memory record(s) from {transcript_path}")


__all__ = ["ingest_command"]
