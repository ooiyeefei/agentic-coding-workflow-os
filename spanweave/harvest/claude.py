"""Read Claude Code's native memory store and import it into Spanweave.

Claude Code curates its own typed memory records under::

    ~/.claude/projects/<encoded-cwd>/memory/*.md

where ``<encoded-cwd>`` is the repo's absolute path with ``/`` replaced by ``-``
(the same encoding Claude Code uses for its session directory). Each record
carries YAML frontmatter (``name``/``title``, ``type``, ``tags``, ...) plus a
markdown body, and a ``MEMORY.md`` index file ties them together. These records
are already typed and human-curated, so they make high-quality imports into the
shared ``.spanweave/memory/`` layer.

This module locates that directory, parses each record into the plain-dict shape
that :func:`stage_pending_decisions` consumes, normalizes the type to one the
review pipeline accepts, and stages it with ``source: native-claude``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter

from spanweave.harvest._common import (
    VALID_RECORD_TYPES,
    dedupe_against_pending_and_confirmed,
)
from spanweave.learning.extractor import stage_pending_decisions

__all__ = [
    "claude_memory_dir",
    "encode_cwd",
    "harvest_claude_memory",
    "read_claude_records",
]

#: Type assigned to native records whose own type is not a valid review type.
_DEFAULT_TYPE = "finding"

#: Index file Claude maintains; it is not itself a memory record.
_INDEX_FILENAME = "MEMORY.md"


def encode_cwd(repo_root: Path) -> str:
    """Encode an absolute repo path the way Claude Code names its dirs.

    The repo's resolved absolute path has every ``/`` replaced by ``-``; e.g.
    ``/home/fei/project`` -> ``-home-fei-project``. This mirrors
    ``extract_latest._claude_project_dir`` so harvest and extraction agree on
    where Claude's per-project data lives.
    """
    return str(repo_root.resolve()).replace("/", "-")


def claude_memory_dir(repo_root: Path) -> Path:
    """Return the Claude native-memory directory for ``repo_root``.

    Mirrors Claude Code's own layout:
    ``~/.claude/projects/<encoded-cwd>/memory``.
    """
    return Path.home() / ".claude" / "projects" / encode_cwd(repo_root) / "memory"


def _coerce_tags(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        items: list[Any] = list(value)  # pyright: ignore[reportUnknownArgumentType]
        return [str(item) for item in items]
    return []


def _extract_type(metadata: dict[str, Any]) -> str:
    """Pull a record type from frontmatter, checking nested ``metadata:`` too.

    Claude writes the type either at the top level (``type: feedback``) or nested
    under a ``metadata:`` mapping (``metadata: {type: project, ...}``) depending
    on the record. Check both.
    """
    raw: Any = metadata.get("type")
    if not isinstance(raw, str):
        nested = metadata.get("metadata")
        if isinstance(nested, dict):
            raw = nested.get("type")  # type: ignore[union-attr]
    return raw.strip() if isinstance(raw, str) else ""


def _title_of(metadata: dict[str, Any], body: str, *, fallback: str) -> str:
    """Best-effort human title: frontmatter name/title, then heading, then stem."""
    for key in ("title", "name"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _record_from_file(path: Path) -> dict[str, Any] | None:
    """Parse one Claude memory file into a stage-able decision dict.

    Returns ``None`` for an empty-bodied file. The returned dict matches the
    shape :func:`stage_pending_decisions` writes: ``type``, ``body``,
    ``reasoning``, ``tags``, ``confidence``.
    """
    post = frontmatter.load(str(path))
    metadata: dict[str, Any] = dict(post.metadata)
    body = post.content.strip()
    if not body:
        return None

    title = _title_of(metadata, body, fallback=path.stem)
    tags = _coerce_tags(metadata.get("tags"))

    native_type = _extract_type(metadata)
    if native_type in VALID_RECORD_TYPES:
        decision_type = native_type
    else:
        decision_type = _DEFAULT_TYPE
        if native_type:
            # Preserve the original native type for provenance / later curation.
            tags = [*tags, f"native-type:{native_type}"]

    # Fold the title into the body as a heading so it survives staging — the
    # pending record format has no dedicated title field. Skip if the body
    # already opens with that heading.
    if not body.startswith(f"# {title}"):
        body = f"# {title}\n\n{body}"

    return {
        "type": decision_type,
        "body": body,
        "reasoning": f"Imported from Claude Code native memory: {path.name}",
        "tags": tags,
        "confidence": 1.0,
    }


def read_claude_records(repo_root: Path) -> list[dict[str, Any]]:
    """Parse Claude native-memory records for ``repo_root``.

    Returns an empty list when the memory directory does not exist, so callers
    can treat a missing store as a graceful no-op. The ``MEMORY.md`` index is
    skipped — it is a table of contents, not a record.
    """
    memory_dir = claude_memory_dir(repo_root)
    if not memory_dir.is_dir():
        return []

    records: list[dict[str, Any]] = []
    for path in sorted(memory_dir.glob("*.md")):
        if path.name == _INDEX_FILENAME:
            continue
        record = _record_from_file(path)
        if record is not None:
            records.append(record)
    return records


def harvest_claude_memory(repo_root: Path) -> list[Path]:
    """Read Claude native memory and stage it into the pending review queue.

    Records are written with ``source: native-claude``. Records whose body
    already exists in pending or confirmed memory are skipped, so repeated runs
    are idempotent. Returns the paths of the records actually written.
    """
    records = read_claude_records(repo_root)
    fresh = dedupe_against_pending_and_confirmed(records, repo_root=repo_root)
    if not fresh:
        return []
    return stage_pending_decisions(fresh, repo_root=repo_root, source="native-claude")
