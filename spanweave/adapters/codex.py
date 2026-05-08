from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path

from spanweave.memory import MemoryRecord

from .base import ToolAdapter, TranscriptEntry

_CODEX_ENV_VARS = ("CODEX_THREAD_ID", "CODEX_CI", "CODEX_MANAGED_BY_NPM")


class CodexAdapter(ToolAdapter):
    tool_name = "codex"
    session_format = "jsonl"

    def ingest_transcript(self, session_path: str | Path) -> list[MemoryRecord]:
        resolved_path = Path(session_path).expanduser()
        entries: list[TranscriptEntry] = []

        for raw_line in resolved_path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            item = json.loads(raw_line)
            if not isinstance(item, dict):
                continue

            item_type = item.get("type")
            if item_type == "event_msg":
                event_entries = self._entries_from_event_payload(item.get("payload"))
                entries.extend(event_entries)
                continue
            if item_type == "response_item":
                response_entries = self._entries_from_response_payload(item.get("payload"))
                entries.extend(response_entries)

        return self._extract_records(entries, session_path=resolved_path)

    def format_context_packet(
        self,
        run_id: str,
        role: str,
        memory_records: Sequence[MemoryRecord],
    ) -> str:
        manifest = self.manifest
        config_lines = ["Read `AGENTS.md` before acting."]
        if manifest is not None:
            config_lines.append(f"Context injection: {manifest.context_injection}")
        return self._build_packet(
            heading="# AGENTS.md Context Packet",
            role=role,
            instructions=[
                "Use this packet as transferred context from prior tool sessions.",
                "Prefer current repository instructions over stale assumptions from earlier runs.",
                (
                    "Preserve the captured decisions unless you find concrete "
                    "evidence the repo moved on."
                ),
            ],
            config_lines=config_lines,
            run_id=run_id,
            memory_records=memory_records,
        )

    def detect(self) -> bool:
        has_env = any(os.getenv(name) for name in _CODEX_ENV_VARS)
        return (self.repo_root / "AGENTS.md").is_file() and has_env

    def _entries_from_event_payload(self, payload: object) -> list[TranscriptEntry]:
        if not isinstance(payload, dict):
            return []
        if payload.get("type") != "user_message":
            return []
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            return []
        return [TranscriptEntry(role="user", text=message.strip())]

    def _entries_from_response_payload(self, payload: object) -> list[TranscriptEntry]:
        if not isinstance(payload, dict):
            return []
        if payload.get("type") != "message" or payload.get("role") != "assistant":
            return []

        text = self._flatten_content(payload.get("content"))
        if not text:
            return []
        return [TranscriptEntry(role="assistant", text=text)]

    def _flatten_content(self, content: object) -> str:
        if not isinstance(content, list):
            return ""

        texts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "output_text":
                continue
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
        return "\n".join(texts).strip()


__all__ = ["CodexAdapter"]
