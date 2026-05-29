"""Tests for the Claude Code native-memory reader/harvester."""

from __future__ import annotations

from pathlib import Path

import pytest
from spanweave.harvest.claude import (
    claude_memory_dir,
    encode_cwd,
    harvest_claude_memory,
    read_claude_records,
)

_FEEDBACK_RECORD = """\
---
title: Use project-local tmp/ not /tmp
type: feedback
tags: [workflow, conventions]
scope: project
created: 2026-05-28
---

User feedback captured during a session.

## The lesson

Always write ephemeral artifacts to a project-local tmp/ directory.
"""

_PROJECT_RECORD = """\
---
name: Memory-capture MVP direction
metadata:
  node_type: memory
  type: project
tags: [memory, architecture]
---

User-stated product direction for memory capture.

## The direction

Harvest the coding agents' own native memory into the shared layer.
"""


def _write_claude_memory(home: Path, repo: Path, name: str, content: str) -> Path:
    """Create a fake Claude native-memory record under the encoded-cwd dir."""
    memory_dir = home / ".claude" / "projects" / encode_cwd(repo) / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    path = memory_dir / name
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point Path.home() at a tmp dir so no real ~/.claude is touched."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


def test_encode_cwd_replaces_slashes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert encode_cwd(repo) == str(repo.resolve()).replace("/", "-")


def test_claude_memory_dir_uses_encoded_cwd(fake_home: Path, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    expected = fake_home / ".claude" / "projects" / encode_cwd(repo) / "memory"
    assert claude_memory_dir(repo) == expected


def test_read_claude_records_parses_frontmatter(fake_home: Path, tmp_path: Path) -> None:
    """A record preserves its body, tags, and a valid native type."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_claude_memory(fake_home, repo, "feedback.md", _FEEDBACK_RECORD)

    records = read_claude_records(repo)

    assert len(records) == 1
    record = records[0]
    assert record["type"] == "feedback" or record["type"] == "finding"
    assert "project-local tmp/" in record["body"]
    # Title folded into the body as a heading so it survives staging.
    assert "Use project-local tmp/ not /tmp" in record["body"]
    assert "workflow" in record["tags"]
    assert record["confidence"] == 1.0


def test_read_claude_records_skips_memory_index(fake_home: Path, tmp_path: Path) -> None:
    """The MEMORY.md index file is not imported as a record."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_claude_memory(fake_home, repo, "MEMORY.md", "# Memory Index\n\n- a\n- b\n")
    _write_claude_memory(fake_home, repo, "feedback.md", _FEEDBACK_RECORD)

    records = read_claude_records(repo)

    assert len(records) == 1
    assert all("Memory Index" not in r["body"] for r in records)


def test_read_claude_records_normalizes_unknown_type(
    fake_home: Path, tmp_path: Path
) -> None:
    """A native type outside the review whitelist -> 'finding', preserved as tag."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_claude_memory(fake_home, repo, "project.md", _PROJECT_RECORD)

    records = read_claude_records(repo)

    assert len(records) == 1
    # 'project' (read from nested metadata.type) is not a valid review type.
    assert records[0]["type"] == "finding"
    assert "native-type:project" in records[0]["tags"]


def test_harvest_claude_stages_with_source(fake_home: Path, tmp_path: Path) -> None:
    """harvest_claude_memory stages records with source: native-claude."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_claude_memory(fake_home, repo, "feedback.md", _FEEDBACK_RECORD)

    paths = harvest_claude_memory(repo)

    assert len(paths) == 1
    content = paths[0].read_text(encoding="utf-8")
    assert "source: native-claude" in content
    assert paths[0].parent == repo / ".spanweave" / "memory" / "pending" / "decisions"


def test_harvest_claude_no_memory_dir_is_noop(fake_home: Path, tmp_path: Path) -> None:
    """Missing memory dir yields no records (graceful no-op)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    assert harvest_claude_memory(repo) == []


def test_harvest_claude_is_idempotent(fake_home: Path, tmp_path: Path) -> None:
    """Harvesting twice does not duplicate records (dedup by body)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_claude_memory(fake_home, repo, "feedback.md", _FEEDBACK_RECORD)

    first = harvest_claude_memory(repo)
    second = harvest_claude_memory(repo)

    assert len(first) == 1
    assert second == []
