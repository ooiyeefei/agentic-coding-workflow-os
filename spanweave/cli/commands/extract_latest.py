"""CLI command: spanweave extract-latest — extract from the most recent session transcript.

Designed to be called from tool hooks (e.g. Claude Code Stop hook).
Finds the newest .jsonl in ~/.claude/projects/<encoded-cwd>/ and runs extraction.
"""

from __future__ import annotations

from pathlib import Path

import click

from spanweave.cli.formatters import build_help_epilog
from spanweave.learning.ollama_client import ollama_available


def _claude_project_dir(repo_root: Path) -> Path:
    """Compute the Claude Code project session directory.

    Claude Code encodes the project path by replacing / with - as the directory name
    under ~/.claude/projects/. For example:
        /home/fei/project -> -home-fei-project
    """
    resolved = str(repo_root.resolve())
    encoded = resolved.replace("/", "-")
    return Path.home() / ".claude" / "projects" / encoded


def _find_latest_session(repo_root: Path) -> Path | None:
    """Find the most recent .jsonl session file for the given repo.

    Searches ~/.claude/projects/<encoded-cwd>/ for .jsonl files
    and returns the one with the most recent modification time.
    """
    project_dir = _claude_project_dir(repo_root)
    if not project_dir.exists():
        return None

    jsonl_files = list(project_dir.glob("*.jsonl"))
    if not jsonl_files:
        return None

    # Sort by modification time, newest first
    jsonl_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return jsonl_files[0]


@click.command(
    "extract-latest",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Finds the newest .jsonl session in ~/.claude/projects/<encoded-cwd>/.",
            "Designed to be called from tool hooks (e.g. Claude Code Stop hook).",
        ),
        examples=(
            "spanweave extract-latest --repo .",
            "spanweave extract-latest --repo /path/to/project",
        ),
    ),
)
@click.option(
    "--repo",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Repository root that contains the .spanweave workspace.",
)
@click.option(
    "--model",
    default="gemma4:e4b",
    show_default=True,
    help="Ollama model for extraction.",
)
def extract_latest_command(repo: Path, model: str) -> None:
    """Extract decisions from the most recent session transcript.

    Finds the newest .jsonl file in ~/.claude/projects/<encoded-cwd>/
    and runs extraction on it. Designed to be called from tool hooks.
    """
    from spanweave.learning.extractor import OllamaNotAvailableError, extract_from_session

    repo_path = repo.resolve()
    session_path = _find_latest_session(repo_path)

    if session_path is None:
        raise click.ClickException(
            f"No session files found for {repo_path}. "
            f"Expected .jsonl files in {_claude_project_dir(repo_path)}"
        )

    # This command runs as a tool hook (Claude Code Stop hook). When the
    # optional local model server isn't running, fail fast and quietly:
    # a single calm stderr line and exit 0. Erroring here would surface as a
    # scary "Stop hook error" on every session end where Ollama is absent.
    if not ollama_available():
        click.echo(
            "spanweave: Ollama not running; skipping auto-extraction.",
            err=True,
        )
        return

    try:
        decisions = extract_from_session(
            session_path,
            model=model,
            repo_root=repo_path,
        )
    except OllamaNotAvailableError:
        # Backstop: the probe passed but the server died mid-run OR the model
        # was too slow to respond (OllamaTimeoutError subclasses this). Same
        # quiet exit-0 no-op — a hook must never exit non-zero for an
        # unavailable/slow optional dependency. Message stays neutral because
        # the cause may be "down" or "too slow".
        click.echo(
            "spanweave: skipping auto-extraction "
            "(Ollama unavailable or model too slow).",
            err=True,
        )
        return
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    if not decisions:
        click.echo("No decisions extracted from latest session.")
        return

    click.echo(
        f"Extracted {len(decisions)} decision(s) "
        f"→ .spanweave/memory/pending/decisions/"
    )


__all__ = ["extract_latest_command"]
