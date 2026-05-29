"""Tests for the multi-source transcript adapters (spanweave.sources).

Covers the source-adapter abstraction that makes extract-latest tool-agnostic:
- CodexSource discovery (scan ~/.codex/sessions rollouts, match by cwd) + parsing
- ClaudeCodeSource discovery + parsing (regression)
- the registry (get_source / all_sources)
- the protocol contract

CLI-level routing (--tool, auto mode, per-source watermark independence) lives
in ``TestMultiSourceCli`` near the bottom.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner

# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #


def _codex_meta_line(cwd: str) -> str:
    """A realistic Codex ``session_meta`` first line carrying ``cwd``."""
    return json.dumps({
        "timestamp": "2026-02-28T05:05:57.231Z",
        "type": "session_meta",
        "payload": {
            "id": "019ca2a1-638d-7992-927c-72717aeec68b",
            "timestamp": "2026-02-28T05:03:31.728Z",
            "cwd": cwd,
            "originator": "codex_cli_rs",
            "cli_version": "0.106.0",
        },
    })


def _codex_message_line(role: str, text: str, part_type: str) -> str:
    """A Codex ``response_item`` message line with one text content-part."""
    return json.dumps({
        "timestamp": "2026-02-28T05:06:00.000Z",
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": role,
            "content": [{"type": part_type, "text": text}],
        },
    })


def _write_codex_rollout(
    sessions_root: Path,
    *,
    cwd: str,
    ymd: tuple[str, str, str] = ("2026", "02", "28"),
    name: str = "rollout-2026-02-28T05-03-31-019ca2a1.jsonl",
    extra_lines: list[str] | None = None,
) -> Path:
    """Write a fake Codex rollout under ``sessions_root/YYYY/MM/DD/``."""
    y, m, d = ymd
    day_dir = sessions_root / y / m / d
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / name
    lines = [_codex_meta_line(cwd), *(extra_lines or [])]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@contextmanager
def fake_home(home: Path) -> Iterator[None]:
    """Point ``Path.home()`` at ``home`` so adapters scan a temp data dir."""
    with patch("pathlib.Path.home", return_value=home):
        yield


# --------------------------------------------------------------------------- #
# CodexSource: discovery
# --------------------------------------------------------------------------- #


class TestCodexSourceDiscovery:
    def test_is_available_reflects_sessions_dir(self, tmp_path: Path) -> None:
        from spanweave.sources.codex import CodexSource

        with fake_home(tmp_path):
            assert CodexSource().is_available() is False
            (tmp_path / ".codex" / "sessions").mkdir(parents=True)
            assert CodexSource().is_available() is True

    def test_latest_session_matches_cwd(self, tmp_path: Path) -> None:
        """Only rollouts whose session_meta cwd == repo_root are candidates."""
        from spanweave.sources.codex import CodexSource

        home = tmp_path / "home"
        sessions = home / ".codex" / "sessions"
        repo = tmp_path / "repo"
        repo.mkdir()
        other = tmp_path / "other"
        other.mkdir()

        # A matching rollout and a non-matching one.
        match = _write_codex_rollout(
            sessions, cwd=str(repo), name="rollout-match.jsonl"
        )
        _write_codex_rollout(sessions, cwd=str(other), name="rollout-other.jsonl")

        with fake_home(home):
            found = CodexSource().latest_session(repo)

        assert found == match

    def test_latest_session_returns_newest_match_by_mtime(self, tmp_path: Path) -> None:
        from spanweave.sources.codex import CodexSource

        home = tmp_path / "home"
        sessions = home / ".codex" / "sessions"
        repo = tmp_path / "repo"
        repo.mkdir()

        older = _write_codex_rollout(
            sessions, cwd=str(repo), ymd=("2026", "02", "28"), name="rollout-old.jsonl"
        )
        newer = _write_codex_rollout(
            sessions, cwd=str(repo), ymd=("2026", "04", "26"), name="rollout-new.jsonl"
        )
        # Force a clear mtime ordering regardless of write speed.
        old_t = time.time() - 100
        import os

        os.utime(older, (old_t, old_t))
        new_t = time.time()
        os.utime(newer, (new_t, new_t))

        with fake_home(home):
            found = CodexSource().latest_session(repo)

        assert found == newer

    def test_latest_session_none_when_no_match(self, tmp_path: Path) -> None:
        from spanweave.sources.codex import CodexSource

        home = tmp_path / "home"
        sessions = home / ".codex" / "sessions"
        repo = tmp_path / "repo"
        repo.mkdir()
        _write_codex_rollout(sessions, cwd="/some/other/place")

        with fake_home(home):
            assert CodexSource().latest_session(repo) is None

    def test_latest_session_none_when_dir_absent(self, tmp_path: Path) -> None:
        from spanweave.sources.codex import CodexSource

        home = tmp_path / "home"  # no .codex at all
        home.mkdir()
        repo = tmp_path / "repo"
        repo.mkdir()
        with fake_home(home):
            assert CodexSource().latest_session(repo) is None

    def test_latest_session_skips_unreadable_meta(self, tmp_path: Path) -> None:
        """A rollout with a non-JSON / non-session_meta first line is ignored."""
        from spanweave.sources.codex import CodexSource

        home = tmp_path / "home"
        sessions = home / ".codex" / "sessions"
        repo = tmp_path / "repo"
        repo.mkdir()

        # Garbage first line -> no cwd -> not a candidate.
        day = sessions / "2026" / "02" / "28"
        day.mkdir(parents=True)
        bad = day / "rollout-bad.jsonl"
        bad.write_text("not json at all\n", encoding="utf-8")

        good = _write_codex_rollout(sessions, cwd=str(repo), name="rollout-good.jsonl")

        with fake_home(home):
            assert CodexSource().latest_session(repo) == good


# --------------------------------------------------------------------------- #
# CodexSource: parsing
# --------------------------------------------------------------------------- #


class TestCodexSourceParsing:
    def test_parse_extracts_user_and_assistant_text(self) -> None:
        from spanweave.sources.codex import CodexSource

        text = "\n".join([
            _codex_meta_line("/repo"),
            _codex_message_line("user", "what is 2+2?", "input_text"),
            _codex_message_line("assistant", "it is 4", "output_text"),
        ])
        msgs = CodexSource().parse_messages(text)

        assert msgs == ["[user]: what is 2+2?", "[assistant]: it is 4"]

    def test_parse_ignores_session_meta_and_event_msg(self) -> None:
        from spanweave.sources.codex import CodexSource

        event_msg = json.dumps({
            "timestamp": "t",
            "type": "event_msg",
            "payload": {"type": "agent_message", "message": "noise"},
        })
        token_count = json.dumps({
            "timestamp": "t",
            "type": "event_msg",
            "payload": {"type": "token_count"},
        })
        text = "\n".join([
            _codex_meta_line("/repo"),
            event_msg,
            token_count,
            _codex_message_line("user", "real question", "input_text"),
        ])
        msgs = CodexSource().parse_messages(text)

        assert msgs == ["[user]: real question"]

    def test_parse_ignores_developer_and_tool_items(self) -> None:
        """developer prompts + reasoning/function_call response items are dropped."""
        from spanweave.sources.codex import CodexSource

        developer = _codex_message_line("developer", "SYSTEM PROMPT", "input_text")
        reasoning = json.dumps({
            "type": "response_item",
            "payload": {"type": "reasoning", "summary": []},
        })
        function_call = json.dumps({
            "type": "response_item",
            "payload": {"type": "function_call", "name": "shell"},
        })
        text = "\n".join([
            developer,
            reasoning,
            function_call,
            _codex_message_line("assistant", "kept", "output_text"),
        ])
        msgs = CodexSource().parse_messages(text)

        assert msgs == ["[assistant]: kept"]

    def test_parse_concatenates_multiple_content_parts(self) -> None:
        from spanweave.sources.codex import CodexSource

        multi = json.dumps({
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "part one"},
                    {"type": "input_text", "text": "part two"},
                ],
            },
        })
        msgs = CodexSource().parse_messages(multi)

        assert msgs == ["[user]: part one\npart two"]

    def test_parse_skips_blank_and_malformed_lines(self) -> None:
        from spanweave.sources.codex import CodexSource

        text = "\n".join([
            "",
            "   ",
            "{not valid json",
            _codex_message_line("user", "survivor", "input_text"),
            "",
        ])
        msgs = CodexSource().parse_messages(text)

        assert msgs == ["[user]: survivor"]

    def test_parse_real_rollout_shape(self) -> None:
        """Parse a fixture mirroring the verified real Codex rollout schema."""
        from spanweave.sources.codex import CodexSource

        text = "\n".join([
            _codex_meta_line("/home/fei/proj"),
            # developer permission injection (skip)
            _codex_message_line("developer", "<permissions instructions>...", "input_text"),
            # real user turn
            _codex_message_line("user", ".codex/prompts/spec", "input_text"),
            # event mirror of the user message (skip)
            json.dumps({
                "type": "event_msg",
                "payload": {"type": "user_message", "message": ".codex/prompts/spec"},
            }),
            # assistant turn
            _codex_message_line("assistant", "Here is the spec.", "output_text"),
        ])
        msgs = CodexSource().parse_messages(text)

        assert msgs == ["[user]: .codex/prompts/spec", "[assistant]: Here is the spec."]


# --------------------------------------------------------------------------- #
# ClaudeCodeSource: regression
# --------------------------------------------------------------------------- #


class TestClaudeCodeSource:
    def test_project_dir_encodes_path(self, tmp_path: Path) -> None:
        from spanweave.sources.claude_code import ClaudeCodeSource

        repo = tmp_path / "myrepo"
        repo.mkdir()
        with fake_home(tmp_path):
            d = ClaudeCodeSource().project_dir(repo)
        encoded = str(repo.resolve()).replace("/", "-")
        assert d == tmp_path / ".claude" / "projects" / encoded

    def test_latest_session_picks_newest_jsonl(self, tmp_path: Path) -> None:
        from spanweave.sources.claude_code import ClaudeCodeSource

        home = tmp_path / "home"
        repo = tmp_path / "repo"
        repo.mkdir()
        encoded = str(repo.resolve()).replace("/", "-")
        proj = home / ".claude" / "projects" / encoded
        proj.mkdir(parents=True)

        import os

        old = proj / "old.jsonl"
        old.write_text("{}\n", encoding="utf-8")
        new = proj / "new.jsonl"
        new.write_text("{}\n", encoding="utf-8")
        os.utime(old, (time.time() - 50, time.time() - 50))
        os.utime(new, (time.time(), time.time()))

        with fake_home(home):
            found = ClaudeCodeSource().latest_session(repo)
        assert found == new

    def test_latest_session_none_when_absent(self, tmp_path: Path) -> None:
        from spanweave.sources.claude_code import ClaudeCodeSource

        home = tmp_path / "home"
        home.mkdir()
        repo = tmp_path / "repo"
        repo.mkdir()
        with fake_home(home):
            assert ClaudeCodeSource().latest_session(repo) is None

    def test_parse_messages_claude_schema(self) -> None:
        from spanweave.sources.claude_code import ClaudeCodeSource

        text = "\n".join([
            json.dumps({"type": "user", "message": "hi"}),
            json.dumps({"type": "assistant", "message": "hello"}),
            json.dumps({"type": "system", "message": "ignored"}),
            json.dumps({"type": "user", "message": ""}),  # empty -> skip
            "garbage",
        ])
        msgs = ClaudeCodeSource().parse_messages(text)
        assert msgs == ["[user]: hi", "[assistant]: hello"]


# --------------------------------------------------------------------------- #
# Registry + protocol
# --------------------------------------------------------------------------- #


class TestRegistry:
    def test_get_source_known(self) -> None:
        from spanweave.sources import get_source
        from spanweave.sources.claude_code import ClaudeCodeSource
        from spanweave.sources.codex import CodexSource

        assert isinstance(get_source("claude-code"), ClaudeCodeSource)
        assert isinstance(get_source("codex"), CodexSource)

    def test_get_source_unknown_raises_with_known_names(self) -> None:
        from spanweave.sources import get_source

        with pytest.raises(KeyError) as exc:
            get_source("cursor")
        assert "claude-code" in str(exc.value)
        assert "codex" in str(exc.value)

    def test_all_sources_includes_both(self) -> None:
        from spanweave.sources import all_sources

        names = {s.name for s in all_sources()}
        assert {"claude-code", "codex"} <= names

    def test_sources_satisfy_protocol(self) -> None:
        from spanweave.sources import all_sources
        from spanweave.sources.base import SessionSource

        for s in all_sources():
            assert isinstance(s, SessionSource)


# --------------------------------------------------------------------------- #
# CLI: --tool routing, auto mode, per-source watermark independence
# --------------------------------------------------------------------------- #


def _mock_response() -> str:
    return json.dumps([
        {
            "type": "decision",
            "body": "Use Pydantic v2",
            "reasoning": "Better perf",
            "tags": ["deps"],
            "confidence": 0.9,
        }
    ])


class TestMultiSourceCli:
    def _wm_path(self, repo: Path, tool: str) -> Path:
        return repo / ".spanweave" / "daemon" / f"extract-latest-{tool}.watermark"

    def test_tool_codex_routes_to_codex_source(self, tmp_path: Path) -> None:
        """--tool codex must discover via CodexSource and parse Codex schema."""
        from spanweave.cli.main import main

        home = tmp_path / "home"
        sessions = home / ".codex" / "sessions"
        repo = tmp_path / "repo"
        repo.mkdir()
        rollout = _write_codex_rollout(
            sessions,
            cwd=str(repo),
            extra_lines=[
                _codex_message_line("user", "decide the db", "input_text"),
                _codex_message_line("assistant", "use sqlite", "output_text"),
            ],
        )

        seen: list[str] = []

        def _record(prompt: str, *_a: Any, **_k: Any) -> str:
            marker = "Conversation:\n---\n"
            if marker in prompt:
                seen.append(prompt.split(marker, 1)[1])
            return _mock_response()

        runner = CliRunner()
        with (
            fake_home(home),
            patch("spanweave.cli.commands.extract_latest.ollama_available", return_value=True),
            patch("spanweave.learning.extractor._call_ollama", side_effect=_record),
        ):
            result = runner.invoke(
                main, ["extract-latest", "--repo", str(repo), "--tool", "codex"]
            )

        assert result.exit_code == 0, result.output
        # Codex watermark written; pointed at the rollout.
        wm = json.loads(self._wm_path(repo, "codex").read_text(encoding="utf-8"))
        assert wm["session_path"] == str(rollout)
        # Codex content was parsed (proves CodexSource.parse_messages ran).
        joined = "\n".join(seen)
        assert "decide the db" in joined
        assert "use sqlite" in joined

    def test_tool_claude_routes_to_claude_source(self, tmp_path: Path) -> None:
        from spanweave.cli.main import main

        repo = tmp_path / "repo"
        repo.mkdir()
        claude_session = repo / "claude.jsonl"
        claude_session.write_text(
            json.dumps({"type": "user", "message": "hi claude"}) + "\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        with (
            patch(
                "spanweave.sources.claude_code.ClaudeCodeSource.latest_session",
                return_value=claude_session,
            ),
            patch(
                "spanweave.sources.claude_code.ClaudeCodeSource.is_available",
                return_value=True,
            ),
            patch("spanweave.cli.commands.extract_latest.ollama_available", return_value=True),
            patch("spanweave.learning.extractor._call_ollama", return_value=_mock_response()),
        ):
            result = runner.invoke(
                main, ["extract-latest", "--repo", str(repo), "--tool", "claude-code"]
            )

        assert result.exit_code == 0, result.output
        wm = json.loads(self._wm_path(repo, "claude-code").read_text(encoding="utf-8"))
        assert wm["session_path"] == str(claude_session)
        # The codex watermark must NOT exist for a claude-only run.
        assert not self._wm_path(repo, "codex").exists()

    def test_auto_processes_both_when_available(self, tmp_path: Path) -> None:
        """No --tool: every installed source with a session for this repo runs."""
        from spanweave.cli.main import main

        home = tmp_path / "home"
        sessions = home / ".codex" / "sessions"
        repo = tmp_path / "repo"
        repo.mkdir()
        _write_codex_rollout(
            sessions,
            cwd=str(repo),
            extra_lines=[_codex_message_line("user", "codex turn", "input_text")],
        )

        claude_session = repo / "claude.jsonl"
        claude_session.write_text(
            json.dumps({"type": "user", "message": "claude turn"}) + "\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        with (
            fake_home(home),
            patch(
                "spanweave.sources.claude_code.ClaudeCodeSource.latest_session",
                return_value=claude_session,
            ),
            patch(
                "spanweave.sources.claude_code.ClaudeCodeSource.is_available",
                return_value=True,
            ),
            patch("spanweave.cli.commands.extract_latest.ollama_available", return_value=True),
            patch("spanweave.learning.extractor._call_ollama", return_value=_mock_response()),
        ):
            result = runner.invoke(main, ["extract-latest", "--repo", str(repo)])

        assert result.exit_code == 0, result.output
        # Both per-source watermarks must exist.
        assert self._wm_path(repo, "codex").exists()
        assert self._wm_path(repo, "claude-code").exists()

    def test_auto_no_available_sources_is_noop_exit0(self, tmp_path: Path) -> None:
        """Auto mode with nothing installed/found -> graceful exit 0 no-op."""
        from spanweave.cli.main import main

        home = tmp_path / "home"  # no .codex, no .claude
        home.mkdir()
        repo = tmp_path / "repo"
        repo.mkdir()

        runner = CliRunner()
        with (
            fake_home(home),
            patch("spanweave.cli.commands.extract_latest.ollama_available", return_value=True),
            patch("spanweave.learning.extractor._call_ollama") as call_mock,
        ):
            result = runner.invoke(main, ["extract-latest", "--repo", str(repo)])

        assert result.exit_code == 0
        call_mock.assert_not_called()
        # No watermarks created.
        daemon = repo / ".spanweave" / "daemon"
        wms = list(daemon.glob("*.watermark")) if daemon.exists() else []
        assert wms == []

    def test_per_source_watermark_independence(self, tmp_path: Path) -> None:
        """Extracting Codex must not touch Claude's watermark, and vice versa."""
        from spanweave.cli.main import main

        home = tmp_path / "home"
        sessions = home / ".codex" / "sessions"
        repo = tmp_path / "repo"
        repo.mkdir()
        _write_codex_rollout(
            sessions,
            cwd=str(repo),
            extra_lines=[_codex_message_line("user", "codex only", "input_text")],
        )
        claude_session = repo / "claude.jsonl"
        claude_session.write_text(
            json.dumps({"type": "user", "message": "claude only"}) + "\n",
            encoding="utf-8",
        )

        runner = CliRunner()

        def _ollama_patches() -> list[Any]:
            # Fresh patcher objects each use — a patcher can't be re-entered
            # after it exits, so build new ones per ``with`` block.
            return [
                patch(
                    "spanweave.cli.commands.extract_latest.ollama_available",
                    return_value=True,
                ),
                patch(
                    "spanweave.learning.extractor._call_ollama",
                    return_value=_mock_response(),
                ),
            ]

        # 1. Run Claude only.
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "spanweave.sources.claude_code.ClaudeCodeSource.latest_session",
                    return_value=claude_session,
                )
            )
            stack.enter_context(
                patch(
                    "spanweave.sources.claude_code.ClaudeCodeSource.is_available",
                    return_value=True,
                )
            )
            for p in _ollama_patches():
                stack.enter_context(p)
            runner.invoke(
                main, ["extract-latest", "--repo", str(repo), "--tool", "claude-code"]
            )

        assert self._wm_path(repo, "claude-code").exists()
        assert not self._wm_path(repo, "codex").exists()
        claude_wm_1 = self._wm_path(repo, "claude-code").read_text(encoding="utf-8")

        # 2. Now run Codex only — Claude's watermark must be byte-for-byte unchanged.
        with ExitStack() as stack:
            stack.enter_context(fake_home(home))
            for p in _ollama_patches():
                stack.enter_context(p)
            runner.invoke(main, ["extract-latest", "--repo", str(repo), "--tool", "codex"])

        assert self._wm_path(repo, "codex").exists()
        claude_wm_2 = self._wm_path(repo, "claude-code").read_text(encoding="utf-8")
        assert claude_wm_1 == claude_wm_2  # Codex run did not disturb Claude
