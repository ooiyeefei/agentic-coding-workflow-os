from __future__ import annotations

from os import PathLike
from pathlib import Path

import yaml

from spanweave.security.redaction import redact
from spanweave.util import atomic_write

from .records import MemoryRecord

DEFAULT_MEMORY_ROOT = Path(".spanweave/memory")


def _serialize_record(record: MemoryRecord) -> str:
    frontmatter_text = yaml.safe_dump(
        record.frontmatter(),
        allow_unicode=True,
        sort_keys=False,
    )
    return f"---\n{frontmatter_text}---\n{record.body}"


def _resolve_destination(record: MemoryRecord, path: str | PathLike[str]) -> Path:
    destination = Path(path)
    if destination.suffix == ".md":
        if destination.name != record.filename:
            raise ValueError(f"expected filename {record.filename!r}, got {destination.name!r}")
        return destination

    if destination.name == record.collection:
        return destination / record.filename

    return destination / record.path_fragment


def write_record(record: MemoryRecord, path: str | PathLike[str] = DEFAULT_MEMORY_ROOT) -> Path:
    """Persist a typed memory record as redacted markdown with YAML frontmatter."""

    destination = _resolve_destination(record, path)
    return atomic_write(destination, redact(_serialize_record(record)))


__all__ = ["DEFAULT_MEMORY_ROOT", "write_record"]
