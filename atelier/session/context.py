from __future__ import annotations

from pathlib import Path

from atelier.compiler import SampleDoc, Source, compile_packet
from atelier.memory import MemoryRecord

from .resume import _load_memory_records, _render_memory_record


def generate_context(target: str, token_limit: int = 4000) -> str:
    """Generate a standalone, token-budgeted context summary from durable memory."""

    if token_limit <= 0:
        raise ValueError("token_limit must be positive")

    repo_root = Path.cwd()
    records = _load_memory_records(repo_root)
    objective = (
        f"Standalone Atelier memory context for {target.strip() or 'external tool'}. "
        "Use this summary without assuming access to the original CLI session."
    )
    packet = compile_packet(
        objective,
        _context_sources(records),
        budget_tokens=token_limit,
    )
    return packet.body


def _context_sources(records: list[MemoryRecord]) -> list[Source]:
    return [
        SampleDoc(
            source_id=record.id,
            priority="should",
            title=f"{record.type}: {record.id}",
            content=_render_memory_record(record),
            path=f".atelier/memory/{record.path_fragment.as_posix()}",
        )
        for record in records
    ]


__all__ = ["generate_context"]
