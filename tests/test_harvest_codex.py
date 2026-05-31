"""Tests for the Codex native-memory reader/harvester."""

from __future__ import annotations

from pathlib import Path

import pytest
from spanweave.harvest.codex import (
    codex_memory_dir,
    harvest_codex_memory,
    read_codex_records,
)

_ROLLOUT_SUMMARY = """\
## Task 1

Implemented the harvest command for native memory.

## Preference signals

User prefers TDD and project-local tmp/.

## Key steps

- Read the extractor module.
- Wrote failing tests first.
"""

_MEMORY_SUMMARY = """\
# Codex memory summary

Across recent sessions the user worked on Spanweave, a tool-agnostic memory
layer. Key themes: TDD discipline and CPU-only EC2 constraints.
"""


def _rollout_with_cwd(cwd: str, body: str) -> str:
    """A rollout summary file as Codex writes it: bare `key: value` frontmatter
    (no `---` fences) that includes a `cwd:` line, then a blank line and prose."""
    return (
        f"thread_id: 019deadbeef\n"
        f"updated_at: 2026-05-20T00:00:00+00:00\n"
        f"cwd: {cwd}\n"
        f"git_branch: main\n"
        f"\n"
        f"{body}\n"
    )


def _write_codex_memory(
    home: Path, *, summary: str | None, rollouts: dict[str, str]
) -> None:
    """Create a fake Codex native-memory store under a fake home."""
    memories = home / ".codex" / "memories"
    rollout_dir = memories / "rollout_summaries"
    rollout_dir.mkdir(parents=True, exist_ok=True)
    if summary is not None:
        (memories / "memory_summary.md").write_text(summary, encoding="utf-8")
    for name, content in rollouts.items():
        (rollout_dir / name).write_text(content, encoding="utf-8")


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


def test_codex_memory_dir_resolves_under_home(fake_home: Path) -> None:
    assert codex_memory_dir() == fake_home / ".codex" / "memories"


def test_read_codex_records_from_rollout(fake_home: Path) -> None:
    """A rollout summary file becomes a finding record with provenance."""
    _write_codex_memory(fake_home, summary=None, rollouts={"session-x.md": _ROLLOUT_SUMMARY})

    records = read_codex_records()

    assert len(records) == 1
    record = records[0]
    assert record["type"] == "finding"
    # The summary content is captured in the body.
    assert "harvest command" in record["body"]
    # Provenance: a pointer back to the source file path is present.
    assert "session-x.md" in record["body"]
    assert any("session-x.md" in tag for tag in record["tags"])


def test_read_codex_records_includes_summary(fake_home: Path) -> None:
    """The top-level memory_summary.md is also imported, with provenance."""
    _write_codex_memory(fake_home, summary=_MEMORY_SUMMARY, rollouts={})

    records = read_codex_records()

    assert len(records) == 1
    assert "tool-agnostic memory" in records[0]["body"]
    assert "memory_summary.md" in records[0]["body"]


def test_harvest_codex_stages_with_source(fake_home: Path, tmp_path: Path) -> None:
    """harvest_codex_memory stages records with source: native-codex."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_codex_memory(
        fake_home,
        summary=None,
        rollouts={
            "session-x.md": _rollout_with_cwd(str(repo.resolve()), _ROLLOUT_SUMMARY)
        },
    )

    paths = harvest_codex_memory(repo)

    assert len(paths) == 1
    content = paths[0].read_text(encoding="utf-8")
    assert "source: native-codex" in content
    assert "session-x.md" in content


def test_harvest_codex_no_memory_dir_is_noop(fake_home: Path, tmp_path: Path) -> None:
    """Missing Codex memory dir yields no records (graceful no-op)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    assert harvest_codex_memory(repo) == []


def test_harvest_codex_is_idempotent(fake_home: Path, tmp_path: Path) -> None:
    """Harvesting twice does not duplicate Codex records."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # cwd matches the repo so the rollout survives default (scoped) harvest;
    # all_projects pulls in the cross-project memory_summary too.
    _write_codex_memory(
        fake_home,
        summary=_MEMORY_SUMMARY,
        rollouts={"x.md": _rollout_with_cwd(str(repo.resolve()), _ROLLOUT_SUMMARY)},
    )

    first = harvest_codex_memory(repo, all_projects=True)
    second = harvest_codex_memory(repo, all_projects=True)

    assert len(first) == 2
    assert second == []


# --- project scoping by cwd (issue: Codex is a single GLOBAL store) ---------


def _write_scoped_tree(home: Path) -> None:
    """Two rollouts for /repo/A, one for /repo/B, plus a memory_summary."""
    _write_codex_memory(
        home,
        summary=_MEMORY_SUMMARY,
        rollouts={
            "a1.md": _rollout_with_cwd(
                "/repo/A", "Decided to use pydantic for config."
            ),
            "a2.md": _rollout_with_cwd("/repo/A", "Switched CI to GitHub Actions."),
            "b1.md": _rollout_with_cwd("/repo/B", "Unrelated other-project note."),
        },
    )


def test_scoped_read_includes_only_matching_cwd(fake_home: Path) -> None:
    """read_codex_records(repo) returns only rollouts whose cwd == repo."""
    _write_scoped_tree(fake_home)

    records = read_codex_records(Path("/repo/A"))

    bodies = "\n".join(r["body"] for r in records)
    assert "pydantic for config" in bodies
    assert "GitHub Actions" in bodies
    # /repo/B and the cross-project memory_summary are excluded.
    assert "other-project note" not in bodies
    assert "tool-agnostic memory" not in bodies
    assert len(records) == 2


def test_scoped_read_resolves_repo_root(fake_home: Path, tmp_path: Path) -> None:
    """Scoping matches on the *resolved* absolute path of repo_root."""
    repo = tmp_path / "proj"
    repo.mkdir()
    _write_codex_memory(
        fake_home,
        summary=None,
        rollouts={
            "here.md": _rollout_with_cwd(str(repo.resolve()), "In-project note."),
            "there.md": _rollout_with_cwd("/repo/elsewhere", "Elsewhere note."),
        },
    )

    records = read_codex_records(repo)

    bodies = "\n".join(r["body"] for r in records)
    assert "In-project note" in bodies
    assert "Elsewhere note" not in bodies
    assert len(records) == 1


def test_all_read_includes_everything(fake_home: Path) -> None:
    """Unscoped (repo_root=None) returns all rollouts + the memory_summary."""
    _write_scoped_tree(fake_home)

    records = read_codex_records()

    bodies = "\n".join(r["body"] for r in records)
    assert "pydantic for config" in bodies
    assert "GitHub Actions" in bodies
    assert "other-project note" in bodies
    assert "tool-agnostic memory" in bodies  # the cross-project summary
    assert len(records) == 4


def test_scoped_excludes_summary_with_no_cwd(fake_home: Path) -> None:
    """A rollout summary lacking a cwd line is excluded from the scoped view,
    but is included when unscoped (--all)."""
    _write_codex_memory(
        fake_home,
        summary=None,
        rollouts={
            "ok.md": _rollout_with_cwd("/repo/A", "In-project note."),
            "nocwd.md": (
                "thread_id: 019nocwd\nupdated_at: 2026-05-20T00:00:00+00:00\n"
                "git_branch: main\n\nSummary that lacks a cwd line.\n"
            ),
        },
    )

    scoped = read_codex_records(Path("/repo/A"))
    scoped_bodies = "\n".join(r["body"] for r in scoped)
    assert "In-project note" in scoped_bodies
    assert "lacks a cwd line" not in scoped_bodies
    assert len(scoped) == 1

    unscoped = read_codex_records()
    unscoped_bodies = "\n".join(r["body"] for r in unscoped)
    assert "lacks a cwd line" in unscoped_bodies


def test_scoped_reasoning_carries_cwd_provenance(fake_home: Path) -> None:
    """The cwd provenance is annotated in the record's reasoning."""
    _write_scoped_tree(fake_home)

    records = read_codex_records(Path("/repo/A"))

    assert records
    assert all("/repo/A" in r["reasoning"] for r in records)


def test_harvest_scoped_stages_only_matching(
    fake_home: Path, tmp_path: Path
) -> None:
    """harvest --tool codex --repo A stages only A's records (default scoped)."""
    repo = tmp_path / "A"
    repo.mkdir()
    # Distinct prose so the word-overlap dedup keeps both A records.
    _write_codex_memory(
        fake_home,
        summary=_MEMORY_SUMMARY,
        rollouts={
            "a1.md": _rollout_with_cwd(
                str(repo.resolve()), "Adopted pydantic-settings for config loading."
            ),
            "a2.md": _rollout_with_cwd(
                str(repo.resolve()), "Migrated the CI pipeline onto GitHub Actions."
            ),
            "b1.md": _rollout_with_cwd(
                "/repo/B", "Refactored the billing webhook handler."
            ),
        },
    )

    paths = harvest_codex_memory(repo)

    assert len(paths) == 2
    staged = "\n".join(p.read_text(encoding="utf-8") for p in paths)
    assert "pydantic-settings" in staged
    assert "GitHub Actions" in staged
    assert "billing webhook" not in staged
    assert "tool-agnostic memory" not in staged  # summary excluded when scoped


def test_harvest_all_stages_everything(fake_home: Path, tmp_path: Path) -> None:
    """harvest --tool codex --repo A --all stages all projects + the summary."""
    repo = tmp_path / "A"
    repo.mkdir()
    _write_codex_memory(
        fake_home,
        summary=_MEMORY_SUMMARY,
        rollouts={
            "a1.md": _rollout_with_cwd(
                str(repo.resolve()), "Adopted pydantic-settings for config loading."
            ),
            "b1.md": _rollout_with_cwd(
                "/repo/B", "Refactored the billing webhook handler."
            ),
        },
    )

    paths = harvest_codex_memory(repo, all_projects=True)

    # 2 rollouts + 1 memory_summary
    assert len(paths) == 3
    staged = "\n".join(p.read_text(encoding="utf-8") for p in paths)
    assert "pydantic-settings" in staged
    assert "billing webhook" in staged
    assert "tool-agnostic memory" in staged


# --- --since recency filter (#116) ------------------------------------------


def _rollout_dated(cwd: str, body: str, *, updated_at: str | None) -> str:
    """A rollout summary with an optional ``updated_at`` frontmatter line.

    When ``updated_at`` is None the line is omitted entirely, so the reader
    must fall back to the date-prefixed filename.
    """
    lines = ["thread_id: 019deadbeef"]
    if updated_at is not None:
        lines.append(f"updated_at: {updated_at}")
    lines += [f"cwd: {cwd}", "git_branch: main", "", body, ""]
    return "\n".join(lines)


def _write_dated_tree(home: Path) -> None:
    """Three same-cwd (/repo/A) rollouts dated 05-07, 05-15, 05-25.

    Both the ``updated_at`` frontmatter and the date-prefixed filename carry
    the date, so either source resolves to the same day. Distinct prose keeps
    the word-overlap dedup from collapsing them.
    """
    _write_codex_memory(
        home,
        summary=None,
        rollouts={
            "2026-05-07T09-14-22-old.md": _rollout_dated(
                "/repo/A",
                "Adopted pydantic-settings for config loading.",
                updated_at="2026-05-07T09:14:30+00:00",
            ),
            "2026-05-15T12-15-13-mid.md": _rollout_dated(
                "/repo/A",
                "Migrated the CI pipeline onto GitHub Actions runners.",
                updated_at="2026-05-15T12:15:35+00:00",
            ),
            "2026-05-25T08-00-00-new.md": _rollout_dated(
                "/repo/A",
                "Refactored the billing webhook retry handler thoroughly.",
                updated_at="2026-05-25T08:00:01+00:00",
            ),
        },
    )


def test_since_filters_out_older_than_date(fake_home: Path) -> None:
    """since=2026-05-20 keeps only the 05-25 session."""
    _write_dated_tree(fake_home)

    records = read_codex_records(Path("/repo/A"), since="2026-05-20")

    bodies = "\n".join(r["body"] for r in records)
    assert "billing webhook" in bodies
    assert "pydantic-settings" not in bodies
    assert "GitHub Actions" not in bodies
    assert len(records) == 1


def test_since_is_inclusive_on_boundary(fake_home: Path) -> None:
    """since=2026-05-15 keeps the 05-15 (boundary) and 05-25 sessions."""
    _write_dated_tree(fake_home)

    records = read_codex_records(Path("/repo/A"), since="2026-05-15")

    bodies = "\n".join(r["body"] for r in records)
    assert "GitHub Actions" in bodies  # 05-15 boundary is inclusive
    assert "billing webhook" in bodies  # 05-25
    assert "pydantic-settings" not in bodies  # 05-07 excluded
    assert len(records) == 2


def test_since_none_returns_all(fake_home: Path) -> None:
    """since=None is the current behavior: no date filtering."""
    _write_dated_tree(fake_home)

    records = read_codex_records(Path("/repo/A"), since=None)

    assert len(records) == 3


def test_since_falls_back_to_filename_date(fake_home: Path) -> None:
    """With no updated_at frontmatter, the leading filename date is used."""
    _write_codex_memory(
        fake_home,
        summary=None,
        rollouts={
            "2026-05-25T08-00-00-fname.md": _rollout_dated(
                "/repo/A",
                "Refactored the billing webhook retry handler thoroughly.",
                updated_at=None,
            ),
            "2026-05-01T00-00-00-old.md": _rollout_dated(
                "/repo/A",
                "Adopted pydantic-settings for config loading.",
                updated_at=None,
            ),
        },
    )

    records = read_codex_records(Path("/repo/A"), since="2026-05-20")

    bodies = "\n".join(r["body"] for r in records)
    assert "billing webhook" in bodies  # 05-25 from filename
    assert "pydantic-settings" not in bodies  # 05-01 from filename, excluded
    assert len(records) == 1


def test_since_excludes_undateable_record(fake_home: Path) -> None:
    """A summary with neither updated_at nor a date-prefixed filename is
    excluded once since is set (cannot prove it is recent)."""
    _write_codex_memory(
        fake_home,
        summary=None,
        rollouts={
            "2026-05-25T08-00-00-new.md": _rollout_dated(
                "/repo/A",
                "Refactored the billing webhook retry handler thoroughly.",
                updated_at="2026-05-25T08:00:01+00:00",
            ),
            "no-date-here.md": _rollout_dated(
                "/repo/A",
                "Adopted pydantic-settings for config loading.",
                updated_at=None,
            ),
        },
    )

    records = read_codex_records(Path("/repo/A"), since="2026-05-20")

    bodies = "\n".join(r["body"] for r in records)
    assert "billing webhook" in bodies
    assert "pydantic-settings" not in bodies  # undateable → excluded
    assert len(records) == 1


def test_since_excludes_cross_project_summary(fake_home: Path) -> None:
    """The cross-project memory_summary.md has no single date → excluded
    whenever since is set, even in all-projects (repo_root=None) mode."""
    _write_dated_tree(fake_home)
    memories = fake_home / ".codex" / "memories"
    (memories / "memory_summary.md").write_text(_MEMORY_SUMMARY, encoding="utf-8")

    records = read_codex_records(None, since="2026-05-01")

    bodies = "\n".join(r["body"] for r in records)
    assert "tool-agnostic memory" not in bodies  # summary excluded
    # The three dated rollouts are all on/after 05-01.
    assert len(records) == 3


def test_harvest_codex_memory_threads_since(
    fake_home: Path, tmp_path: Path
) -> None:
    """harvest_codex_memory(repo, since=...) only stages recent sessions."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_codex_memory(
        fake_home,
        summary=None,
        rollouts={
            "2026-05-07T00-00-00-old.md": _rollout_dated(
                str(repo.resolve()),
                "Adopted pydantic-settings for config loading.",
                updated_at="2026-05-07T00:00:00+00:00",
            ),
            "2026-05-25T00-00-00-new.md": _rollout_dated(
                str(repo.resolve()),
                "Refactored the billing webhook retry handler thoroughly.",
                updated_at="2026-05-25T00:00:00+00:00",
            ),
        },
    )

    paths = harvest_codex_memory(repo, since="2026-05-20")

    assert len(paths) == 1
    staged = paths[0].read_text(encoding="utf-8")
    assert "billing webhook" in staged
    assert "pydantic-settings" not in staged
