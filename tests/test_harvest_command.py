"""Tests for the ``spanweave harvest`` CLI command."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from spanweave.cli.commands.harvest import harvest_command
from spanweave.harvest.claude import encode_cwd

_CLAUDE_RECORD = """\
---
title: Claude remembered this
type: feedback
tags: [workflow]
scope: project
created: 2026-05-28
---

User feedback.

## The lesson

Use project-local tmp/ for ephemeral artifacts on this user's projects.
"""

_CODEX_ROLLOUT = """\
## Task 1

Codex remembered this rollout summary about a deploy debugging session.

## Key steps

- Reproduced the failure, then fixed the DNS misconfiguration.
"""


def _write_claude(home: Path, repo: Path) -> None:
    memory_dir = home / ".claude" / "projects" / encode_cwd(repo) / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "feedback.md").write_text(_CLAUDE_RECORD, encoding="utf-8")


def _write_codex(home: Path) -> None:
    rollout_dir = home / ".codex" / "memories" / "rollout_summaries"
    rollout_dir.mkdir(parents=True, exist_ok=True)
    (rollout_dir / "session.md").write_text(_CODEX_ROLLOUT, encoding="utf-8")


def _pending_bodies(repo: Path) -> list[str]:
    pending = repo / ".spanweave" / "memory" / "pending" / "decisions"
    if not pending.exists():
        return []
    return [p.read_text(encoding="utf-8") for p in sorted(pending.glob("*.md"))]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


def test_harvest_tool_claude_only(runner: CliRunner, fake_home: Path, tmp_path: Path) -> None:
    """``--tool claude-code`` harvests Claude memory but not Codex."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_claude(fake_home, repo)
    _write_codex(fake_home)

    result = runner.invoke(harvest_command, ["--tool", "claude-code", "--repo", str(repo)])

    assert result.exit_code == 0, result.output
    bodies = _pending_bodies(repo)
    assert any("source: native-claude" in b for b in bodies)
    assert all("source: native-codex" not in b for b in bodies)


def test_harvest_default_both_tools(runner: CliRunner, fake_home: Path, tmp_path: Path) -> None:
    """With no ``--tool`` flag, both available tools are harvested."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_claude(fake_home, repo)
    _write_codex(fake_home)

    result = runner.invoke(harvest_command, ["--repo", str(repo)])

    assert result.exit_code == 0, result.output
    bodies = _pending_bodies(repo)
    assert any("source: native-claude" in b for b in bodies)
    assert any("source: native-codex" in b for b in bodies)


def test_harvest_codex_only(runner: CliRunner, fake_home: Path, tmp_path: Path) -> None:
    """``--tool codex`` harvests Codex memory but not Claude."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_claude(fake_home, repo)
    _write_codex(fake_home)

    result = runner.invoke(harvest_command, ["--tool", "codex", "--repo", str(repo)])

    assert result.exit_code == 0, result.output
    bodies = _pending_bodies(repo)
    assert any("source: native-codex" in b for b in bodies)
    assert all("source: native-claude" not in b for b in bodies)


def test_harvest_is_idempotent(runner: CliRunner, fake_home: Path, tmp_path: Path) -> None:
    """Running harvest twice does not duplicate pending records."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_claude(fake_home, repo)
    _write_codex(fake_home)

    runner.invoke(harvest_command, ["--repo", str(repo)])
    count_after_first = len(_pending_bodies(repo))
    second = runner.invoke(harvest_command, ["--repo", str(repo)])
    count_after_second = len(_pending_bodies(repo))

    assert second.exit_code == 0, second.output
    assert count_after_first == count_after_second
    assert count_after_first >= 2  # one Claude + one Codex


def test_harvest_no_native_memory_is_graceful(
    runner: CliRunner, fake_home: Path, tmp_path: Path
) -> None:
    """A repo with no native memory at all exits 0 with a clear message."""
    repo = tmp_path / "repo"
    repo.mkdir()

    result = runner.invoke(harvest_command, ["--repo", str(repo)])

    assert result.exit_code == 0, result.output
    assert "No native memory" in result.output


def test_harvest_summary_mentions_pending(
    runner: CliRunner, fake_home: Path, tmp_path: Path
) -> None:
    """The command prints a per-tool harvested-count summary."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_claude(fake_home, repo)

    result = runner.invoke(harvest_command, ["--tool", "claude-code", "--repo", str(repo)])

    assert result.exit_code == 0, result.output
    assert "claude-code" in result.output
    assert "pending" in result.output


def test_harvest_requested_tool_without_store_is_graceful(
    runner: CliRunner, fake_home: Path, tmp_path: Path
) -> None:
    """Explicitly requesting a tool with no native store exits 0, says skipped."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # No Codex store created.

    result = runner.invoke(harvest_command, ["--tool", "codex", "--repo", str(repo)])

    assert result.exit_code == 0, result.output
    assert "No codex native memory found" in result.output
