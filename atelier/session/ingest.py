from __future__ import annotations

from pathlib import Path

from atelier.memory import MemoryRecord, write_record

from .resume import _adapter_for_target


def ingest_transcript(path: str | Path, source_tool: str = "generic") -> list[MemoryRecord]:
    """Ingest a transcript through the requested tool adapter and persist memory records."""

    transcript_path = Path(path).expanduser()
    adapter = _adapter_for_target(source_tool, repo_root=Path.cwd())
    records = adapter.ingest_transcript(transcript_path)
    memory_root = Path.cwd() / ".atelier" / "memory"
    for record in records:
        write_record(record, memory_root)
    return records


__all__ = ["ingest_transcript"]
