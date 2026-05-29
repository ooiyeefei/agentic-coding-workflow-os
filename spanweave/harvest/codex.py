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

**Project scoping.** Codex's memory store is a single GLOBAL tree shared by every
repo, so a naive import pulls in every project's sessions. Each rollout summary
carries bare ``key: value`` frontmatter (no ``---`` fences) that includes a
``cwd:`` line — the absolute path of the repo that session ran in. By default we
import only the summaries whose ``cwd`` matches the current repo, mirroring the
already-per-repo Claude harvester; pass ``all_projects=True`` (the ``--all``
flag) to import the entire global store unscoped. The consolidated
``memory_summary.md`` has no single ``cwd`` (it is cross-project) and is included
only in the unscoped ``--all`` view.
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


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split a Codex summary's bare ``key: value`` frontmatter from its body.

    Codex rollout summaries open with a run of unfenced ``key: value`` metadata
    lines (``thread_id:``, ``updated_at:``, ``cwd:``, ``git_branch:`` ...),
    followed by a blank line and then the markdown prose. The frontmatter ends at
    the first blank line, or at the first line that doesn't look like
    ``key: value`` (e.g. a ``#`` heading) — so files with no frontmatter at all
    (like ``memory_summary.md``, which opens with a ``## User Profile`` heading)
    yield an empty meta dict and the whole text as the body.

    Returns ``(meta, body)`` where ``meta`` keys/values are stripped strings.
    """
    lines = text.splitlines()
    meta: dict[str, str] = {}
    idx = 0
    for idx, line in enumerate(lines):
        if line.strip() == "":
            idx += 1  # consume the blank separator
            break
        key, sep, value = line.partition(":")
        if not sep or not key.strip() or key.lstrip().startswith("#"):
            # Not a ``key: value`` line → frontmatter (if any) has ended here.
            break
        meta[key.strip()] = value.strip()
    else:
        # Every line was frontmatter (no trailing body).
        idx = len(lines)
    body = "\n".join(lines[idx:]).strip()
    return meta, body


def _record_from_file(
    path: Path, *, kind: str, meta: dict[str, str] | None = None
) -> dict[str, Any] | None:
    """Build a finding-record dict from a Codex prose summary file.

    ``kind`` is a short provenance label (``"summary"`` or ``"rollout"``). The
    file path is embedded in the body so the provenance survives promotion, and
    a ``source:<file>`` tag keeps the dedup body stable across runs. ``meta`` is
    the parsed frontmatter; when present its ``cwd`` is annotated into the
    record's reasoning for provenance. Pass ``None`` to parse it here.
    """
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None

    if meta is None:
        meta, _ = _parse_frontmatter(text)

    if kind == "summary":
        title = "Codex memory summary"
    else:
        heading = _first_heading(text)
        title = f"Codex session: {heading}" if heading else f"Codex session: {path.stem}"

    provenance = f"Source: Codex native memory ({kind}) — {path.name}"
    body = f"# {title}\n\n{provenance}\n\n{text}"

    reasoning = f"Imported from Codex native memory: {path.name}"
    cwd = meta.get("cwd")
    if cwd:
        reasoning = f"{reasoning} (cwd: {cwd})"

    return {
        "type": _RECORD_TYPE,
        "body": body,
        "reasoning": reasoning,
        "tags": ["codex", f"codex-{kind}", f"source:{path.name}"],
        "confidence": 1.0,
    }


def read_codex_records(repo_root: Path | None = None) -> list[dict[str, Any]]:
    """Parse Codex native-memory summaries into stage-able decision dicts.

    Codex's memory store is GLOBAL — a single ``~/.codex/memories`` tree shared
    across every repo — so this reader is project-scoped by default:

    * When ``repo_root`` is provided, include a rollout summary ONLY if its
      frontmatter ``cwd`` equals ``str(repo_root.resolve())`` (exact match on the
      resolved absolute path). A summary with no ``cwd`` line is excluded, and
      the cross-project ``memory_summary.md`` (which has no single ``cwd``) is
      excluded too — it would pollute a project-scoped import.
    * When ``repo_root`` is ``None`` (the ``--all`` case), include the entire
      global store unscoped, ``memory_summary.md`` included.

    Returns an empty list when the Codex memory store is absent.
    """
    memory_dir = codex_memory_dir()
    if not memory_dir.is_dir():
        return []

    scoped_cwd = str(repo_root.resolve()) if repo_root is not None else None

    records: list[dict[str, Any]] = []

    # The consolidated summary is cross-project; include it only when unscoped.
    summary_path = memory_dir / _SUMMARY_FILENAME
    if scoped_cwd is None and summary_path.is_file():
        record = _record_from_file(summary_path, kind="summary")
        if record is not None:
            records.append(record)

    rollout_dir = memory_dir / _ROLLOUT_DIRNAME
    if rollout_dir.is_dir():
        for path in sorted(rollout_dir.glob("*.md")):
            meta, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
            if scoped_cwd is not None and meta.get("cwd") != scoped_cwd:
                # Different project, or no cwd at all → not in the scoped view.
                continue
            record = _record_from_file(path, kind="rollout", meta=meta)
            if record is not None:
                records.append(record)

    return records


def harvest_codex_memory(
    repo_root: Path, *, all_projects: bool = False
) -> list[Path]:
    """Read Codex native memory and stage it into the pending review queue.

    By default the harvest is project-scoped to ``repo_root``: only rollout
    summaries whose frontmatter ``cwd`` matches the repo are imported (Codex
    memory is one global store, so this keeps a repo's import from pulling in
    every other project's sessions). Pass ``all_projects=True`` (the ``--all``
    flag) to import the entire global store unscoped, including
    ``memory_summary.md``.

    Records are written with ``source: native-codex``. Records whose body
    already exists in pending or confirmed memory are skipped, so repeated runs
    are idempotent. Returns the paths of the records actually written.
    """
    scope = None if all_projects else repo_root
    records = read_codex_records(scope)
    fresh = dedupe_against_pending_and_confirmed(records, repo_root=repo_root)
    if not fresh:
        return []
    return stage_pending_decisions(fresh, repo_root=repo_root, source="native-codex")
