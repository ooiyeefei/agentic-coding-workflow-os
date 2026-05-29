"""Shared helpers for the native-memory harvesters.

Keeps the per-tool readers (``claude.py``, ``codex.py``) thin: they only know
how to turn their native store into decision dicts; type-normalization and
dedup live here so both behave identically.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spanweave.learning.extractor import _compute_overlap  # pyright: ignore[reportPrivateUsage]

__all__ = [
    "VALID_RECORD_TYPES",
    "dedupe_against_pending_and_confirmed",
    "existing_bodies",
]

#: Record types the review pipeline knows how to route (see the ``_TYPE_TO_DIR``
#: map in ``spanweave.cli.commands.review``). A harvested record whose native
#: type isn't one of these is normalized to a safe default by the reader so it
#: still flows through ``spanweave review`` instead of being rejected.
VALID_RECORD_TYPES: frozenset[str] = frozenset({
    "decision",
    "finding",
    "rejected_alternative",
})

#: Word-overlap ratio above which two bodies are treated as the same record.
#: Matches the threshold ``extractor.dedupe_against_existing`` uses.
_OVERLAP_THRESHOLD = 0.8

# Memory subdirectories that may already hold a record with the same body:
# the pending queue plus every confirmed destination the review pipeline
# routes to (private/ and shared/ for each record type, plus the legacy
# top-level decisions/ dir the extractor's own dedup checks).
_SEARCH_SUBDIRS: tuple[tuple[str, ...], ...] = (
    ("pending", "decisions"),
    ("pending", "reflections"),
    ("decisions",),
    ("private", "decisions"),
    ("private", "findings"),
    ("private", "rejected_alternatives"),
    ("private", "reflections"),
    ("shared", "decisions"),
    ("shared", "findings"),
    ("shared", "rejected_alternatives"),
    ("shared", "reflections"),
)


def _body_of(raw: str) -> str:
    """Return the normalized body text of a memory record file.

    Strips YAML frontmatter (everything up to the second ``---``) and
    lowercases, mirroring ``extractor.dedupe_against_existing`` so overlap
    comparisons are consistent across the codebase.
    """
    parts = raw.split("---", 2)
    body = parts[2] if len(parts) >= 3 else raw
    return body.strip().lower()


def existing_bodies(repo_root: Path) -> list[str]:
    """Collect normalized bodies of every existing pending/confirmed record."""
    memory_root = repo_root / ".spanweave" / "memory"
    bodies: list[str] = []
    for subdir in _SEARCH_SUBDIRS:
        directory = memory_root.joinpath(*subdir)
        if not directory.is_dir():
            continue
        for path in directory.glob("*.md"):
            body = _body_of(path.read_text(encoding="utf-8"))
            if body:
                bodies.append(body)
    return bodies


def dedupe_against_pending_and_confirmed(
    records: list[dict[str, Any]],
    *,
    repo_root: Path,
) -> list[dict[str, Any]]:
    """Drop records whose body already exists in pending or confirmed memory.

    Uses the same word-overlap heuristic as the extractor's dedup, so a native
    record that merely restates an already-captured decision is skipped. This is
    what makes ``spanweave harvest`` idempotent: a second run finds its own
    first-run output in ``pending/`` and stages nothing new. Also dedupes within
    the incoming batch so two identical native files don't both land.
    """
    prior = existing_bodies(repo_root)
    kept: list[dict[str, Any]] = []
    kept_bodies: list[str] = []
    for record in records:
        body = str(record.get("body", "")).strip().lower()
        if not body:
            continue
        if any(_compute_overlap(body, seen) > _OVERLAP_THRESHOLD for seen in prior):
            continue
        if any(_compute_overlap(body, seen) > _OVERLAP_THRESHOLD for seen in kept_bodies):
            continue
        kept.append(record)
        kept_bodies.append(body)
    return kept
