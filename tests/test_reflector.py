"""Tests for the auto-reflection pipeline and CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from click.testing import CliRunner


def _create_decision_files(repo_root: Path, count: int) -> list[Path]:
    """Helper: create N decision markdown files in .spanweave/memory/decisions/."""
    decisions_dir = repo_root / ".spanweave" / "memory" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for i in range(count):
        content = (
            f"---\n"
            f"type: decision\n"
            f"source: test\n"
            f"confidence: 0.{8 + (i % 2)}\n"
            f"reasoning: Reason {i}\n"
            f"timestamp: 2026-05-{20 + i:02d}T10:00:00+00:00\n"
            f"tags:\n- architecture\n"
            f"---\n"
            f"Decision body number {i}: use pattern {i} for feature {i}.\n"
        )
        filepath = decisions_dir / f"decision_{i:04d}.md"
        filepath.write_text(content, encoding="utf-8")
        paths.append(filepath)

    return paths


class TestGatherRecentDecisions:
    """Tests for _gather_recent_decisions reading from memory."""

    def test_gather_recent_decisions_reads_from_memory(self, tmp_path: Path) -> None:
        """Verify it finds decisions on disk."""
        from spanweave.learning.reflector import _gather_recent_decisions

        _create_decision_files(tmp_path, 5)
        decisions = _gather_recent_decisions(tmp_path, max_count=20)

        assert len(decisions) == 5
        for d in decisions:
            assert "body" in d
            assert "id" in d

    def test_gather_recent_decisions_respects_max_count(self, tmp_path: Path) -> None:
        """Verify max_count limits the returned decisions."""
        from spanweave.learning.reflector import _gather_recent_decisions

        _create_decision_files(tmp_path, 10)
        decisions = _gather_recent_decisions(tmp_path, max_count=5)

        assert len(decisions) == 5

    def test_gather_recent_decisions_empty_repo(self, tmp_path: Path) -> None:
        """Verify empty list when no decisions exist."""
        from spanweave.learning.reflector import _gather_recent_decisions

        decisions = _gather_recent_decisions(tmp_path, max_count=20)
        assert decisions == []


class TestReflectOnDecisions:
    """Tests for the reflect_on_decisions function."""

    def test_reflect_returns_none_below_threshold(self, tmp_path: Path) -> None:
        """Fewer than min_decisions -> None."""
        from spanweave.learning.reflector import reflect_on_decisions

        _create_decision_files(tmp_path, 2)

        result = reflect_on_decisions(repo_root=tmp_path, min_decisions=3)
        assert result is None

    def test_reflect_parses_structured_response(self, tmp_path: Path) -> None:
        """Mock Ollama, verify JSON parsing of reflection."""
        from spanweave.learning.reflector import reflect_on_decisions

        _create_decision_files(tmp_path, 5)

        mock_response = json.dumps({
            "lesson": "Rolling windows are preferred over fixed bans for throttling",
            "supporting_decisions": ["decision_0000", "decision_0002"],
            "tags": ["architecture", "throttling"],
            "confidence": 0.82,
            "applies_to": "Any new rate-limiting or throttling feature",
        })

        with patch(
            "spanweave.learning.reflector.call_ollama", return_value=mock_response
        ):
            result = reflect_on_decisions(repo_root=tmp_path, min_decisions=3)

        assert result is not None
        assert result["lesson"] == "Rolling windows are preferred over fixed bans for throttling"
        assert result["confidence"] == 0.82
        assert "architecture" in result["tags"]
        assert "decision_0000" in result["supporting_decisions"]

    def test_reflect_handles_invalid_json(self, tmp_path: Path) -> None:
        """Graceful fallback when model returns non-JSON."""
        from spanweave.learning.reflector import reflect_on_decisions

        _create_decision_files(tmp_path, 5)

        with patch(
            "spanweave.learning.reflector.call_ollama",
            return_value="This is not valid JSON at all, just rambling text.",
        ):
            result = reflect_on_decisions(repo_root=tmp_path, min_decisions=3)

        assert result is None

    def test_reflect_handles_json_embedded_in_text(self, tmp_path: Path) -> None:
        """Verify extraction of JSON from surrounding text."""
        from spanweave.learning.reflector import reflect_on_decisions

        _create_decision_files(tmp_path, 4)

        mock_response = (
            "After analyzing the decisions, here is my reflection:\n"
            '{"lesson": "Always prefer composition over inheritance", '
            '"supporting_decisions": ["decision_0001"], '
            '"tags": ["design"], "confidence": 0.75, '
            '"applies_to": "class hierarchy decisions"}'
        )

        with patch(
            "spanweave.learning.reflector.call_ollama", return_value=mock_response
        ):
            result = reflect_on_decisions(repo_root=tmp_path, min_decisions=3)

        assert result is not None
        assert result["lesson"] == "Always prefer composition over inheritance"


class TestStageReflection:
    """Tests for staging reflection files to disk."""

    def test_stage_reflection_writes_file(self, tmp_path: Path) -> None:
        """Verify frontmatter + body in pending/reflections/."""
        from spanweave.learning.reflector import stage_reflection

        reflection: dict[str, Any] = {
            "lesson": "Rolling windows preferred over fixed bans for throttling",
            "supporting_decisions": ["decision_001", "decision_003"],
            "tags": ["architecture", "throttling"],
            "confidence": 0.82,
            "applies_to": "Any new throttling feature",
        }

        filepath = stage_reflection(reflection, repo_root=tmp_path)

        assert filepath.exists()
        assert filepath.suffix == ".md"
        assert filepath.parent.name == "reflections"
        assert "pending" in str(filepath)

        content = filepath.read_text(encoding="utf-8")
        assert "---" in content
        assert "type: Reflection" in content
        assert "source: auto-reflection" in content
        assert "confidence: 0.82" in content
        assert "Rolling windows preferred over fixed bans" in content
        assert "decision_001" in content

    def test_stage_reflection_creates_directory(self, tmp_path: Path) -> None:
        """Verify pending/reflections/ is created if missing."""
        from spanweave.learning.reflector import stage_reflection

        reflection: dict[str, Any] = {
            "lesson": "Test lesson",
            "supporting_decisions": [],
            "tags": [],
            "confidence": 0.5,
            "applies_to": "",
        }

        filepath = stage_reflection(reflection, repo_root=tmp_path)

        pending_dir = tmp_path / ".spanweave" / "memory" / "pending" / "reflections"
        assert pending_dir.exists()
        assert filepath.exists()


class TestReflectCommand:
    """Tests for the spanweave reflect CLI command."""

    def test_reflect_command_ollama_not_running(self, tmp_path: Path) -> None:
        """Verify helpful error when Ollama is not available."""
        from spanweave.cli.main import main
        from spanweave.learning.ollama_client import OllamaNotAvailableError

        _create_decision_files(tmp_path, 5)

        runner = CliRunner()

        with patch(
            "spanweave.learning.reflector.call_ollama",
            side_effect=OllamaNotAvailableError(
                "Ollama not running. Install: https://ollama.ai then `ollama pull gemma4:e4b`"
            ),
        ):
            result = runner.invoke(main, ["reflect", "--repo", str(tmp_path)])

        assert result.exit_code != 0
        assert "Ollama not running" in result.output

    def test_reflect_command_not_enough_decisions(self, tmp_path: Path) -> None:
        """'Not enough decisions to reflect on (need at least 3)'."""
        from spanweave.cli.main import main

        _create_decision_files(tmp_path, 2)

        runner = CliRunner()
        result = runner.invoke(main, ["reflect", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        assert "Not enough decisions to reflect on" in result.output

    def test_reflect_command_success(self, tmp_path: Path) -> None:
        """Verify successful reflection flow with mocked Ollama."""
        from spanweave.cli.main import main

        _create_decision_files(tmp_path, 5)

        mock_response = json.dumps({
            "lesson": "Prefer rolling windows over fixed bans",
            "supporting_decisions": ["decision_0000", "decision_0001"],
            "tags": ["throttling"],
            "confidence": 0.85,
            "applies_to": "rate limiting features",
        })

        runner = CliRunner()

        with patch(
            "spanweave.learning.reflector.call_ollama", return_value=mock_response
        ):
            result = runner.invoke(main, ["reflect", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        assert "Reflection synthesized" in result.output
        assert "Prefer rolling windows over fixed bans" in result.output
        assert "Staged to:" in result.output

    def test_reflect_command_no_decisions(self, tmp_path: Path) -> None:
        """Verify message when repo has no decisions at all."""
        from spanweave.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["reflect", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        assert "Not enough decisions" in result.output


class TestReviewCommandWithReflections:
    """Tests for spanweave review picking up reflections."""

    def test_review_auto_accept_reflections(self, tmp_path: Path) -> None:
        """Verify reflections are moved to confirmed reflections dir."""
        from spanweave.cli.main import main

        # Create a pending reflection
        pending_dir = tmp_path / ".spanweave" / "memory" / "pending" / "reflections"
        pending_dir.mkdir(parents=True)
        pending_file = pending_dir / "reflection_test.md"
        pending_file.write_text(
            "---\ntype: Reflection\nsource: auto-reflection\n"
            "confidence: 0.8\ntags:\n- architecture\n"
            "supporting_decisions:\n- decision_001\n---\n"
            "Rolling windows preferred.\n"
        )

        runner = CliRunner()
        result = runner.invoke(main, ["review", "--repo", str(tmp_path), "--auto-accept"])

        assert result.exit_code == 0
        assert "Accepted" in result.output

        # Pending file should be moved to routed reflections dir
        # (default policy routes to private/reflections/)
        assert not pending_file.exists()
        # Check both possible locations based on sharing policy
        private_dir = tmp_path / ".spanweave" / "memory" / "private" / "reflections"
        shared_dir = tmp_path / ".spanweave" / "memory" / "shared" / "reflections"
        assert private_dir.exists() or shared_dir.exists()
        dest_dir = private_dir if private_dir.exists() else shared_dir
        confirmed_files = list(dest_dir.iterdir())
        assert len(confirmed_files) == 1

    def test_review_accepts_both_decisions_and_reflections(self, tmp_path: Path) -> None:
        """Verify both types are processed together."""
        from spanweave.cli.main import main

        # Create pending decision
        pending_decisions_dir = tmp_path / ".spanweave" / "memory" / "pending" / "decisions"
        pending_decisions_dir.mkdir(parents=True)
        (pending_decisions_dir / "test_decision.md").write_text(
            "---\ntype: decision\nsource: test\nconfidence: 0.9\ntags: []\n---\nSome decision.\n"
        )

        # Create pending reflection
        pending_reflections_dir = tmp_path / ".spanweave" / "memory" / "pending" / "reflections"
        pending_reflections_dir.mkdir(parents=True)
        (pending_reflections_dir / "test_reflection.md").write_text(
            "---\ntype: Reflection\nsource: auto-reflection\nconfidence: 0.8\n"
            "tags: []\nsupporting_decisions: []\n---\nSome lesson.\n"
        )

        runner = CliRunner()
        result = runner.invoke(main, ["review", "--repo", str(tmp_path), "--auto-accept"])

        assert result.exit_code == 0
        assert "Accepted 2" in result.output
