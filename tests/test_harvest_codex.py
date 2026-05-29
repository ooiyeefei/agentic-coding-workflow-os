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
        fake_home, summary=None, rollouts={"session-x.md": _ROLLOUT_SUMMARY}
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
    _write_codex_memory(
        fake_home, summary=_MEMORY_SUMMARY, rollouts={"x.md": _ROLLOUT_SUMMARY}
    )

    first = harvest_codex_memory(repo)
    second = harvest_codex_memory(repo)

    assert len(first) == 2
    assert second == []
