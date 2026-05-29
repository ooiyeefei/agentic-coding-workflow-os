"""Dual-track recall-compare: load records, bucket by source, compare tracks.

See ``spanweave.eval`` package docstring for the track definitions and the
recall metric. This module is pure logic (no click, no I/O beyond reading the
record files) so it is straightforward to unit-test.

Matching reuses ``spanweave.learning.extractor._compute_overlap`` (read-only):
a Track A record counts as *recalled* (A∩B) when its body's word-overlap with
the best-matching Track B body is >= the threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import yaml

# Reused read-only for body matching (the brief mandates reusing this exact
# word-overlap helper); strict pyright flags the cross-module private import,
# which we accept rather than modify extractor.py to widen its API.
from spanweave.learning.extractor import (
    _compute_overlap,  # pyright: ignore[reportPrivateUsage]
)

# Default match threshold for word-overlap similarity in [0, 1]. 0.5 means "at
# least half the words of the smaller body are shared" — high enough to reject
# incidental single-word overlaps, low enough that gemma's paraphrase of an
# agent-curated decision (different surface wording, same substance) still
# matches. Overridable via the CLI ``--threshold`` option.
DEFAULT_THRESHOLD = 0.5

# Memory subdirectories (relative to ``.spanweave/memory/``) that hold decision
# records. ``confirmed`` covers the post-review locations (decisions/, findings/,
# rejected_alternatives/ plus their private/ and shared/ variants); ``pending``
# is the not-yet-reviewed staging area. We rglob each root so nested private/
# and shared/ trees are included without enumerating every leaf here.
_CONFIRMED_ROOTS = (
    "decisions",
    "findings",
    "rejected_alternatives",
    "shared",
    "private",
)
_PENDING_ROOT = "pending"

# Prefix that identifies a Track A (native-curated) record.
NATIVE_SOURCE_PREFIX = "native-"
# Exact source value that identifies a Track B (gemma-extracted) record.
AUTO_EXTRACTION_SOURCE = "auto-extraction"


@dataclass(frozen=True)
class EvalRecord:
    """A single parsed memory record relevant to the eval.

    ``source`` is the raw frontmatter value; ``body`` is the markdown body
    (everything after the closing ``---``). ``path`` is kept for reporting /
    debugging. ``track`` is ``"A"`` (native-*), ``"B"`` (auto-extraction), or
    ``None`` (some other source such as ``seed`` — ignored by the comparison).
    """

    path: Path
    source: str
    body: str
    track: str | None


def _parse_frontmatter_and_body(filepath: Path) -> tuple[dict[str, object], str]:
    """Split a record file into (frontmatter dict, body text).

    Mirrors ``review._parse_record_frontmatter`` but also returns the body.
    A file that doesn't open with ``---\\n`` or has no closing ``---`` yields
    ``({}, "")`` so it is treated as untracked (neither A nor B).
    """
    try:
        raw = filepath.read_text(encoding="utf-8")
    except OSError:
        return {}, ""
    if not raw.startswith("---\n"):
        return {}, ""
    _, _, remainder = raw.partition("---\n")
    frontmatter_text, separator, body = remainder.partition("\n---\n")
    if not separator:
        return {}, ""
    try:
        payload = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        return {}, body.strip()
    if not isinstance(payload, dict):
        return {}, body.strip()
    return cast("dict[str, object]", payload), body.strip()


def _classify_track(source: str) -> str | None:
    """Map a raw ``source`` value to a track label (``"A"``/``"B"``/``None``)."""
    if source.startswith(NATIVE_SOURCE_PREFIX):
        return "A"
    if source == AUTO_EXTRACTION_SOURCE:
        return "B"
    return None


def _iter_record_files(memory_dir: Path, *, include_pending: bool) -> list[Path]:
    """Collect all ``*.md`` record files under the configured roots.

    De-duplicates by resolved path (the confirmed roots could in principle
    overlap) and returns a sorted list for deterministic reporting.
    """
    seen: set[Path] = set()
    roots: list[str] = list(_CONFIRMED_ROOTS)
    if include_pending:
        roots.append(_PENDING_ROOT)
    for root_name in roots:
        root = memory_dir / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            if path.is_file():
                seen.add(path)
    return sorted(seen)


def load_records(
    repo_root: Path,
    *,
    include_pending: bool = True,
) -> list[EvalRecord]:
    """Walk ``<repo_root>/.spanweave/memory`` and parse every record.

    Returns one ``EvalRecord`` per ``*.md`` file under the decision-bearing
    subdirectories (and ``pending/`` when ``include_pending``). Records whose
    ``source`` is neither native-* nor auto-extraction get ``track=None`` and
    are carried through (callers filter by track).
    """
    memory_dir = repo_root / ".spanweave" / "memory"
    records: list[EvalRecord] = []
    for path in _iter_record_files(memory_dir, include_pending=include_pending):
        frontmatter, body = _parse_frontmatter_and_body(path)
        raw_source = frontmatter.get("source", "")
        source = raw_source.strip() if isinstance(raw_source, str) else ""
        records.append(
            EvalRecord(
                path=path,
                source=source,
                body=body,
                track=_classify_track(source),
            )
        )
    return records


def bucket_records(
    records: list[EvalRecord],
) -> tuple[list[EvalRecord], list[EvalRecord]]:
    """Split records into ``(track_a, track_b)`` by their classified track.

    Records with an empty body are dropped — they carry no signal to match on
    and would otherwise inflate the denominator of recall with un-matchable
    entries.
    """
    track_a = [r for r in records if r.track == "A" and r.body]
    track_b = [r for r in records if r.track == "B" and r.body]
    return track_a, track_b


@dataclass(frozen=True)
class RecallReport:
    """Result of comparing Track A (native) against Track B (extraction).

    ``intersection`` (A∩B): A records that have a B match >= threshold.
    ``a_only`` (A−B): A records with no B match — coverage gaps (the agent
    remembered it, gemma missed it).
    ``b_only`` (B−A): B records that matched no A record — extras (gemma found
    it, the agent didn't curate it; either noise or extra coverage).
    ``recall`` = |A∩B| / |A|, or ``0.0`` when Track A is empty.
    """

    threshold: float
    track_a_size: int
    track_b_size: int
    intersection: list[EvalRecord]
    a_only: list[EvalRecord]
    b_only: list[EvalRecord]

    @property
    def recall(self) -> float:
        if self.track_a_size == 0:
            return 0.0
        return len(self.intersection) / self.track_a_size


def _best_overlap(body: str, candidates: list[EvalRecord]) -> float:
    """Return the max word-overlap of ``body`` against any candidate body."""
    best = 0.0
    for candidate in candidates:
        score = _compute_overlap(body, candidate.body)
        if score > best:
            best = score
    return best


def compare_tracks(
    track_a: list[EvalRecord],
    track_b: list[EvalRecord],
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> RecallReport:
    """Compare native Track A against extracted Track B at ``threshold``.

    For each A record, find its best-matching B record by word overlap; >=
    threshold counts as a match (A∩B), otherwise A−B. B records that match no
    A record (best overlap < threshold against the A set) are B−A.
    """
    intersection: list[EvalRecord] = []
    a_only: list[EvalRecord] = []
    for a_record in track_a:
        if _best_overlap(a_record.body, track_b) >= threshold:
            intersection.append(a_record)
        else:
            a_only.append(a_record)

    b_only = [
        b_record
        for b_record in track_b
        if _best_overlap(b_record.body, track_a) < threshold
    ]

    return RecallReport(
        threshold=threshold,
        track_a_size=len(track_a),
        track_b_size=len(track_b),
        intersection=intersection,
        a_only=a_only,
        b_only=b_only,
    )


@dataclass(frozen=True)
class EvalResult:
    """Top-level result returned by ``run_eval`` for both renderers to consume.

    ``report`` is ``None`` only when Track A is empty (no native memory yet) —
    the CLI uses that to print the "run harvest first" guidance.
    """

    report: RecallReport | None
    track_a: list[EvalRecord] = field(default_factory=list[EvalRecord])
    track_b: list[EvalRecord] = field(default_factory=list[EvalRecord])


def run_eval(
    repo_root: Path,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    include_pending: bool = True,
) -> EvalResult:
    """Load, bucket, and compare in one call.

    Returns an ``EvalResult``. When Track A is empty its ``report`` is ``None``
    so callers can emit the harvest-first message instead of a zero-denominator
    recall.
    """
    records = load_records(repo_root, include_pending=include_pending)
    track_a, track_b = bucket_records(records)
    if not track_a:
        return EvalResult(report=None, track_a=track_a, track_b=track_b)
    report = compare_tracks(track_a, track_b, threshold=threshold)
    return EvalResult(report=report, track_a=track_a, track_b=track_b)


__all__ = [
    "AUTO_EXTRACTION_SOURCE",
    "DEFAULT_THRESHOLD",
    "NATIVE_SOURCE_PREFIX",
    "EvalRecord",
    "EvalResult",
    "RecallReport",
    "bucket_records",
    "compare_tracks",
    "load_records",
    "run_eval",
]
