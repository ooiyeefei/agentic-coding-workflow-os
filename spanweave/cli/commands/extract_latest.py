"""CLI command: spanweave extract-latest — extract from the most recent session transcript.

Designed to be called from tool hooks (e.g. the Claude Code SessionEnd hook).

Multi-source: the same chunk -> local-LLM -> stage pipeline runs over either
Claude Code (``~/.claude/projects/<encoded-cwd>/*.jsonl``) or Codex
(``~/.codex/sessions/**/rollout-*.jsonl`` matched by recorded cwd), behind the
``spanweave.sources`` adapter abstraction. ``--tool`` selects sources
explicitly (repeatable); the default auto mode processes every installed source
that has a session for this repo.

Each source tracks its own byte-offset watermark
(``extract-latest-<tool>.watermark``) so Claude's and Codex's progress never
interfere.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import click

from spanweave.cli.formatters import build_help_epilog
from spanweave.learning.ollama_client import EXTRACTION_MODEL, ollama_available
from spanweave.sources import SessionSource, all_sources, get_source

# Hook path used to bound work to the last N chunks (legacy recency window).
# Still exposed via the explicit ``--recent N`` override for debugging /
# backfill, but the default SessionEnd-hook path now uses the byte-offset
# watermark so successive fires don't re-process overlapping windows.
DEFAULT_RECENT_CHUNKS = 15

logger = logging.getLogger(__name__)


def _lock_path(repo_root: Path) -> Path:
    return repo_root / ".spanweave" / "daemon" / "extract-latest.lock"


def _watermark_path(repo_root: Path, source_name: str = "claude-code") -> Path:
    """Where the byte-offset watermark for ``source_name`` in this repo lives.

    Per-source watermark files (``extract-latest-<tool>.watermark``) keep each
    tool's offset independent: extracting Codex never disturbs Claude's progress
    and vice versa. ``source_name`` defaults to ``"claude-code"`` so the helper
    (and any legacy caller / test) keeps the historical single-tool path.
    """
    return (
        repo_root
        / ".spanweave"
        / "daemon"
        / f"extract-latest-{source_name}.watermark"
    )


def _read_watermark(
    repo_root: Path, source_name: str = "claude-code"
) -> dict[str, Any]:
    """Read the persisted watermark for ``source_name``.

    Returns a fresh ``{"session_path": "", "byte_offset": 0}`` dict if the file
    is missing or unparseable — both mean "start from byte 0" semantically.
    """
    path = _watermark_path(repo_root, source_name)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("watermark is not a JSON object")
        obj = cast("dict[str, Any]", data)
        return {
            "session_path": str(obj.get("session_path", "")),
            "byte_offset": int(obj.get("byte_offset", 0)),
        }
    except (OSError, ValueError, json.JSONDecodeError):
        return {"session_path": "", "byte_offset": 0}


def _write_watermark(
    repo_root: Path,
    *,
    session_path: Path,
    byte_offset: int,
    source_name: str = "claude-code",
) -> None:
    """Persist the watermark for ``source_name`` after a successful run."""
    path = _watermark_path(repo_root, source_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": source_name,
        "session_path": str(session_path),
        "byte_offset": int(byte_offset),
        "last_advanced_at": datetime.now(UTC).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _resolve_start_byte(
    repo_root: Path, session_path: Path, source_name: str = "claude-code"
) -> int:
    """Decide the start byte for delta extraction of ``source_name``.

    Rules (in order):
    - missing/garbage watermark -> 0,
    - different session_path than the watermark -> 0 (new conversation),
    - file size < watermark.byte_offset -> 0 (truncation defense; the file
      was rotated/rewritten and we can't trust the old offset),
    - otherwise the watermark's recorded byte offset.
    """
    wm = _read_watermark(repo_root, source_name)
    if not wm["session_path"] or wm["session_path"] != str(session_path):
        return 0
    try:
        size = session_path.stat().st_size
    except OSError:
        return 0
    if size < wm["byte_offset"]:
        return 0
    return wm["byte_offset"]


def _run_watermark_extraction(
    *,
    repo_root: Path,
    session_path: Path,
    model: str,
    provider: str = "ollama",
    source: SessionSource | None = None,
) -> int:
    """Worker pipeline for the watermark-driven path.

    Reads the per-source watermark, chunks only the new bytes via
    ``chunk_session_from_offset`` using the source's ``parse_messages``, runs
    the same extract/dedupe/stage steps as ``extract_from_session``, and
    advances the watermark only on success.

    ``source`` defaults to the Claude Code adapter so the historical single-tool
    behavior (and existing tests that call this without a source) is preserved.

    Returns the number of decisions staged (so the CLI can print the same
    "Extracted N decision(s)" message).
    """
    from spanweave.learning.extractor import (
        OllamaNotAvailableError,
        chunk_session_from_offset,
        dedupe_against_existing,
        dedupe_within_batch,
        extract_decisions_from_chunk,
        stage_pending_decisions,
    )

    if source is None:
        source = get_source("claude-code")
    source_name = source.name

    start_byte = _resolve_start_byte(repo_root, session_path, source_name)
    chunks, end_byte = chunk_session_from_offset(
        session_path, start_byte=start_byte, parse_messages=source.parse_messages
    )

    if not chunks:
        # No new bytes -> success no-op, but still advance the watermark to
        # capture any file growth (e.g. metadata-only line that produced no
        # extractable message) so we don't re-scan the same bytes next fire.
        _write_watermark(
            repo_root,
            session_path=session_path,
            byte_offset=end_byte,
            source_name=source_name,
        )
        return 0

    all_decisions: list[dict[str, Any]] = []
    for chunk in chunks:
        try:
            extracted = extract_decisions_from_chunk(
                chunk, model=model, provider=provider
            )
            all_decisions.extend(extracted)
        except OllamaNotAvailableError:
            # Propagate so the CLI's quiet exit-0 backstop handles it; do NOT
            # advance the watermark — next fire re-processes these bytes.
            raise
        except Exception:
            logger.warning("Failed to extract from chunk, skipping", exc_info=True)
            continue

    if all_decisions:
        batch_unique = dedupe_within_batch(all_decisions)
        unique = dedupe_against_existing(batch_unique, repo_root=repo_root)
        if unique:
            # If staging raises (disk full, permission, etc.) we let it
            # propagate; the watermark is NOT advanced and next fire retries.
            stage_pending_decisions(unique, repo_root=repo_root)
        staged_count = len(unique)
    else:
        staged_count = 0

    _write_watermark(
        repo_root,
        session_path=session_path,
        byte_offset=end_byte,
        source_name=source_name,
    )
    return staged_count


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


def _spawn_detached(repo_root: Path, recent: int | None, tools: tuple[str, ...]) -> None:
    """Launch the (slow) extraction as a detached background process.

    Returns immediately; ``start_new_session=True`` detaches the child so it
    survives the hook returning — that's what keeps the hook under its timeout
    while gemma4:e4b takes its time on CPU. Child output goes to a log under
    .spanweave/daemon/ for inspection.

    When ``recent`` is None (the default hook path) we omit ``--recent`` from
    the child's argv so the worker uses watermark mode. Any explicit ``--tool``
    selections are forwarded so the detached worker processes the same sources.
    """
    log_dir = repo_root / ".spanweave" / "daemon"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = (log_dir / "extract-latest.log").open("ab")
    argv = [sys.argv[0], "extract-latest", "--repo", str(repo_root)]
    if recent is not None:
        argv += ["--recent", str(recent)]
    for tool in tools:
        argv += ["--tool", tool]
    try:
        subprocess.Popen(  # noqa: S603
            argv,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            cwd=str(repo_root),
        )
    finally:
        log.close()


def _selected_sources(tools: tuple[str, ...]) -> list[SessionSource]:
    """Resolve the ``--tool`` selection into source adapters.

    Explicit ``--tool`` values are looked up by name (a bad name raises a
    ClickException). With no ``--tool`` (auto mode), every registered source is
    returned; availability + per-repo session presence are filtered later, per
    source, so auto mode silently skips uninstalled tools.
    """
    if not tools:
        return all_sources()
    resolved: list[SessionSource] = []
    for name in tools:
        try:
            resolved.append(get_source(name))
        except KeyError as exc:
            raise click.ClickException(str(exc)) from exc
    return resolved


def _resolve_source_sessions(
    sources: list[SessionSource],
    repo_root: Path,
    *,
    explicit: bool,
) -> list[tuple[SessionSource, Path]]:
    """Pair each source with its latest session for ``repo_root``.

    In auto mode (``explicit=False``) a source is skipped unless it
    ``is_available()`` AND has a ``latest_session`` for this repo — so a machine
    with only one tool installed just processes that one, no errors.

    With explicit ``--tool`` we still require an actual session (you can't
    extract from a tool that has no transcript for this repo) but we don't
    pre-filter on ``is_available`` — an explicit request that finds a session is
    honored regardless.
    """
    pairs: list[tuple[SessionSource, Path]] = []
    for source in sources:
        if not explicit and not source.is_available():
            continue
        session = source.latest_session(repo_root)
        if session is None:
            continue
        pairs.append((source, session))
    return pairs


@click.command(
    "extract-latest",
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=build_help_epilog(
        notes=(
            "Reads the newest session for each selected tool: Claude Code "
            "(~/.claude/projects/<encoded-cwd>/) and/or Codex "
            "(~/.codex/sessions/ matched by repo).",
            "Default (no --tool) auto-processes every installed tool with a "
            "session for this repo.",
            "Designed to be called from tool hooks (e.g. a SessionEnd hook).",
        ),
        examples=(
            "spanweave extract-latest --repo .",
            "spanweave extract-latest --repo . --tool codex",
            "spanweave extract-latest --repo . --tool claude-code --tool codex",
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
    "--tool",
    "tools",
    multiple=True,
    type=click.Choice(["claude-code", "codex"]),
    help=(
        "Source tool to extract from (repeatable). Omit to auto-process every "
        "installed tool that has a session for this repo."
    ),
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
    "recent",
    default=None,
    type=int,
    show_default=False,
    help=(
        "Manual override: bound work to the last N conversation chunks "
        "(recency-window mode, for debugging / backfill). When omitted, the "
        "hook path uses the byte-offset watermark to process only new "
        "bytes since the last successful run."
    ),
)
@click.option(
    "--detach",
    is_flag=True,
    default=False,
    help=(
        "Launch extraction as a detached background process and return "
        "immediately. Used by the hook so a slow model never trips the "
        "hook timeout."
    ),
)
def extract_latest_command(
    repo: Path,
    tools: tuple[str, ...],
    model: str | None,
    recent: int | None,
    detach: bool,
) -> None:
    """Extract decisions from the most recent session transcript(s).

    For each selected tool, finds the newest transcript for this repo and runs
    extraction on it. Designed to be called from tool hooks.

    Default mode (no ``--recent``) uses a per-tool byte-offset watermark at
    ``.spanweave/daemon/extract-latest-<tool>.watermark`` so each fire processes
    only the bytes appended since the last successful run. Pass ``--recent N`` to
    force the legacy recency window (e.g. for backfill).
    """
    from spanweave.learning.extractor import OllamaNotAvailableError, extract_from_session

    repo_path = repo.resolve()
    explicit = bool(tools)
    sources = _selected_sources(tools)
    source_sessions = _resolve_source_sessions(sources, repo_path, explicit=explicit)

    if not source_sessions:
        # Auto mode with nothing to do is a graceful no-op (exit 0): a machine
        # may simply have no recorded sessions for this repo yet. An explicit
        # --tool that finds no session is a real error worth surfacing.
        if explicit:
            raise click.ClickException(
                f"No session files found for {repo_path} "
                f"from tool(s): {', '.join(tools)}."
            )
        return

    # Launcher mode (the hook): spawn a detached worker and return in <1s, so a
    # slow model (gemma4:e4b on CPU) never blocks the hook past its timeout. The
    # presence check above already confirmed there's work to do.
    if detach:
        _spawn_detached(repo_path, recent, tools)
        return

    # Worker mode. Default to the quality model (extraction runs detached, so
    # latency is decoupled from any interactive wait).
    if model is None:
        model = EXTRACTION_MODEL

    # Single-flight: if a live extraction already holds the lock, no-op quietly
    # so rapid session-ends don't pile up parallel CPU-bound Gemma runs. One
    # lock covers the whole run (all selected sources) — successive fires
    # serialize, but the watermarks make re-runs cheap.
    lock_path = _lock_path(repo_path)
    if not _acquire_lock(lock_path):
        return

    try:
        # This command runs as a tool hook (e.g. Claude Code SessionEnd hook).
        # When the optional local model server isn't running, fail fast and
        # quietly: a single calm stderr line and exit 0. Erroring here would
        # surface as a scary "hook error" on every session end where Ollama is
        # absent.
        if not ollama_available():
            click.echo(
                "spanweave: Ollama not running; skipping auto-extraction.",
                err=True,
            )
            return

        total_decisions = 0
        try:
            for source, session_path in source_sessions:
                if recent is not None:
                    # Manual override: legacy recency-window mode. Does NOT
                    # touch the watermark, so it's safe for ad-hoc backfill.
                    decisions = extract_from_session(
                        session_path,
                        model=model,
                        repo_root=repo_path,
                        recent_chunks=recent,
                        parse_messages=source.parse_messages,
                    )
                    total_decisions += len(decisions)
                else:
                    # Default: per-source byte-offset watermark mode. Advances
                    # the watermark only on success; on any failure the next
                    # fire re-processes the same bytes (dedup is the safety net).
                    total_decisions += _run_watermark_extraction(
                        repo_root=repo_path,
                        session_path=session_path,
                        model=model,
                        source=source,
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

        if not total_decisions:
            click.echo("No decisions extracted from latest session.")
            return

        click.echo(
            f"Extracted {total_decisions} decision(s) "
            f"→ .spanweave/memory/pending/decisions/"
        )
    finally:
        _release_lock(lock_path)


__all__ = ["extract_latest_command"]
