"""Unit tests for the dual-track recall-compare logic (spanweave.eval.recall)."""

from __future__ import annotations

from pathlib import Path

from spanweave.eval.recall import (
    bucket_records,
    compare_tracks,
    load_records,
    run_eval,
)


def _write_record(
    repo_root: Path,
    *,
    subdir: str,
    name: str,
    source: str,
    body: str,
    record_type: str = "decision",
) -> Path:
    """Write a memory record file with frontmatter + body under memory/<subdir>."""
    target_dir = repo_root / ".spanweave" / "memory" / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "---\n"
        f"type: {record_type}\n"
        f"source: {source}\n"
        "confidence: 0.9\n"
        "reasoning: test\n"
        "timestamp: 2026-01-01T00:00:00Z\n"
        "tags: []\n"
        "---\n"
        f"{body}\n"
    )
    path = target_dir / name
    path.write_text(content, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Bucketing
# --------------------------------------------------------------------------- #


def test_bucketing_routes_native_to_a_and_auto_extraction_to_b(tmp_path: Path) -> None:
    _write_record(
        tmp_path,
        subdir="decisions",
        name="a_claude.md",
        source="native-claude",
        body="use byte offset watermark for delta extraction",
    )
    _write_record(
        tmp_path,
        subdir="decisions",
        name="a_codex.md",
        source="native-codex",
        body="prefer project local tmp directory over system tmp",
    )
    _write_record(
        tmp_path,
        subdir="pending/decisions",
        name="b_auto.md",
        source="auto-extraction",
        body="store memory as markdown with yaml frontmatter",
    )

    records = load_records(tmp_path, include_pending=True)
    track_a, track_b = bucket_records(records)

    a_sources = sorted(r.source for r in track_a)
    b_sources = sorted(r.source for r in track_b)
    assert a_sources == ["native-claude", "native-codex"]
    assert b_sources == ["auto-extraction"]


def test_bucketing_ignores_other_sources(tmp_path: Path) -> None:
    """A non-native, non-auto source (e.g. seed) lands in neither track."""
    _write_record(
        tmp_path,
        subdir="decisions",
        name="seed.md",
        source="seed",
        body="seeded baseline decision body",
    )

    records = load_records(tmp_path, include_pending=True)
    track_a, track_b = bucket_records(records)

    assert track_a == []
    assert track_b == []


# --------------------------------------------------------------------------- #
# Comparison buckets + recall
# --------------------------------------------------------------------------- #


def test_near_identical_body_counts_as_intersection_and_recall(tmp_path: Path) -> None:
    shared_body = "always run ruff check before committing python changes to the repo"
    _write_record(
        tmp_path,
        subdir="decisions",
        name="a.md",
        source="native-claude",
        body=shared_body,
    )
    _write_record(
        tmp_path,
        subdir="pending/decisions",
        name="b.md",
        source="auto-extraction",
        # Same substance, slightly reworded — high word overlap.
        body="always run ruff check before committing python changes here",
    )

    result = run_eval(tmp_path, threshold=0.5, include_pending=True)
    assert result.report is not None
    report = result.report

    assert len(report.intersection) == 1
    assert report.a_only == []
    assert report.recall == 1.0


def test_a_record_with_no_similar_b_is_a_only(tmp_path: Path) -> None:
    _write_record(
        tmp_path,
        subdir="decisions",
        name="a.md",
        source="native-claude",
        body="adopt hexagonal architecture for the payments service boundary",
    )
    _write_record(
        tmp_path,
        subdir="pending/decisions",
        name="b.md",
        source="auto-extraction",
        body="bump the docker base image to python 3.12 slim",
    )

    report = run_eval(tmp_path, threshold=0.5, include_pending=True).report
    assert report is not None
    assert len(report.a_only) == 1
    assert report.intersection == []
    assert report.recall == 0.0


def test_b_record_with_no_similar_a_is_b_only(tmp_path: Path) -> None:
    _write_record(
        tmp_path,
        subdir="decisions",
        name="a.md",
        source="native-claude",
        body="adopt hexagonal architecture for the payments service boundary",
    )
    _write_record(
        tmp_path,
        subdir="pending/decisions",
        name="b.md",
        source="auto-extraction",
        body="bump the docker base image to python 3.12 slim",
    )

    report = run_eval(tmp_path, threshold=0.5, include_pending=True).report
    assert report is not None
    assert len(report.b_only) == 1


def test_threshold_changes_matching(tmp_path: Path) -> None:
    """A partial overlap matches at a low threshold but not at a high one."""
    _write_record(
        tmp_path,
        subdir="decisions",
        name="a.md",
        source="native-claude",
        body="cache the compiled regular expression for the grep command",
    )
    _write_record(
        tmp_path,
        subdir="pending/decisions",
        name="b.md",
        source="auto-extraction",
        # Shares several words ("cache", "the", "compiled", "regular",
        # "expression") but not all — overlap sits between the two thresholds.
        body="cache the compiled regular expression results elsewhere now",
    )

    low = compare_tracks(*bucket_records(load_records(tmp_path)), threshold=0.3)
    high = compare_tracks(*bucket_records(load_records(tmp_path)), threshold=0.95)

    assert len(low.intersection) == 1
    assert low.recall == 1.0
    assert len(high.intersection) == 0
    assert len(high.a_only) == 1


def test_empty_track_a_returns_no_report(tmp_path: Path) -> None:
    """No native records -> run_eval signals empty A via report=None."""
    _write_record(
        tmp_path,
        subdir="pending/decisions",
        name="b.md",
        source="auto-extraction",
        body="only an extracted decision exists here, no native curation",
    )

    result = run_eval(tmp_path, include_pending=True)
    assert result.report is None
    assert len(result.track_b) == 1


def test_include_pending_toggle_excludes_pending_records(tmp_path: Path) -> None:
    _write_record(
        tmp_path,
        subdir="decisions",
        name="a.md",
        source="native-claude",
        body="confirmed native decision in decisions dir",
    )
    _write_record(
        tmp_path,
        subdir="pending/decisions",
        name="b_pending.md",
        source="auto-extraction",
        body="pending extracted decision not yet reviewed",
    )

    with_pending = bucket_records(load_records(tmp_path, include_pending=True))
    without_pending = bucket_records(load_records(tmp_path, include_pending=False))

    # Track B (the auto-extraction record) only lives in pending/ here.
    assert len(with_pending[1]) == 1
    assert without_pending[1] == []


def test_confirmed_shared_records_are_loaded(tmp_path: Path) -> None:
    """Records under shared/** are discovered even with pending excluded."""
    _write_record(
        tmp_path,
        subdir="shared/decisions",
        name="a_shared.md",
        source="native-codex",
        body="shared native decision promoted for the team",
    )

    track_a, _ = bucket_records(load_records(tmp_path, include_pending=False))
    assert len(track_a) == 1
    assert track_a[0].source == "native-codex"


def test_empty_body_records_are_dropped_from_buckets(tmp_path: Path) -> None:
    _write_record(
        tmp_path,
        subdir="decisions",
        name="a_empty.md",
        source="native-claude",
        body="",
    )

    track_a, _ = bucket_records(load_records(tmp_path))
    assert track_a == []
