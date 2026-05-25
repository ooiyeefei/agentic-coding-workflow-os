"""CLI command: spanweave extract-latest — extract from the most recent session transcript.

Designed to be called from tool hooks (e.g. Claude Code Stop hook).
Finds the newest .jsonl in ~/.claude/projects/<encoded-cwd>/ and runs extraction.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click

from spanweave.cli.formatters import build_help_epilog
from spanweave.learning.ollama_client import EXTRACTION_MODEL, ollama_available

# Hook path bounds work to the last N chunks so a huge/compacted transcript
# can't trigger a multi-hour run. The hook fires every session end and dedup
# handles overlap, so the most recent window is what each run needs.
DEFAULT_RECENT_CHUNKS = 15


def _lock_path(repo_root: Path) -> Path:
    return repo_root / ".spanweave" / "daemon" / "extract-latest.lock"


def _lock_is_live(lock_path: Path) -> bool:
    """True if the lockfile names a still-running process."""
    try:
        pid = int(lock_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False  # unreadable / garbage PID -> treat as stale
    try:
        os.kill(pid, 0)  # signal 0 just probes existence
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by another user
    except OSError:
        return False
    return True


def _acquire_lock(lock_path: Path) -> bool:
    """Atomically acquire a single-flight PID lock; steal it if stale.

    Returns True if this process now holds the lock. A live holder -> False
    (so a second worker no-ops); a stale holder (dead/garbage PID) is stolen.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        if _lock_is_live(lock_path):
            return False
        try:
            lock_path.unlink()
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except (OSError, FileExistsError):
            return False  # lost a race to another worker
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))
    return True


def _release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except OSError:
        pass


def _spawn_detached(repo_root: Path, recent: int) -> None:
    """Launch the (slow) extraction as a detached background process.

    Returns immediately; ``start_new_session=True`` detaches the child so it
    survives the Stop hook returning — that's what keeps the hook under its
    timeout while gemma4:e4b takes its time on CPU. Child output goes to a log
    under .spanweave/daemon/ for inspection.
    """
    log_dir = repo_root / ".spanweave" / "daemon"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = (log_dir / "extract-latest.log").open("ab")
    try:
        subprocess.Popen(  # noqa: S603
            [sys.argv[0], "extract-latest", "--repo", str(repo_root), "--recent", str(recent)],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            cwd=str(repo_root),
        )
    finally:
        log.close()


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
    default=None,
    help=(
        "Ollama model for extraction. Defaults to gemma4:e4b (quality); "
        "override with any pulled model, e.g. --model qwen2.5:1.5b for speed."
    ),
)
@click.option(
    "--recent",
    default=DEFAULT_RECENT_CHUNKS,
    show_default=True,
    help="Extract only the last N conversation chunks (bounds work on huge sessions).",
)
@click.option(
    "--detach",
    is_flag=True,
    default=False,
    help=(
        "Launch extraction as a detached background process and return "
        "immediately. Used by the Stop hook so a slow model never trips the "
        "hook timeout."
    ),
)
def extract_latest_command(repo: Path, model: str | None, recent: int, detach: bool) -> None:
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

    # Launcher mode (the Stop hook): spawn a detached worker and return in <1s,
    # so a slow model (gemma4:e4b on CPU) never blocks the hook past its timeout.
    if detach:
        _spawn_detached(repo_path, recent)
        return

    # Worker mode. Default to the quality model (extraction runs detached, so
    # latency is decoupled from any interactive wait).
    if model is None:
        model = EXTRACTION_MODEL

    # Single-flight: if a live extraction already holds the lock, no-op quietly
    # so rapid session-ends don't pile up parallel CPU-bound Gemma runs.
    lock_path = _lock_path(repo_path)
    if not _acquire_lock(lock_path):
        return

    try:
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
                recent_chunks=recent,
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
    finally:
        _release_lock(lock_path)


__all__ = ["extract_latest_command"]
