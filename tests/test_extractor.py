"""Tests for the decision extraction pipeline and CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_SESSION = FIXTURES_DIR / "sample_session.jsonl"


class TestChunkSession:
    """Tests for chunk_session splitting logic."""

    def test_chunk_session_splits_conversation(self) -> None:
        """Verify chunking produces non-empty chunks from a fixture JSONL."""
        from spanweave.learning.extractor import chunk_session

        chunks = chunk_session(SAMPLE_SESSION, max_tokens=2000)

        assert len(chunks) > 0
        for chunk in chunks:
            assert len(chunk.strip()) > 0

    def test_chunk_session_respects_max_tokens(self) -> None:
        """Verify chunks are within the approximate token limit."""
        from spanweave.learning.extractor import chunk_session

        # Use a small token limit to force multiple chunks
        chunks = chunk_session(SAMPLE_SESSION, max_tokens=200)

        assert len(chunks) > 1
        for chunk in chunks:
            # Approximate: 4 chars per token
            estimated_tokens = len(chunk) / 4
            # Allow some overshoot for message boundary alignment
            assert estimated_tokens < 400  # 2x tolerance

    def test_chunk_session_missing_file(self) -> None:
        """Verify FileNotFoundError for missing session file."""
        from spanweave.learning.extractor import chunk_session

        with pytest.raises(FileNotFoundError):
            chunk_session(Path("/nonexistent/session.jsonl"))


class TestExtractDecisionsFromChunk:
    """Tests for the LLM extraction from a single chunk."""

    def test_extract_decisions_from_chunk_parses_json_response(self) -> None:
        """Mock the Ollama HTTP call, verify parsed output."""
        from spanweave.learning.extractor import extract_decisions_from_chunk

        mock_response = json.dumps([
            {
                "type": "decision",
                "body": "Use Pydantic v2 for data validation",
                "reasoning": "5-50x faster validation, cleaner API",
                "tags": ["dependencies", "validation"],
                "confidence": 0.9,
            }
        ])

        with patch("spanweave.learning.extractor._call_ollama", return_value=mock_response):
            results = extract_decisions_from_chunk("some conversation chunk")

        assert len(results) == 1
        assert results[0]["type"] == "decision"
        assert results[0]["body"] == "Use Pydantic v2 for data validation"
        assert results[0]["confidence"] == 0.9

    def test_extract_decisions_from_chunk_handles_invalid_json(self) -> None:
        """Verify graceful fallback on bad model output."""
        from spanweave.learning.extractor import extract_decisions_from_chunk

        with patch(
            "spanweave.learning.extractor._call_ollama",
            return_value="This is not valid JSON at all",
        ):
            results = extract_decisions_from_chunk("some conversation chunk")

        assert results == []

    def test_extract_decisions_from_chunk_handles_partial_json(self) -> None:
        """Verify graceful handling when model outputs text around JSON."""
        from spanweave.learning.extractor import extract_decisions_from_chunk

        mock_response = (
            "Here are the decisions:\n"
            '[{"type": "decision", "body": "Use pytest", '
            '"reasoning": "Better than unittest", '
            '"tags": ["testing"], "confidence": 0.8}]'
        )

        with patch(
            "spanweave.learning.extractor._call_ollama", return_value=mock_response
        ):
            results = extract_decisions_from_chunk("some conversation chunk")

        assert len(results) == 1
        assert results[0]["body"] == "Use pytest"

    def test_extract_decisions_ollama_not_available(self) -> None:
        """Verify OllamaNotAvailableError when Ollama is not running."""
        from spanweave.learning.extractor import (
            OllamaNotAvailableError,
            extract_decisions_from_chunk,
        )

        with patch(
            "spanweave.learning.extractor._call_ollama",
            side_effect=OllamaNotAvailableError(
                "Ollama not running. Install: https://ollama.ai then `ollama pull gemma4:e4b`"
            ),
        ):
            with pytest.raises(OllamaNotAvailableError):
                extract_decisions_from_chunk("some chunk")


class TestStagePendingDecisions:
    """Tests for staging decisions as pending markdown files."""

    def test_stage_pending_decisions_writes_files(self, tmp_path: Path) -> None:
        """Verify files are written to pending/ with correct frontmatter."""
        from spanweave.learning.extractor import stage_pending_decisions

        decisions: list[dict[str, Any]] = [
            {
                "type": "decision",
                "body": "Use Pydantic v2 for data validation",
                "reasoning": "5-50x faster validation, cleaner API",
                "tags": ["dependencies", "validation"],
                "confidence": 0.9,
            },
            {
                "type": "finding",
                "body": "Files-first approach avoids database complexity",
                "reasoning": "Record count stays manageable",
                "tags": ["architecture"],
                "confidence": 0.85,
            },
        ]

        paths = stage_pending_decisions(decisions, repo_root=tmp_path, source="test-extraction")

        assert len(paths) == 2
        pending_dir = tmp_path / ".spanweave" / "memory" / "pending" / "decisions"
        assert pending_dir.exists()

        for path in paths:
            assert path.exists()
            assert path.suffix == ".md"
            content = path.read_text()
            assert "---" in content  # YAML frontmatter delimiter


class TestDedupeAgainstExisting:
    """Tests for deduplication logic."""

    def test_dedupe_filters_existing(self, tmp_path: Path) -> None:
        """Verify dedup logic works for overlapping decisions."""
        from spanweave.learning.extractor import dedupe_against_existing

        # Create an existing decision
        decisions_dir = tmp_path / ".spanweave" / "memory" / "decisions"
        decisions_dir.mkdir(parents=True)
        existing = decisions_dir / "existing_decision.md"
        existing.write_text(
            "---\ntype: decision\n---\nUse Pydantic v2 for data validation in this project.\n"
        )

        candidates: list[dict[str, Any]] = [
            {
                "type": "decision",
                "body": "Use Pydantic v2 for data validation in this project",
                "reasoning": "Performance",
                "tags": [],
                "confidence": 0.9,
            },
            {
                "type": "decision",
                "body": "Use pytest as the test framework with function-based tests",
                "reasoning": "Better ergonomics",
                "tags": ["testing"],
                "confidence": 0.8,
            },
        ]

        filtered = dedupe_against_existing(candidates, repo_root=tmp_path)

        # The first one overlaps >80% with existing, should be filtered
        assert len(filtered) == 1
        assert filtered[0]["body"] == "Use pytest as the test framework with function-based tests"

    def test_dedupe_keeps_all_when_no_existing(self, tmp_path: Path) -> None:
        """Verify all candidates pass when no existing decisions."""
        from spanweave.learning.extractor import dedupe_against_existing

        candidates: list[dict[str, Any]] = [
            {
                "type": "decision",
                "body": "Use pytest",
                "reasoning": "x",
                "tags": [],
                "confidence": 0.9,
            },
        ]

        filtered = dedupe_against_existing(candidates, repo_root=tmp_path)
        assert len(filtered) == 1


class TestReviewCommand:
    """Tests for the spanweave review CLI command."""

    def test_review_command_auto_accept(self, tmp_path: Path) -> None:
        """Use CliRunner with --auto-accept to verify non-interactive path."""
        from spanweave.cli.main import main

        # Create a pending decision
        pending_dir = tmp_path / ".spanweave" / "memory" / "pending" / "decisions"
        pending_dir.mkdir(parents=True)
        pending_file = pending_dir / "test_decision.md"
        pending_file.write_text(
            "---\ntype: decision\nsource: auto-extraction\n"
            "confidence: 0.9\ntags:\n- testing\n---\n"
            "Use pytest for all tests.\n"
        )

        runner = CliRunner()
        result = runner.invoke(main, ["review", "--repo", str(tmp_path), "--auto-accept"])

        assert result.exit_code == 0
        assert "Accepted" in result.output

        # Pending file should be moved to confirmed
        assert not pending_file.exists()
        confirmed_dir = tmp_path / ".spanweave" / "memory" / "decisions"
        assert confirmed_dir.exists()
        confirmed_files = list(confirmed_dir.iterdir())
        assert len(confirmed_files) == 1

    def test_review_command_empty_pending(self, tmp_path: Path) -> None:
        """Verify clean exit when nothing to review."""
        from spanweave.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["review", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        assert "No pending learnings" in result.output


class TestExtractCommand:
    """Tests for the spanweave extract CLI command."""

    def test_extract_command_ollama_not_running(self, tmp_path: Path) -> None:
        """Verify helpful error message when Ollama is not available."""
        from spanweave.cli.main import main
        from spanweave.learning.extractor import OllamaNotAvailableError

        runner = CliRunner()

        with patch(
            "spanweave.learning.extractor._call_ollama",
            side_effect=OllamaNotAvailableError(
                "Ollama not running. Install: https://ollama.ai then `ollama pull gemma4:e4b`"
            ),
        ):
            result = runner.invoke(
                main, ["extract", "--session", str(SAMPLE_SESSION), "--repo", str(tmp_path)]
            )

        assert result.exit_code != 0
        assert "Ollama not running" in result.output

    def test_extract_command_success(self, tmp_path: Path) -> None:
        """Verify successful extraction flow with mocked Ollama."""
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

        with patch("spanweave.learning.extractor._call_ollama", return_value=mock_response):
            result = runner.invoke(
                main, ["extract", "--session", str(SAMPLE_SESSION), "--repo", str(tmp_path)]
            )

        assert result.exit_code == 0
        assert "Extracted" in result.output
