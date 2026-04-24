from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from atelier.memory import MemoryRecord

from .base import ToolAdapter, TranscriptEntry

_ROLE_HEADING_PATTERN = re.compile(r"^#{1,6}\s*(user|assistant|system)\b", re.IGNORECASE)


class GenericAdapter(ToolAdapter):
    tool_name = "generic"
    session_format = "markdown"

    def ingest_transcript(self, session_path: str | Path) -> list[MemoryRecord]:
        resolved_path = Path(session_path).expanduser()
        text = resolved_path.read_text(encoding="utf-8")
        entries = self._parse_markdown_entries(text)
        return self._extract_records(entries, session_path=resolved_path)

    def format_context_packet(
        self,
        run_id: str,
        role: str,
        memory_records: Sequence[MemoryRecord],
    ) -> str:
        return self._build_packet(
            heading="# Tool Context Packet",
            role=role,
            instructions=[
                "This packet is self-contained and does not assume tool-specific config files.",
                (
                    "Use the captured decisions, ADR references, and run state "
                    "to resume work in a new tool."
                ),
            ],
            config_lines=["No repo-specific convention file is required for this fallback packet."],
            run_id=run_id,
            memory_records=memory_records,
        )

    def detect(self) -> bool:
        return False

    def _parse_markdown_entries(self, text: str) -> list[TranscriptEntry]:
        entries: list[TranscriptEntry] = []
        role = "assistant"
        buffer: list[str] = []

        def flush() -> None:
            if not buffer:
                return
            chunk = "\n".join(buffer).strip()
            buffer.clear()
            if chunk:
                entries.append(TranscriptEntry(role=role, text=chunk))

        for raw_line in text.splitlines():
            heading_match = _ROLE_HEADING_PATTERN.match(raw_line.strip())
            if heading_match is not None:
                flush()
                role = heading_match.group(1).lower()
                continue
            buffer.append(raw_line)

        flush()
        return entries


__all__ = ["GenericAdapter"]
