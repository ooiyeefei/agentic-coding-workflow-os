"""CLI tests for `spanweave eval` (spanweave.cli.commands.eval)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from click.testing import CliRunner
from spanweave.cli.main import main


def _write_record(
    repo_root: Path,
    *,
    subdir: str,
    name: str,
    source: str,
    body: str,
) -> None:
    target_dir = repo_root / ".spanweave" / "memory" / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "---\n"
        "type: decision\n"
        f"source: {source}\n"
        "confidence: 0.9\n"
        "reasoning: test\n"
        "timestamp: 2026-01-01T00:00:00Z\n"
        "tags: []\n"
        "---\n"
        f"{body}\n"
    )
    (target_dir / name).write_text(content, encoding="utf-8")


def test_eval_is_registered_in_main_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "eval" in result.output


def test_eval_help_includes_examples_and_track_guidance() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["eval", "--help"])
    assert result.exit_code == 0
    assert "Examples:" in result.output
    assert "spanweave eval --repo ." in result.output
    assert "Track A" in result.output
    assert "Track B" in result.output


def test_eval_empty_track_a_prints_harvest_hint_and_exits_zero(tmp_path: Path) -> None:
    _write_record(
        tmp_path,
        subdir="pending/decisions",
        name="b.md",
        source="auto-extraction",
        body="an extracted decision with no native counterpart",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["eval", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "spanweave harvest" in result.output


def test_eval_json_emits_counts_and_recall(tmp_path: Path) -> None:
    shared = "always run ruff check before committing python changes to the repo"
    _write_record(
        tmp_path,
        subdir="decisions",
        name="a_match.md",
        source="native-claude",
        body=shared,
    )
    _write_record(
        tmp_path,
        subdir="decisions",
        name="a_gap.md",
        source="native-codex",
        body="adopt hexagonal architecture for the payments service boundary",
    )
    _write_record(
        tmp_path,
        subdir="pending/decisions",
        name="b_match.md",
        source="auto-extraction",
        body="always run ruff check before committing python changes here",
    )
    _write_record(
        tmp_path,
        subdir="pending/decisions",
        name="b_extra.md",
        source="auto-extraction",
        body="bump the docker base image to python 3.12 slim release",
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["eval", "--repo", str(tmp_path), "--threshold", "0.5", "--json"]
    )

    assert result.exit_code == 0
    payload = cast(dict[str, object], json.loads(result.output))
    assert payload["track_a_size"] == 2
    assert payload["track_b_size"] == 2
    counts = cast(dict[str, int], payload["counts"])
    assert counts["intersection"] == 1
    assert counts["a_only"] == 1
    assert counts["b_only"] == 1
    # recall = 1 matched / 2 native = 0.5
    assert payload["recall"] == 0.5


def test_eval_human_report_shows_recall_percentage(tmp_path: Path) -> None:
    shared = "cache the compiled regular expression for the grep command path"
    _write_record(
        tmp_path,
        subdir="decisions",
        name="a.md",
        source="native-claude",
        body=shared,
    )
    _write_record(
        tmp_path,
        subdir="pending/decisions",
        name="b.md",
        source="auto-extraction",
        body=shared,
    )

    runner = CliRunner()
    result = runner.invoke(main, ["eval", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert "recall" in result.output
    assert "100.0%" in result.output


def test_eval_threshold_option_changes_outcome(tmp_path: Path) -> None:
    _write_record(
        tmp_path,
        subdir="decisions",
        name="a.md",
        source="native-claude",
        body="cache the compiled regular expression for the grep command",
    )
    _write_record(
        tmp_path,
        subdir="pending/decisions",
        name="b.md",
        source="auto-extraction",
        body="cache the compiled regular expression results elsewhere now",
    )

    runner = CliRunner()
    low = runner.invoke(
        main, ["eval", "--repo", str(tmp_path), "--threshold", "0.3", "--json"]
    )
    high = runner.invoke(
        main, ["eval", "--repo", str(tmp_path), "--threshold", "0.95", "--json"]
    )

    low_payload = cast(dict[str, object], json.loads(low.output))
    high_payload = cast(dict[str, object], json.loads(high.output))
    assert cast(dict[str, int], low_payload["counts"])["intersection"] == 1
    assert cast(dict[str, int], high_payload["counts"])["intersection"] == 0


def test_eval_no_include_pending_excludes_pending_from_json(tmp_path: Path) -> None:
    _write_record(
        tmp_path,
        subdir="decisions",
        name="a.md",
        source="native-claude",
        body="confirmed native decision living in the decisions directory",
    )
    _write_record(
        tmp_path,
        subdir="pending/decisions",
        name="b.md",
        source="auto-extraction",
        body="pending extracted decision not yet reviewed by a human",
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["eval", "--repo", str(tmp_path), "--no-include-pending", "--json"],
    )

    assert result.exit_code == 0
    payload = cast(dict[str, object], json.loads(result.output))
    # Track B only existed in pending/, so excluding pending empties it.
    assert payload["track_b_size"] == 0
