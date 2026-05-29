"""Codex CLI source adapter.

Codex writes one ``rollout-<ISO-ts>-<uuid>.jsonl`` transcript per session under
a date-partitioned tree: ``~/.codex/sessions/YYYY/MM/DD/``. Unlike Claude Code,
the directory path does NOT encode the repo — the repo lives *inside* the file,
on the first line:

    {"timestamp": ..., "type": "session_meta",
     "payload": {"id": ..., "cwd": "/abs/repo/path", ...}}

So matching a session to a repo means scanning rollouts and reading each one's
``session_meta.payload.cwd`` (the ``~/.codex/session_index.jsonl`` file has no
cwd field, so it can't be used for this).

Message schema (verified against real rollouts, codex_cli_rs 0.106.0):

    {"timestamp": ..., "type": "response_item",
     "payload": {"type": "message", "role": "user"|"assistant"|"developer",
                 "content": [{"type": "input_text"|"output_text",
                              "text": "..."}]}}

We keep ``role`` in {user, assistant} only — ``developer`` lines are Codex's
own injected system/permission/AGENTS.md prompts, not conversation. Other line
shapes (``event_msg`` task_started/agent_message/token_count/…,
``turn_context``, and ``response_item`` of type reasoning/function_call/
function_call_output) carry no human conversation text and are skipped.

Content parts are normalized by reading each part's ``text`` field regardless of
the part ``type`` (``input_text`` for user, ``output_text`` for assistant, and
any future text-bearing part), which keeps the parser robust to part-type
renames.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


class CodexSource:
    """``SessionSource`` for Codex CLI rollouts."""

    name = "codex"

    def sessions_dir(self) -> Path:
        """Root of Codex's date-partitioned session tree."""
        return Path.home() / ".codex" / "sessions"

    def is_available(self) -> bool:
        """True if ``~/.codex/sessions`` exists (Codex has run on this machine)."""
        return self.sessions_dir().exists()

    @staticmethod
    def _read_session_meta(rollout: Path) -> dict[str, Any] | None:
        """Read and return a rollout's first-line ``session_meta`` payload.

        Returns ``None`` if the file is empty/unreadable, the first line isn't
        valid JSON, or it isn't a ``session_meta`` record. Only the first line
        is read — that's where Codex always writes the meta — so this stays
        cheap even for large rollouts.
        """
        try:
            with rollout.open("r", encoding="utf-8") as f:
                first = f.readline().strip()
        except OSError:
            return None
        if not first:
            return None
        try:
            obj = json.loads(first)
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        record = cast("dict[str, Any]", obj)
        if record.get("type") != "session_meta":
            return None
        payload = record.get("payload")
        if not isinstance(payload, dict):
            return None
        return cast("dict[str, Any]", payload)

    def _session_cwd(self, rollout: Path) -> str | None:
        """Resolved ``cwd`` recorded in a rollout's ``session_meta``, if any."""
        payload = self._read_session_meta(rollout)
        if payload is None:
            return None
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            return None
        try:
            return str(Path(cwd).resolve())
        except OSError:
            return cwd

    def latest_session(self, repo_root: Path) -> Path | None:
        """Newest rollout whose ``session_meta`` cwd matches ``repo_root``.

        Scans ``~/.codex/sessions/**/rollout-*.jsonl``, reads each one's
        first-line cwd, keeps those equal to the resolved ``repo_root``, and
        returns the most-recently-modified match (mtime). Returns ``None`` when
        the tree is absent or no rollout was recorded for this repo.
        """
        sessions_dir = self.sessions_dir()
        if not sessions_dir.exists():
            return None

        target = str(repo_root.resolve())
        matches: list[Path] = []
        for rollout in sessions_dir.glob("**/rollout-*.jsonl"):
            if self._session_cwd(rollout) == target:
                matches.append(rollout)

        if not matches:
            return None

        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return matches[0]

    @staticmethod
    def _content_text(content: Any) -> str:
        """Flatten a message ``content`` value into a single text string.

        Codex content is a list of parts (each typically ``{"type": ...,
        "text": ...}``); we concatenate every part's ``text``. A bare string
        content (older/edge shapes) is returned as-is. Non-text parts contribute
        nothing.
        """
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return ""
        pieces: list[str] = []
        for part in cast("list[Any]", content):
            if isinstance(part, dict):
                text = cast("dict[str, Any]", part).get("text")
                if isinstance(text, str) and text:
                    pieces.append(text)
            elif isinstance(part, str) and part:
                pieces.append(part)
        return "\n".join(pieces)

    def parse_messages(self, text: str) -> list[str]:
        """Parse a Codex rollout's JSONL into ``"[role]: body"`` strings.

        Keeps only ``response_item`` message lines with ``role`` in
        {user, assistant}; skips ``developer`` lines, ``event_msg`` /
        ``turn_context`` lines, reasoning/function-call response items, blanks,
        and malformed JSON.
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
            payload = cast("dict[str, Any]", entry).get("payload")
            if not isinstance(payload, dict):
                continue
            payload = cast("dict[str, Any]", payload)
            if payload.get("type") != "message":
                continue
            role = payload.get("role")
            if role not in ("user", "assistant"):
                continue
            body = self._content_text(payload.get("content")).strip()
            if body:
                messages.append(f"[{role}]: {body}")
        return messages


__all__ = ["CodexSource"]
