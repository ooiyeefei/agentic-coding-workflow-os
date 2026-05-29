"""Claude Code source adapter.

Claude Code writes one ``*.jsonl`` transcript per session under
``~/.claude/projects/<encoded-cwd>/``, where ``<encoded-cwd>`` is the absolute
repo path with every ``/`` replaced by ``-`` (e.g. ``/home/fei/proj`` ->
``-home-fei-proj``). Each line is a JSON object; user/assistant turns look like
``{"type": "user"|"assistant", "message": "..."}``.

This adapter is a 1:1 move of the discovery + parsing logic that previously
lived inline in ``extract_latest.py`` and ``extractor._parse_jsonl_messages`` —
behavior preserved so the existing Claude tests keep passing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


class ClaudeCodeSource:
    """``SessionSource`` for Claude Code transcripts."""

    name = "claude-code"

    def project_dir(self, repo_root: Path) -> Path:
        """Compute the per-repo Claude Code session directory.

        Claude Code encodes the project path by replacing ``/`` with ``-`` as
        the directory name under ``~/.claude/projects/``. For example::

            /home/fei/project -> -home-fei-project
        """
        resolved = str(repo_root.resolve())
        encoded = resolved.replace("/", "-")
        return Path.home() / ".claude" / "projects" / encoded

    def is_available(self) -> bool:
        """True if ``~/.claude/projects`` exists (Claude Code has run here)."""
        return (Path.home() / ".claude" / "projects").exists()

    def latest_session(self, repo_root: Path) -> Path | None:
        """Newest ``*.jsonl`` in the repo's Claude project dir, or ``None``."""
        project_dir = self.project_dir(repo_root)
        if not project_dir.exists():
            return None

        jsonl_files = list(project_dir.glob("*.jsonl"))
        if not jsonl_files:
            return None

        # Most recent modification time wins.
        jsonl_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return jsonl_files[0]

    def parse_messages(self, text: str) -> list[str]:
        """Parse Claude's ``{"type","message"}`` JSONL into ``"[role]: body"``.

        Skips blank lines, malformed JSON, and non-user/assistant entries —
        the same contract the chunker has always consumed.
        """
        messages: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            record = cast("dict[str, Any]", entry)
            msg_type = record.get("type", "")
            message = record.get("message", "")
            if msg_type in ("user", "assistant") and message:
                messages.append(f"[{msg_type}]: {message}")
        return messages


__all__ = ["ClaudeCodeSource"]
