"""Tests for `spanweave init --tool` and `spanweave extract-latest`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from spanweave.cli.main import main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings_json(repo: Path) -> dict[str, Any]:
    """Read and parse .claude/settings.json from the repo."""
    result: dict[str, Any] = json.loads(
        (repo / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    return result


def _stop_hook_commands(settings: dict[str, Any]) -> list[str]:
    """Extract command strings from hooks.Stop, validating the schema shape.

    Claude Code requires each Stop entry to be a matcher-block with a nested
    ``hooks`` array: ``{"matcher": "", "hooks": [{"type": "command", ...}]}``.
    This helper asserts that shape (the bug /doctor caught was a flat entry
    missing the ``hooks`` wrapper) and returns the inner command strings.
    """
    blocks: list[dict[str, Any]] = settings["hooks"]["Stop"]
    commands: list[str] = []
    for block in blocks:
        assert "hooks" in block, f"Stop entry missing 'hooks' array: {block!r}"
        assert isinstance(block["hooks"], list)
        for inner in block["hooks"]:
            assert inner.get("type") == "command"
            commands.append(inner["command"])
    return commands


# ---------------------------------------------------------------------------
# Claude Code hook tests
# ---------------------------------------------------------------------------


class TestInitToolClaudeCode:
    def test_creates_settings_with_hook(self, tmp_path: Path) -> None:
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        settings = _settings_json(tmp_path)
        assert "hooks" in settings
        assert "Stop" in settings["hooks"]
        hook_commands = _stop_hook_commands(settings)
        # Tolerant of invocation form (plain vs .venv/bin) — tmp_path has no venv
        # so it resolves to the plain command here.
        assert any(c.endswith("extract-latest --repo .") for c in hook_commands)
        assert "Claude Code Stop hook wired" in result.output

    def test_preserves_existing_settings(self, tmp_path: Path) -> None:
        # Pre-populate with existing settings
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        existing = {
            "permissions": {"allow": ["bash(git *)"]},
            "env": {"FOO": "bar"},
        }
        (claude_dir / "settings.json").write_text(
            json.dumps(existing, indent=2), encoding="utf-8"
        )
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        settings = _settings_json(tmp_path)
        # Existing keys preserved
        assert settings["permissions"] == {"allow": ["bash(git *)"]}
        assert settings["env"] == {"FOO": "bar"}
        # Hook added
        hook_commands = _stop_hook_commands(settings)
        assert any(c.endswith("extract-latest --repo .") for c in hook_commands)

    def test_is_idempotent(self, tmp_path: Path) -> None:
        runner = CliRunner()

        runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])
        runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])

        settings = _settings_json(tmp_path)
        hook_commands = _stop_hook_commands(settings)
        # Only one spanweave extract-latest hook regardless of invocation form
        extract_hooks = [c for c in hook_commands if c.endswith("extract-latest --repo .")]
        assert len(extract_hooks) == 1

    def test_uses_venv_binary_when_present(self, tmp_path: Path) -> None:
        """When a repo-local venv exists, the hook must point at its binary.

        The bare /bin/sh that Claude Code uses for Stop hooks has neither the
        venv nor `uv` on PATH, so a plain `spanweave` command fails with
        "not found". A repo-relative `.venv/bin/spanweave` path works because
        hooks run with cwd = project root.
        """
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "spanweave").write_text("#!/bin/sh\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        hook_commands = _stop_hook_commands(_settings_json(tmp_path))
        assert ".venv/bin/spanweave extract-latest --repo ." in hook_commands

    def test_self_heals_stale_plain_command(self, tmp_path: Path) -> None:
        """Re-running init upgrades a stale bare-`spanweave` hook in place.

        Simulates a user bitten by the pre-fix bug (plain `spanweave` that
        fails in the bare hook shell): the broken command is replaced with the
        venv-resolved one rather than duplicated or left broken.
        """
        # Pre-populate with the old, broken hook command
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        stale = {
            "hooks": {
                "Stop": [
                    {
                        "matcher": "",
                        "hooks": [
                            {"type": "command", "command": "spanweave extract-latest --repo ."}
                        ],
                    }
                ]
            }
        }
        (claude_dir / "settings.json").write_text(json.dumps(stale, indent=2), encoding="utf-8")
        # Give the repo a venv so the resolver upgrades to the venv path
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "spanweave").write_text("#!/bin/sh\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        hook_commands = _stop_hook_commands(_settings_json(tmp_path))
        # Upgraded in place — exactly one hook, now pointing at the venv binary
        assert hook_commands == [".venv/bin/spanweave extract-latest --repo ."]
        assert "updated" in result.output.lower()


# ---------------------------------------------------------------------------
# Codex hook tests
# ---------------------------------------------------------------------------


class TestInitToolCodex:
    def test_appends_to_agents_md(self, tmp_path: Path) -> None:
        # Create an existing AGENTS.md
        (tmp_path / "AGENTS.md").write_text("# My Project\n\nSome content.\n", encoding="utf-8")
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "codex", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert "spanweave extract-latest --repo ." in content
        assert "Session end protocol" in content
        assert "Codex instruction added" in result.output

    def test_creates_agents_md_if_missing(self, tmp_path: Path) -> None:
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "codex", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        assert (tmp_path / "AGENTS.md").is_file()
        content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert "spanweave extract-latest --repo ." in content

    def test_is_idempotent(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("# Project\n", encoding="utf-8")
        runner = CliRunner()

        runner.invoke(main, ["init", "--tool", "codex", "--repo", str(tmp_path)])
        runner.invoke(main, ["init", "--tool", "codex", "--repo", str(tmp_path)])

        content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert content.count("spanweave extract-latest --repo .") == 1


# ---------------------------------------------------------------------------
# Cursor hook tests
# ---------------------------------------------------------------------------


class TestInitToolCursor:
    def test_creates_cursorrules(self, tmp_path: Path) -> None:
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "cursor", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        assert (tmp_path / ".cursorrules").is_file()
        content = (tmp_path / ".cursorrules").read_text(encoding="utf-8")
        assert "spanweave extract-latest --repo ." in content
        assert ".spanweave/runs/" in content
        assert "Cursor rules updated" in result.output

    def test_preserves_existing_cursorrules(self, tmp_path: Path) -> None:
        (tmp_path / ".cursorrules").write_text("# Existing rules\nDo things.\n", encoding="utf-8")
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "cursor", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        content = (tmp_path / ".cursorrules").read_text(encoding="utf-8")
        assert "# Existing rules" in content
        assert "spanweave extract-latest --repo ." in content


# ---------------------------------------------------------------------------
# Windsurf hook tests
# ---------------------------------------------------------------------------


class TestInitToolWindsurf:
    def test_creates_windsurfrules(self, tmp_path: Path) -> None:
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "windsurf", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        assert (tmp_path / ".windsurfrules").is_file()
        content = (tmp_path / ".windsurfrules").read_text(encoding="utf-8")
        assert "spanweave extract-latest --repo ." in content
        assert ".spanweave/runs/" in content
        assert "Windsurf rules updated" in result.output


# ---------------------------------------------------------------------------
# extract-latest tests
# ---------------------------------------------------------------------------


class TestExtractLatest:
    def test_finds_most_recent_session(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mock the session dir, verify it picks the newest file."""
        # Create a fake repo
        repo = tmp_path / "project"
        repo.mkdir()
        (repo / ".spanweave").mkdir()

        # Simulate the Claude Code project sessions directory
        encoded = str(repo.resolve()).replace("/", "-")
        sessions_dir = tmp_path / "fakehome" / ".claude" / "projects" / encoded
        sessions_dir.mkdir(parents=True)

        # Create two session files with different mtimes
        old_session = sessions_dir / "old-session.jsonl"
        new_session = sessions_dir / "new-session.jsonl"
        old_session.write_text('{"type":"user","message":"old"}\n', encoding="utf-8")
        new_session.write_text('{"type":"user","message":"new"}\n', encoding="utf-8")

        import os

        os.utime(old_session, (1000000, 1000000))
        os.utime(new_session, (2000000, 2000000))

        # Patch Path.home() to point to our fake home
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "fakehome")

        # Patch extract_from_session to just record the call
        with patch("spanweave.learning.extractor.extract_from_session") as mock_extract:
            mock_extract.return_value = [{"type": "decision", "body": "test"}]
            runner = CliRunner()
            result = runner.invoke(main, ["extract-latest", "--repo", str(repo)])

        assert result.exit_code == 0
        mock_extract.assert_called_once()
        called_path = mock_extract.call_args[0][0]
        assert called_path == new_session

    def test_no_sessions_gives_helpful_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify error message when no sessions exist."""
        repo = tmp_path / "project"
        repo.mkdir()

        # Patch Path.home() to a location with no sessions
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "fakehome")

        runner = CliRunner()
        result = runner.invoke(main, ["extract-latest", "--repo", str(repo)])

        assert result.exit_code == 1
        assert "No session files found" in result.output
