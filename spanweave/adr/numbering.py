from __future__ import annotations

import re
from pathlib import Path

_ADR_FILENAME_RE = re.compile(r"^(\d{4})-.*\.md$")


def next_adr_number(docs_adr_dir: Path) -> int:
    """Return the next sequential ADR number by scanning existing files."""
    if not docs_adr_dir.exists():
        return 1

    highest = 0
    for entry in docs_adr_dir.iterdir():
        match = _ADR_FILENAME_RE.match(entry.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


__all__ = ["next_adr_number"]
