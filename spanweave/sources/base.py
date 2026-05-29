"""The ``SessionSource`` protocol shared by every tool adapter.

A source adapter answers four questions for one coding tool:
    1. What's my stable ``name``? (used by ``--tool`` and watermark keys)
    2. Is this tool's data dir present on this machine? (``is_available``)
    3. Where is the newest transcript for *this repo*? (``latest_session``)
    4. How do I turn that transcript's raw text into normalized turns?
       (``parse_messages``)

Everything downstream — chunking, the local-LLM extraction, dedupe, staging —
is tool-agnostic and lives in ``spanweave.learning.extractor``. Adapters only
own discovery + parsing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class SessionSource(Protocol):
    """Tool-specific transcript discovery + parsing.

    Implemented by ``ClaudeCodeSource``, ``CodexSource``, and any future
    adapter. ``runtime_checkable`` so tests can assert ``isinstance(x,
    SessionSource)`` structurally.
    """

    #: Stable identifier, e.g. ``"claude-code"`` / ``"codex"``. Used as the
    #: ``--tool`` value and as the per-source watermark filename suffix, so it
    #: must be filesystem-safe and never change across releases.
    name: str

    def is_available(self) -> bool:
        """Whether this tool's data directory exists on the machine.

        Auto mode (no ``--tool``) skips sources that return False so a machine
        with only Claude Code installed never tries to scan a missing
        ``~/.codex``.
        """
        ...

    def latest_session(self, repo_root: Path) -> Path | None:
        """Newest transcript file for ``repo_root``, or ``None`` if none match.

        ``repo_root`` is the repository whose ``.spanweave`` workspace we're
        populating. The adapter resolves the tool's per-repo session location
        and returns the most-recently-modified transcript, or ``None`` when the
        tool has no session recorded for this repo.
        """
        ...

    def parse_messages(self, text: str) -> list[str]:
        """Turn raw transcript text into normalized ``"[role]: body"`` strings.

        Output is the exact shape the chunker consumes (the same list
        ``_parse_jsonl_messages`` historically produced): one entry per
        human-readable user/assistant turn, e.g. ``"[user]: ..."`` /
        ``"[assistant]: ..."``. Tool-internal noise (system/developer prompts,
        tool calls, reasoning traces, metadata) is dropped.
        """
        ...


__all__ = ["SessionSource"]
