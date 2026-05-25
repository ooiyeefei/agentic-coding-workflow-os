"""Tests for the spanweave extract-latest CLI command (hook-invoked).

extract-latest is wired as a Claude Code Stop hook, so it must degrade
gracefully when Ollama is unavailable: a quiet no-op that exits 0 rather
than erroring (which Claude Code surfaces as a scary Stop hook error).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_SESSION = FIXTURES_DIR / "sample_session.jsonl"


class TestExtractLatestGracefulDegradation:
    """extract-latest must be a silent, exit-0 no-op when Ollama is down."""

    def test_extract_latest_quiet_noop_when_ollama_down(self, tmp_path: Path) -> None:
        """Probe says Ollama is down -> exit 0, no stdout, nothing staged."""
        from spanweave.cli.main import main

        runner = CliRunner()

        with (
            patch(
                "spanweave.cli.commands.extract_latest._find_latest_session",
                return_value=SAMPLE_SESSION,
            ),
            patch(
                "spanweave.cli.commands.extract_latest.ollama_available",
                return_value=False,
            ),
        ):
            result = runner.invoke(main, ["extract-latest", "--repo", str(tmp_path)])

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
            patch(
                "spanweave.cli.commands.extract_latest._find_latest_session",
                return_value=SAMPLE_SESSION,
            ),
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
            result = runner.invoke(main, ["extract-latest", "--repo", str(tmp_path)])

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
            patch(
                "spanweave.cli.commands.extract_latest._find_latest_session",
                return_value=SAMPLE_SESSION,
            ),
            patch(
                "spanweave.cli.commands.extract_latest.ollama_available",
                return_value=True,
            ),
            patch(
                "spanweave.learning.extractor._call_ollama",
                return_value=mock_response,
            ),
        ):
            result = runner.invoke(main, ["extract-latest", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        assert "Extracted" in result.stdout
        pending_dir = tmp_path / ".spanweave" / "memory" / "pending" / "decisions"
        assert pending_dir.exists()
        assert list(pending_dir.glob("*.md"))

    def test_extract_latest_no_sessions_found(self, tmp_path: Path) -> None:
        """No session files -> clean error (this is not the Ollama path)."""
        from spanweave.cli.main import main

        runner = CliRunner()

        with patch(
            "spanweave.cli.commands.extract_latest._find_latest_session",
            return_value=None,
        ):
            result = runner.invoke(main, ["extract-latest", "--repo", str(tmp_path)])

        # No session is a different failure mode from Ollama-down; it stays an error.
        assert result.exit_code != 0


class TestExtractLatestModelAndWindow:
    """extract-latest defaults to the quality model and bounds work to recent chunks."""

    def test_defaults_to_quality_model_and_bounded_window(self, tmp_path: Path) -> None:
        from spanweave.cli.main import main

        runner = CliRunner()
        with (
            patch(
                "spanweave.cli.commands.extract_latest._find_latest_session",
                return_value=SAMPLE_SESSION,
            ),
            patch("spanweave.cli.commands.extract_latest.ollama_available", return_value=True),
            patch(
                "spanweave.learning.extractor.extract_from_session", return_value=[]
            ) as m,
        ):
            result = runner.invoke(main, ["extract-latest", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        assert m.call_args.kwargs.get("model") == "gemma4:e4b"
        # Hook path must be bounded, not a full-session run.
        assert m.call_args.kwargs.get("recent_chunks") is not None
        assert m.call_args.kwargs["recent_chunks"] > 0


class TestExtractLatestDetach:
    """--detach makes the hook a fast launcher: spawn a worker, return immediately."""

    def test_detach_spawns_worker_and_does_not_extract_inline(self, tmp_path: Path) -> None:
        from spanweave.cli.main import main

        runner = CliRunner()
        with (
            patch(
                "spanweave.cli.commands.extract_latest._find_latest_session",
                return_value=SAMPLE_SESSION,
            ),
            patch("spanweave.cli.commands.extract_latest._spawn_detached") as spawn,
            patch("spanweave.learning.extractor.extract_from_session") as extract,
        ):
            result = runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--detach"]
            )

        assert result.exit_code == 0
        spawn.assert_called_once()
        extract.assert_not_called()  # the launcher must not block on extraction

    def test_detach_no_session_still_errors(self, tmp_path: Path) -> None:
        from spanweave.cli.main import main

        runner = CliRunner()
        with patch(
            "spanweave.cli.commands.extract_latest._find_latest_session", return_value=None
        ):
            result = runner.invoke(
                main, ["extract-latest", "--repo", str(tmp_path), "--detach"]
            )
        assert result.exit_code != 0


class TestExtractLatestSingleFlight:
    """A second worker must no-op while a live extraction holds the lock."""

    def test_worker_skips_when_lock_held(self, tmp_path: Path) -> None:
        from spanweave.cli.main import main

        runner = CliRunner()
        with (
            patch(
                "spanweave.cli.commands.extract_latest._find_latest_session",
                return_value=SAMPLE_SESSION,
            ),
            patch("spanweave.cli.commands.extract_latest._acquire_lock", return_value=False),
            patch("spanweave.cli.commands.extract_latest.ollama_available", return_value=True),
            patch("spanweave.learning.extractor.extract_from_session") as extract,
        ):
            result = runner.invoke(main, ["extract-latest", "--repo", str(tmp_path)])

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
