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


def _session_end_hook_commands(settings: dict[str, Any]) -> list[str]:
    """Extract command strings from hooks.SessionEnd, validating the schema shape.

    Claude Code requires each SessionEnd entry to be a matcher-block with a
    nested ``hooks`` array: ``{"matcher": "", "hooks": [{"type": "command", ...}]}``.
    This helper asserts that shape and returns the inner command strings.

    SessionEnd (not Stop) is the correct event for capturing at session end:
    Stop fires per-turn (after every reply), while SessionEnd fires once when
    the session terminates (close, /clear, exit) — matching the mental model
    documented in README.md / CLAUDE.md.
    """
    blocks: list[dict[str, Any]] = settings["hooks"]["SessionEnd"]
    commands: list[str] = []
    for block in blocks:
        assert "hooks" in block, f"SessionEnd entry missing 'hooks' array: {block!r}"
        assert isinstance(block["hooks"], list)
        for inner in block["hooks"]:
            assert inner.get("type") == "command"
            commands.append(inner["command"])
    return commands


def _extract_read_pointer_body(content: str) -> str:
    """Slice out just the read-pointer section body from a wired convention file.

    The convention files may contain multiple Spanweave headings (read-pointer
    for cross-tool load + write-pointer that captures to ``pending/``), plus
    user content. Scoping the negative assertions to the read-pointer body
    avoids false positives from substrings that legitimately appear elsewhere
    (e.g. the write-pointer's ``pending/`` target).
    """
    heading = "## Load Spanweave context on session start"
    start = content.find(heading)
    assert start != -1, f"read-pointer heading not found in:\n{content}"
    rest = content[start + len(heading) :]
    # Stop at the next top-level heading (``\n## ``) — whichever comes first.
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _assert_read_pointer_covers_all_record_dirs(content: str) -> None:
    """Assert the scaffolded read-pointer mentions every record-type dir.

    Issue #96: prior wiring named only ``decisions/`` and ``shared/decisions/``,
    so a fresh agent silently skipped findings, reflections, and
    rejected_alternatives — defeating the cross-tool ambient-memory promise.
    The pointer must point at every public record-type subtree (both the
    local and ``shared/`` copies), and must NOT mention ``private/`` (local-
    only, never crosses machines) or ``pending/`` (pre-review quarantine).
    """
    body = _extract_read_pointer_body(content)
    # Positive: every public record-type dir + its shared/ promoted copy.
    for record_type in ("decisions", "findings", "reflections", "rejected_alternatives"):
        assert f".spanweave/memory/{record_type}/" in body, (
            f"read-pointer missing .spanweave/memory/{record_type}/\nbody was:\n{body}"
        )
        assert f".spanweave/memory/shared/{record_type}/" in body, (
            f"read-pointer missing .spanweave/memory/shared/{record_type}/\nbody was:\n{body}"
        )
    # Negative: private/ and pending/ are out of scope for cross-tool loading.
    assert "private/" not in body, (
        f"read-pointer must not point at private/ (local-only by definition)\nbody:\n{body}"
    )
    assert "pending/" not in body, (
        f"read-pointer must not point at pending/ (pre-review quarantine)\nbody:\n{body}"
    )


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
        assert "SessionEnd" in settings["hooks"]
        # Stop must NOT be present — capture belongs on the per-session event,
        # not the per-turn event.
        assert "Stop" not in settings["hooks"]
        hook_commands = _session_end_hook_commands(settings)
        # Tolerant of invocation form (plain vs .venv/bin) — tmp_path has no venv
        # so it resolves to the plain command here. The hook uses --detach so a
        # slow model never trips the hook timeout.
        assert any(c.endswith("extract-latest --repo . --detach") for c in hook_commands)
        assert "Claude Code SessionEnd hook wired" in result.output

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
        # Hook added on the SessionEnd event (per-session, not per-turn).
        hook_commands = _session_end_hook_commands(settings)
        assert any(c.endswith("extract-latest --repo . --detach") for c in hook_commands)

    def test_is_idempotent(self, tmp_path: Path) -> None:
        runner = CliRunner()

        runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])
        runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])

        settings = _settings_json(tmp_path)
        hook_commands = _session_end_hook_commands(settings)
        # Only one spanweave extract-latest hook regardless of invocation form
        extract_hooks = [c for c in hook_commands if "extract-latest --repo ." in c]
        assert len(extract_hooks) == 1

    def test_uses_venv_binary_when_present(self, tmp_path: Path) -> None:
        """When a repo-local venv exists, the hook must point at its binary.

        The bare /bin/sh that Claude Code uses for hooks has neither the
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
        hook_commands = _session_end_hook_commands(_settings_json(tmp_path))
        assert ".venv/bin/spanweave extract-latest --repo . --detach" in hook_commands

    def test_self_heals_stale_plain_command(self, tmp_path: Path) -> None:
        """Re-running init upgrades a stale hook in place (no duplicate).

        The pre-populated command is the old form: bare `spanweave` (fails in
        the bare hook shell) AND without `--detach` (pre-async). The entry also
        lives under the old `Stop` event key. Re-running init must move it to
        `SessionEnd` AND upgrade it in place to the venv-resolved, detached
        command — exercising the event migration, the PATH self-heal, and the
        pre-detach migration in one shot.
        """
        # Pre-populate with the old, broken hook command on the old event key.
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
        settings = _settings_json(tmp_path)
        hook_commands = _session_end_hook_commands(settings)
        # Upgraded in place — exactly one hook, now venv-resolved AND detached.
        assert hook_commands == [".venv/bin/spanweave extract-latest --repo . --detach"]
        # The old Stop entry must no longer contain a spanweave hook (key may be
        # dropped entirely OR left as an empty list — both are acceptable).
        stop_blocks = settings.get("hooks", {}).get("Stop", [])
        stop_commands: list[str] = []
        for block in stop_blocks:
            for inner in block.get("hooks", []):
                stop_commands.append(inner.get("command", ""))
        assert not any("extract-latest --repo ." in c for c in stop_commands)
        assert "updated" in result.output.lower()

    def test_self_heals_stale_stop_hook_to_sessionend(self, tmp_path: Path) -> None:
        """Migration: a hook on the old `Stop` event is moved to `SessionEnd`.

        Earlier spanweave versions wired the capture command under `hooks.Stop`,
        which fires after every Claude Code turn instead of once per session
        end. Re-running `init --tool claude-code` on such a repo must MOVE that
        entry to `hooks.SessionEnd[]` (remove from Stop, add to SessionEnd),
        preserving the inner command + matcher intact. This makes the wiring
        self-healing across the Stop→SessionEnd migration.
        """
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        # Pre-populate with the already-detached form on the old `Stop` event
        # (worst case: the hook is "current" except for the event key).
        stale = {
            "hooks": {
                "Stop": [
                    {
                        "matcher": "",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "spanweave extract-latest --repo . --detach",
                            }
                        ],
                    }
                ]
            }
        }
        (claude_dir / "settings.json").write_text(json.dumps(stale, indent=2), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        settings = _settings_json(tmp_path)
        # The hook is now on SessionEnd, with the correct command.
        hook_commands = _session_end_hook_commands(settings)
        assert hook_commands == ["spanweave extract-latest --repo . --detach"]
        # The old Stop list no longer references the spanweave hook.
        stop_blocks = settings.get("hooks", {}).get("Stop", [])
        for block in stop_blocks:
            for inner in block.get("hooks", []):
                assert "extract-latest --repo ." not in inner.get("command", "")

    def test_writes_read_pointer_to_claude_md(self, tmp_path: Path) -> None:
        """Claude Code gets a CLAUDE.md read-pointer covering memory/.

        The SessionEnd hook is the *capture* (write) side; the read side lives
        in CLAUDE.md so a fresh session loads prior decisions from the ambient
        memory substrate.
        """
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        claude_md = tmp_path / "CLAUDE.md"
        assert claude_md.is_file()
        content = claude_md.read_text(encoding="utf-8")
        assert "Load Spanweave context on session start" in content
        assert ".spanweave/memory/" in content

    def test_claude_md_read_pointer_covers_all_record_dirs(self, tmp_path: Path) -> None:
        """Regression for #96: CLAUDE.md read-pointer must name every record-type dir.

        Before this fix the pointer mentioned only ``decisions/`` — so a fresh
        Claude Code session silently skipped findings, reflections, and
        rejected_alternatives even though extract-latest had captured them.
        """
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        _assert_read_pointer_covers_all_record_dirs(content)

    def test_claude_md_has_no_manual_capture_instruction(self, tmp_path: Path) -> None:
        """CLAUDE.md must NOT carry the manual capture (write) pointer.

        Capture for Claude Code is automatic via the SessionEnd hook. Adding a
        manual 'run spanweave extract-latest' instruction too would invite the
        model to double-extract — so the write-pointer is deliberately omitted
        here (it's only for hookless tools: codex/cursor/windsurf).
        """
        runner = CliRunner()

        runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])

        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Capture decisions on session end" not in content

    def test_claude_md_read_pointer_is_idempotent(self, tmp_path: Path) -> None:
        runner = CliRunner()

        runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])
        runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])

        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert content.count("## Load Spanweave context on session start") == 1

    def test_preserves_existing_claude_md(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text(
            "# House Rules\n\nUse 4-space indents.\n", encoding="utf-8"
        )
        runner = CliRunner()

        runner.invoke(main, ["init", "--tool", "claude-code", "--repo", str(tmp_path)])

        content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "# House Rules" in content
        assert "Use 4-space indents." in content
        assert "Load Spanweave context on session start" in content


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
        # Existing user content is preserved (sections are appended, not rewritten).
        assert "# My Project" in content
        assert "Some content." in content
        # Write-pointer (capture on end) is present.
        assert "spanweave extract-latest --repo ." in content
        assert "Capture decisions on session end" in content
        assert "Codex" in result.output

    def test_read_pointer_covers_memory(self, tmp_path: Path) -> None:
        """Codex's AGENTS.md must point at memory/ on load.

        Earlier wiring gave Codex only a capture-on-end instruction (no
        load-context pointer at all), so a fresh Codex session never learned to
        read decisions staged by extract-latest.
        """
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "codex", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        # Read-pointer heading + memory substrate location.
        assert "Load Spanweave context on session start" in content
        assert ".spanweave/memory/" in content

    def test_agents_md_read_pointer_covers_all_record_dirs(self, tmp_path: Path) -> None:
        """Regression for #96: AGENTS.md read-pointer must name every record-type dir."""
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "codex", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        _assert_read_pointer_covers_all_record_dirs(content)

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
        # Neither the write-pointer command nor either heading is duplicated.
        assert content.count("spanweave extract-latest --repo .") == 1
        assert content.count("## Load Spanweave context on session start") == 1
        assert content.count("## Capture decisions on session end") == 1

    def test_adds_only_missing_section(self, tmp_path: Path) -> None:
        """Migration case: a repo with only the old write-pointer gains the read one.

        ``_ensure_sections`` keys off each heading independently, so a repo wired
        by an older spanweave (capture-only) picks up the new load-context
        pointer on re-init without duplicating the section it already has.
        """
        agents = tmp_path / "AGENTS.md"
        agents.write_text(
            "# Project\n\n## Capture decisions on session end\n\n"
            "Before ending your session, run:\n"
            "```bash\nspanweave extract-latest --repo .\n```\n",
            encoding="utf-8",
        )
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "codex", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        content = agents.read_text(encoding="utf-8")
        # Read-pointer added; capture section not duplicated.
        assert content.count("## Load Spanweave context on session start") == 1
        assert content.count("## Capture decisions on session end") == 1


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
        # Write-pointer (capture) + read-pointer covering the memory substrate.
        assert "spanweave extract-latest --repo ." in content
        assert ".spanweave/memory/" in content
        assert "Cursor" in result.output

    def test_preserves_existing_cursorrules(self, tmp_path: Path) -> None:
        (tmp_path / ".cursorrules").write_text("# Existing rules\nDo things.\n", encoding="utf-8")
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "cursor", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        content = (tmp_path / ".cursorrules").read_text(encoding="utf-8")
        assert "# Existing rules" in content
        assert "spanweave extract-latest --repo ." in content

    def test_cursorrules_read_pointer_covers_all_record_dirs(self, tmp_path: Path) -> None:
        """Regression for #96: .cursorrules read-pointer must name every record-type dir."""
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "cursor", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        content = (tmp_path / ".cursorrules").read_text(encoding="utf-8")
        _assert_read_pointer_covers_all_record_dirs(content)


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
        # Write-pointer (capture) + read-pointer covering the memory substrate.
        assert "spanweave extract-latest --repo ." in content
        assert ".spanweave/memory/" in content
        assert "Windsurf" in result.output

    def test_windsurfrules_read_pointer_covers_all_record_dirs(self, tmp_path: Path) -> None:
        """Regression for #96: .windsurfrules read-pointer must name every record-type dir."""
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--tool", "windsurf", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        content = (tmp_path / ".windsurfrules").read_text(encoding="utf-8")
        _assert_read_pointer_covers_all_record_dirs(content)


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

        # Patch extract_from_session to record the call, AND force the Ollama
        # availability probe True. extract-latest gates extraction behind
        # ollama_available() (added in #82); on CI there's no Ollama, so without
        # this mock the command quietly early-returns and extract_from_session
        # is never called. This test targets session *discovery*, so we assume
        # Ollama is up.
        with (
            patch("spanweave.cli.commands.extract_latest.ollama_available", return_value=True),
            patch("spanweave.learning.extractor.extract_from_session") as mock_extract,
        ):
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
