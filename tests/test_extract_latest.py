"""Tests for the spanweave extract-latest CLI command (hook-invoked).

extract-latest is wired as a Claude Code SessionEnd hook, so it must degrade
gracefully when Ollama is unavailable: a quiet no-op that exits 0 rather
than erroring (which Claude Code surfaces as a scary hook error).

Since the multi-source refactor, transcript discovery is delegated to source
adapters (``spanweave.sources``). The Claude-Code tests below pin to
``--tool claude-code`` and patch ``ClaudeCodeSource.latest_session`` (the new
discovery seam that replaced the old module-level ``_find_latest_session``).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_SESSION = FIXTURES_DIR / "sample_session.jsonl"

# The Claude adapter is the discovery seam these tests pin to. Patching its
# ``latest_session`` replaces what ``_find_latest_session`` used to mock.
CLAUDE_SOURCE = "spanweave.sources.claude_code.ClaudeCodeSource"


@contextmanager
def claude_session(session: Path | None) -> Iterator[None]:
    """Force the Claude adapter to 'find' ``session`` (or None) for any repo.

    Also forces ``is_available`` True so auto/explicit selection always reaches
    discovery regardless of whether ~/.claude exists in the test environment.
    """
    with (
        patch(f"{CLAUDE_SOURCE}.latest_session", return_value=session),
        patch(f"{CLAUDE_SOURCE}.is_available", return_value=True),
    ):
        yield


class TestExtractLatestGracefulDegradation:
    """extract-latest must be a silent, exit-0 no-op when Ollama is down."""

    def test_extract_latest_quiet_noop_when_ollama_down(self, tmp_path: Path) -> None:
        """Probe says Ollama is down -> exit 0, no stdout, nothing staged."""
        from spanweave.cli.main import main

        runner = CliRunner()

        with (
            claude_session(SAMPLE_SESSION),
            patch(
                "spanweave.cli.commands.extract_latest.ollama_available",
                return_value=False,
            ),
        ):
            result = runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
            )

        assert result.exit_code == 0
        # Nothing on stdout — the hook is silent-success by default.
        assert result.stdout == ""
        # Nothing staged to pending/.
        pending_dir = tmp_path / ".spanweave" / "memory" / "pending"
        staged = list(pending_dir.rglob("*.md")) if pending_dir.exists() else []
        assert staged == []

    def test_extract_latest_backstop_on_ollama_error(self, tmp_path: Path) -> None:
        """Probe passes but extraction raises OllamaNotAvailableError -> exit 0, quiet."""
        from spanweave.cli.main import main
        from spanweave.learning.extractor import OllamaNotAvailableError

        runner = CliRunner()

        with (
            claude_session(SAMPLE_SESSION),
            patch(
                "spanweave.cli.commands.extract_latest.ollama_available",
                return_value=True,
            ),
            patch(
                "spanweave.learning.extractor._call_ollama",
                side_effect=OllamaNotAvailableError(
                    "Ollama not running. Install: https://ollama.ai then "
                    "`ollama pull gemma4:e4b`"
                ),
            ),
        ):
            result = runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
            )

        assert result.exit_code == 0
        assert result.stdout == ""
        pending_dir = tmp_path / ".spanweave" / "memory" / "pending"
        staged = list(pending_dir.rglob("*.md")) if pending_dir.exists() else []
        assert staged == []

    def test_extract_latest_success_when_ollama_up(self, tmp_path: Path) -> None:
        """When Ollama is available, extract + stage + print summary."""
        from spanweave.cli.main import main

        mock_response = json.dumps([
            {
                "type": "decision",
                "body": "Use Pydantic v2",
                "reasoning": "Better performance",
                "tags": ["deps"],
                "confidence": 0.9,
            }
        ])

        runner = CliRunner()

        with (
            claude_session(SAMPLE_SESSION),
            patch(
                "spanweave.cli.commands.extract_latest.ollama_available",
                return_value=True,
            ),
            patch(
                "spanweave.learning.extractor._call_ollama",
                return_value=mock_response,
            ),
        ):
            result = runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
            )

        assert result.exit_code == 0
        assert "Extracted" in result.stdout
        pending_dir = tmp_path / ".spanweave" / "memory" / "pending" / "decisions"
        assert pending_dir.exists()
        assert list(pending_dir.glob("*.md"))

    def test_extract_latest_no_sessions_found(self, tmp_path: Path) -> None:
        """No session files for an explicit tool -> clean error (not the Ollama path)."""
        from spanweave.cli.main import main

        runner = CliRunner()

        with claude_session(None):
            result = runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
            )

        # No session is a different failure mode from Ollama-down; for an
        # explicit --tool it stays an error.
        assert result.exit_code != 0


class TestExtractLatestModelAndWindow:
    """extract-latest uses the quality model in both watermark and recency modes."""

    def test_default_uses_watermark_mode_with_quality_model(
        self, tmp_path: Path
    ) -> None:
        """Default (no --recent) bypasses extract_from_session entirely and
        runs the watermark pipeline with the gemma quality model."""
        from spanweave.cli.main import main

        runner = CliRunner()
        with (
            claude_session(SAMPLE_SESSION),
            patch("spanweave.cli.commands.extract_latest.ollama_available", return_value=True),
            patch(
                "spanweave.cli.commands.extract_latest._run_watermark_extraction",
                return_value=0,
            ) as m,
            patch(
                "spanweave.learning.extractor.extract_from_session"
            ) as legacy,
        ):
            result = runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
            )

        assert result.exit_code == 0
        # Watermark path is the default; legacy recency window is bypassed.
        m.assert_called_once()
        assert m.call_args.kwargs.get("model") == "gemma4:e4b"
        legacy.assert_not_called()

    def test_explicit_recent_uses_legacy_path_with_quality_model(
        self, tmp_path: Path
    ) -> None:
        from spanweave.cli.main import main

        runner = CliRunner()
        with (
            claude_session(SAMPLE_SESSION),
            patch("spanweave.cli.commands.extract_latest.ollama_available", return_value=True),
            patch(
                "spanweave.learning.extractor.extract_from_session", return_value=[]
            ) as m,
            patch(
                "spanweave.cli.commands.extract_latest._run_watermark_extraction"
            ) as wm,
        ):
            result = runner.invoke(
                main,
                [
                    "extract-latest",
                    "--repo",
                    str(tmp_path),
                    "--tool",
                    "claude-code",
                    "--recent",
                    "12",
                ],
            )

        assert result.exit_code == 0
        assert m.call_args.kwargs.get("model") == "gemma4:e4b"
        assert m.call_args.kwargs.get("recent_chunks") == 12
        # And the watermark path is NOT used when --recent is explicit.
        wm.assert_not_called()


class TestExtractLatestDetach:
    """--detach makes the hook a fast launcher: spawn a worker, return immediately."""

    def test_detach_spawns_worker_and_does_not_extract_inline(self, tmp_path: Path) -> None:
        from spanweave.cli.main import main

        runner = CliRunner()
        with (
            claude_session(SAMPLE_SESSION),
            patch("spanweave.cli.commands.extract_latest._spawn_detached") as spawn,
            patch("spanweave.learning.extractor.extract_from_session") as extract,
        ):
            result = runner.invoke(
                main,
                ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code", "--detach"],
            )

        assert result.exit_code == 0
        spawn.assert_called_once()
        extract.assert_not_called()  # the launcher must not block on extraction

    def test_detach_no_session_still_errors(self, tmp_path: Path) -> None:
        from spanweave.cli.main import main

        runner = CliRunner()
        with claude_session(None):
            result = runner.invoke(
                main,
                ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code", "--detach"],
            )
        assert result.exit_code != 0


class TestExtractLatestSingleFlight:
    """A second worker must no-op while a live extraction holds the lock."""

    def test_worker_skips_when_lock_held(self, tmp_path: Path) -> None:
        from spanweave.cli.main import main

        runner = CliRunner()
        with (
            claude_session(SAMPLE_SESSION),
            patch("spanweave.cli.commands.extract_latest._acquire_lock", return_value=False),
            patch("spanweave.cli.commands.extract_latest.ollama_available", return_value=True),
            patch("spanweave.learning.extractor.extract_from_session") as extract,
        ):
            result = runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
            )

        assert result.exit_code == 0
        extract.assert_not_called()


class TestExtractLatestLock:
    """The PID lockfile primitive: fresh acquire, live-held reject, stale steal."""

    def test_acquire_then_reject_then_release(self, tmp_path: Path) -> None:
        from spanweave.cli.commands.extract_latest import _acquire_lock, _release_lock

        lock = tmp_path / "extract.lock"
        assert _acquire_lock(lock) is True
        assert lock.exists()
        # This (alive) PID already holds it -> a second acquire is refused.
        assert _acquire_lock(lock) is False
        _release_lock(lock)
        assert not lock.exists()

    def test_acquire_steals_stale_lock(self, tmp_path: Path) -> None:
        from spanweave.cli.commands.extract_latest import _acquire_lock

        lock = tmp_path / "extract.lock"
        lock.write_text("not-a-pid", encoding="utf-8")  # unreadable PID -> stale
        assert _acquire_lock(lock) is True


def _make_session(tmp_path: Path, name: str = "session.jsonl") -> Path:
    """Build a minimal valid JSONL session in tmp_path and return its Path."""
    path = tmp_path / name
    path.write_text(
        "\n".join([
            json.dumps({"type": "user", "message": "first question"}),
            json.dumps({"type": "assistant", "message": "first answer"}),
        ])
        + "\n",
        encoding="utf-8",
    )
    return path


def _append(path: Path, lines: list[dict[str, str]]) -> None:
    with path.open("a", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")


def _mock_response(decisions: list[dict[str, Any]] | None = None) -> str:
    if decisions is None:
        decisions = [
            {
                "type": "decision",
                "body": "Use Pydantic v2",
                "reasoning": "Better perf",
                "tags": ["deps"],
                "confidence": 0.9,
            }
        ]
    return json.dumps(decisions)


class TestExtractLatestWatermark:
    """extract-latest writes a per-source byte-offset watermark, processes deltas.

    The hook fires every session end, so without a watermark we'd
    re-process the same recency window on every fire. The watermark records
    the byte offset of EOF after the last successful run; subsequent fires
    pass that offset to ``chunk_session_from_offset`` to chunk only new bytes.

    Since the multi-source refactor the watermark filename is per-tool
    (``extract-latest-<tool>.watermark``).

    Failure modes covered:
    - first fire creates the watermark file
    - second fire with no new bytes is a no-op
    - second fire with new bytes processes only the delta
    - truncation (file < watermark) resets to byte 0
    - different session_path resets to byte 0
    - worker crash mid-stage does NOT advance the watermark
    - explicit ``--recent N`` ignores the watermark (manual override)
    """

    def _watermark_path(self, repo: Path, tool: str = "claude-code") -> Path:
        return repo / ".spanweave" / "daemon" / f"extract-latest-{tool}.watermark"

    def _read_watermark(self, repo: Path, tool: str = "claude-code") -> dict[str, Any]:
        return json.loads(self._watermark_path(repo, tool).read_text(encoding="utf-8"))

    def test_first_fire_creates_watermark(self, tmp_path: Path) -> None:
        from spanweave.cli.main import main

        session = _make_session(tmp_path)
        runner = CliRunner()
        with (
            claude_session(session),
            patch(
                "spanweave.cli.commands.extract_latest.ollama_available",
                return_value=True,
            ),
            patch(
                "spanweave.learning.extractor._call_ollama",
                return_value=_mock_response(),
            ),
        ):
            result = runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
            )

        assert result.exit_code == 0
        wm_path = self._watermark_path(tmp_path)
        assert wm_path.exists()
        wm = self._read_watermark(tmp_path)
        assert wm["session_path"] == str(session)
        # Watermark must record EOF after the read.
        assert wm["byte_offset"] == session.stat().st_size
        assert "last_advanced_at" in wm

    def test_second_fire_no_new_bytes_is_noop(self, tmp_path: Path) -> None:
        from spanweave.cli.main import main

        session = _make_session(tmp_path)
        runner = CliRunner()
        with (
            claude_session(session),
            patch(
                "spanweave.cli.commands.extract_latest.ollama_available",
                return_value=True,
            ),
            patch(
                "spanweave.learning.extractor._call_ollama",
                return_value=_mock_response(),
            ) as call_mock,
        ):
            # First fire processes everything.
            runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
            )
            first_calls = call_mock.call_count
            wm_before = self._read_watermark(tmp_path)

            # Second fire with no appended bytes: no new chunks -> no model calls.
            result = runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
            )

        assert result.exit_code == 0
        # No additional Ollama calls because there were no new chunks.
        assert call_mock.call_count == first_calls
        wm_after = self._read_watermark(tmp_path)
        assert wm_after["byte_offset"] == wm_before["byte_offset"]

    def test_second_fire_with_appended_bytes_processes_only_delta(
        self, tmp_path: Path
    ) -> None:
        from spanweave.cli.main import main

        session = _make_session(tmp_path)
        runner = CliRunner()

        seen_chunks: list[str] = []

        def _record(prompt: str, *_a: Any, **_k: Any) -> str:
            # Record only the chunk contents (after "Conversation:\n---\n").
            marker = "Conversation:\n---\n"
            if marker in prompt:
                seen_chunks.append(prompt.split(marker, 1)[1])
            return _mock_response()

        with (
            claude_session(session),
            patch(
                "spanweave.cli.commands.extract_latest.ollama_available",
                return_value=True,
            ),
            patch(
                "spanweave.learning.extractor._call_ollama",
                side_effect=_record,
            ),
        ):
            runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
            )
            seen_after_first = list(seen_chunks)
            seen_chunks.clear()

            # Append two NEW messages and fire again.
            _append(
                session,
                [
                    {"type": "user", "message": "brand new question"},
                    {"type": "assistant", "message": "brand new answer"},
                ],
            )
            result = runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
            )

        assert result.exit_code == 0
        assert seen_after_first, "first fire should have processed initial bytes"
        # Second fire's chunks should only contain the new content, never the
        # old already-processed messages.
        joined = "\n".join(seen_chunks)
        assert "brand new" in joined
        assert "first question" not in joined
        assert "first answer" not in joined

    def test_truncated_file_resets_watermark_to_zero(self, tmp_path: Path) -> None:
        from spanweave.cli.main import main

        session = _make_session(tmp_path)
        runner = CliRunner()
        with (
            claude_session(session),
            patch(
                "spanweave.cli.commands.extract_latest.ollama_available",
                return_value=True,
            ),
            patch(
                "spanweave.learning.extractor._call_ollama",
                return_value=_mock_response(),
            ),
        ):
            runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
            )
            wm_before = self._read_watermark(tmp_path)
            assert wm_before["byte_offset"] > 0

            # Truncate to one short line.
            session.write_text(
                json.dumps({"type": "user", "message": "fresh"}) + "\n",
                encoding="utf-8",
            )
            new_size = session.stat().st_size
            assert new_size < wm_before["byte_offset"]

            result = runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
            )

        assert result.exit_code == 0
        wm_after = self._read_watermark(tmp_path)
        # After processing a truncated file from offset 0, watermark is the new size.
        assert wm_after["byte_offset"] == new_size

    def test_different_session_path_resets_watermark_to_zero(
        self, tmp_path: Path
    ) -> None:
        from spanweave.cli.main import main

        session_a = _make_session(tmp_path, "a.jsonl")
        session_b = _make_session(tmp_path, "b.jsonl")
        runner = CliRunner()

        seen_chunks: list[str] = []

        def _record(prompt: str, *_a: Any, **_k: Any) -> str:
            marker = "Conversation:\n---\n"
            if marker in prompt:
                seen_chunks.append(prompt.split(marker, 1)[1])
            return _mock_response()

        with (
            patch(
                "spanweave.cli.commands.extract_latest.ollama_available",
                return_value=True,
            ),
            patch(
                "spanweave.learning.extractor._call_ollama",
                side_effect=_record,
            ),
        ):
            # First fire on session A.
            with claude_session(session_a):
                runner.invoke(
                    main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
                )
            wm_a = self._read_watermark(tmp_path)
            assert wm_a["session_path"] == str(session_a)
            seen_chunks.clear()

            # Second fire on session B: must reset and process B fully.
            with claude_session(session_b):
                result = runner.invoke(
                    main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
                )

        assert result.exit_code == 0
        wm_b = self._read_watermark(tmp_path)
        assert wm_b["session_path"] == str(session_b)
        assert wm_b["byte_offset"] == session_b.stat().st_size
        # And session B's chunks were actually processed (not skipped).
        assert seen_chunks, "session B should have been chunked from byte 0"

    def test_worker_crash_does_not_advance_watermark(self, tmp_path: Path) -> None:
        """If staging raises mid-run, watermark stays at its prior value.

        Next fire then re-processes the same window; dedup is the safety net.
        """
        from spanweave.cli.main import main

        session = _make_session(tmp_path)
        runner = CliRunner()

        # Pre-seed a watermark by doing a first successful fire.
        with (
            claude_session(session),
            patch(
                "spanweave.cli.commands.extract_latest.ollama_available",
                return_value=True,
            ),
            patch(
                "spanweave.learning.extractor._call_ollama",
                return_value=_mock_response(),
            ),
        ):
            runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"]
            )

        wm_before = self._read_watermark(tmp_path)
        _append(session, [{"type": "user", "message": "new line"}])

        # Now make the staging step crash and verify watermark stays put.
        with (
            claude_session(session),
            patch(
                "spanweave.cli.commands.extract_latest.ollama_available",
                return_value=True,
            ),
            patch(
                "spanweave.learning.extractor._call_ollama",
                return_value=_mock_response(),
            ),
            patch(
                "spanweave.learning.extractor.stage_pending_decisions",
                side_effect=RuntimeError("disk full"),
            ),
        ):
            with pytest.raises(RuntimeError):
                runner.invoke(
                    main,
                    ["extract-latest", "--repo", str(tmp_path), "--tool", "claude-code"],
                    catch_exceptions=False,
                )

        wm_after = self._read_watermark(tmp_path)
        assert wm_after["byte_offset"] == wm_before["byte_offset"]

    def test_explicit_recent_ignores_watermark(self, tmp_path: Path) -> None:
        """--recent N is the manual override: use recency window, skip watermark."""
        from spanweave.cli.main import main

        session = _make_session(tmp_path)
        # Make sure there are >= 5 messages so --recent 5 has something to bound.
        _append(
            session,
            [
                {"type": "user", "message": f"q{i}"} for i in range(6)
            ],
        )
        runner = CliRunner()

        captured: dict[str, Any] = {}

        def _capture(
            sp: Path, *, model: Any, repo_root: Path, recent_chunks: Any, **kw: Any
        ) -> list[dict[str, Any]]:
            captured["recent_chunks"] = recent_chunks
            captured["call_kwargs"] = kw
            return []

        with (
            claude_session(session),
            patch(
                "spanweave.cli.commands.extract_latest.ollama_available",
                return_value=True,
            ),
            patch(
                "spanweave.learning.extractor.extract_from_session",
                side_effect=_capture,
            ),
        ):
            result = runner.invoke(
                main,
                [
                    "extract-latest",
                    "--repo",
                    str(tmp_path),
                    "--tool",
                    "claude-code",
                    "--recent",
                    "5",
                ],
            )

        assert result.exit_code == 0
        # The explicit override flows through; watermark file is NOT created.
        assert captured["recent_chunks"] == 5
        assert not self._watermark_path(tmp_path).exists()
