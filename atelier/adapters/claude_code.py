from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from atelier.memory import MemoryRecord

from .base import ToolAdapter, TranscriptEntry


class ClaudeCodeAdapter(ToolAdapter):
    tool_name = "claude-code"
    session_format = "jsonl"

    def ingest_transcript(self, session_path: str | Path) -> list[MemoryRecord]:
        resolved_path = Path(session_path).expanduser()
        entries: list[TranscriptEntry] = []
        for raw_line in resolved_path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            payload = json.loads(raw_line)
            if not isinstance(payload, dict):
                continue
            message = payload.get("message")
            if not isinstance(message, dict):
                continue

            role = message.get("role")
            if role not in {"user", "assistant"}:
                continue

            text = self._flatten_content(message.get("content"))
            if not text:
                continue
            entries.append(
                TranscriptEntry(
                    role=cast(str, role),
                    text=text,
                    timestamp=self._optional_text(payload.get("timestamp")),
                )
            )

        return self._extract_records(entries, session_path=resolved_path)

    def format_context_packet(
        self,
        run_id: str,
        role: str,
        memory_records: Sequence[MemoryRecord],
    ) -> str:
        manifest = self.manifest
        config_lines = [
            "Read `CLAUDE.md` before acting.",
            "Review relevant files in `.claude/rules/` before implementation.",
        ]
        if manifest is not None:
            config_lines.append(f"Context injection: {manifest.context_injection}")
        return self._build_packet(
            heading="# CLAUDE.md Context Packet",
            role=role,
            instructions=[
                "Treat this packet as durable context captured from prior tool sessions.",
                "Prefer repository and rules-file conventions over restating them from memory.",
                "Carry forward the recorded decisions unless the repository now contradicts them.",
            ],
            config_lines=config_lines,
            run_id=run_id,
            memory_records=memory_records,
        )

    def detect(self) -> bool:
        return (self.repo_root / ".claude").is_dir()

    def _flatten_content(self, content: object) -> str:
        if isinstance(content, str):
            return content.strip()
        if not isinstance(content, list):
            return ""

        texts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "text":
                continue
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
        return "\n".join(texts).strip()

    def _optional_text(self, value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value
        return None
__all__ = ["ClaudeCodeAdapter"]
