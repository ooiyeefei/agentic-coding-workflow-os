"""Read Codex's native memory store and import it into Spanweave.

Codex consolidates prose summaries about its past sessions under::

    ~/.codex/memories/memory_summary.md          # rolling cross-session summary
    ~/.codex/memories/rollout_summaries/*.md     # one summary per past session

Unlike Claude Code's typed records, these are free-form prose with markdown
headings (``## Task N``, ``## Preference signals``, ``## Key steps``, ...). For
v1 we do not parse the prose into structured decisions; instead each source file
is imported as a single ``finding`` record whose body is the summary text, with
a provenance pointer back to the originating file path. That captures what Codex
remembered, with attribution, and lets it flow through the same review → promote
pipeline as everything else.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spanweave.harvest._common import dedupe_against_pending_and_confirmed
from spanweave.learning.extractor import stage_pending_decisions

__all__ = [
    "codex_memory_dir",
    "harvest_codex_memory",
    "read_codex_records",
]

#: Codex prose summaries are imported as findings (they are not typed natively).
_RECORD_TYPE = "finding"

_SUMMARY_FILENAME = "memory_summary.md"
_ROLLOUT_DIRNAME = "rollout_summaries"


def codex_memory_dir() -> Path:
    """Return Codex's native-memory directory (``~/.codex/memories``)."""
    return Path.home() / ".codex" / "memories"


def _first_heading(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading:
                return heading
    return None


def _record_from_file(path: Path, *, kind: str) -> dict[str, Any] | None:
    """Build a finding-record dict from a Codex prose summary file.

    ``kind`` is a short provenance label (``"summary"`` or ``"rollout"``). The
    file path is embedded in the body so the provenance survives promotion, and
    a ``source:<file>`` tag keeps the dedup body stable across runs.
    """
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None

    if kind == "summary":
        title = "Codex memory summary"
    else:
        heading = _first_heading(text)
        title = f"Codex session: {heading}" if heading else f"Codex session: {path.stem}"

    provenance = f"Source: Codex native memory ({kind}) — {path.name}"
    body = f"# {title}\n\n{provenance}\n\n{text}"

    return {
        "type": _RECORD_TYPE,
        "body": body,
        "reasoning": f"Imported from Codex native memory: {path.name}",
        "tags": ["codex", f"codex-{kind}", f"source:{path.name}"],
        "confidence": 1.0,
    }


def read_codex_records(repo_root: Path | None = None) -> list[dict[str, Any]]:
    """Parse Codex native-memory summaries into stage-able decision dicts.

    ``repo_root`` is accepted for signature symmetry with the Claude reader;
    Codex memory is global (not per-repo), so it is unused here. Returns an empty
    list when the Codex memory store is absent.
    """
    del repo_root  # Codex memory is not scoped to a repo.

    memory_dir = codex_memory_dir()
    if not memory_dir.is_dir():
        return []

    records: list[dict[str, Any]] = []

    summary_path = memory_dir / _SUMMARY_FILENAME
    if summary_path.is_file():
        record = _record_from_file(summary_path, kind="summary")
        if record is not None:
            records.append(record)

    rollout_dir = memory_dir / _ROLLOUT_DIRNAME
    if rollout_dir.is_dir():
        for path in sorted(rollout_dir.glob("*.md")):
            record = _record_from_file(path, kind="rollout")
            if record is not None:
                records.append(record)

    return records


def harvest_codex_memory(repo_root: Path) -> list[Path]:
    """Read Codex native memory and stage it into the pending review queue.

    Records are written with ``source: native-codex``. Records whose body
    already exists in pending or confirmed memory are skipped, so repeated runs
    are idempotent. Returns the paths of the records actually written.
    """
    records = read_codex_records(repo_root)
    fresh = dedupe_against_pending_and_confirmed(records, repo_root=repo_root)
    if not fresh:
        return []
    return stage_pending_decisions(fresh, repo_root=repo_root, source="native-codex")
