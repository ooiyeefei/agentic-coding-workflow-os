from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from spanweave.cli.main import main


def _json_output(result_output: str) -> object:
    return json.loads(result_output)


def test_help_prints_overview() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "Spanweave" in result.output
    assert "init" in result.output
    assert "extract" in result.output
    assert "grep" in result.output
    assert "Examples:" in result.output
    assert "spanweave init --tool claude-code --repo ." in result.output


@pytest.mark.parametrize(
    ("argv", "needles"),
    [
        (
            ["init", "--help"],
            [
                "Examples:",
                "idempotent and does not overwrite existing workspace files",
                "Examples:\n\n    spanweave init --repo .",
            ],
        ),
        (
            ["grep", "--help"],
            [
                "Examples:",
                "pattern is treated as a Python regular expression",
                "Examples:\n\n    spanweave grep 'issue #42' --repo .",
            ],
        ),
    ],
)
def test_command_help_includes_examples_and_guidance(
    argv: list[str],
    needles: list[str],
) -> None:
    runner = CliRunner()

    result = runner.invoke(main, argv)

    assert result.exit_code == 0
    for needle in needles:
        assert needle in result.output


def test_init_scaffolds_spanweave_workspace(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["init", "--repo", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = _json_output(result.output)
    assert isinstance(payload, dict)
    assert payload["changed"] is True
    assert (tmp_path / ".spanweave" / "memory" / "decisions").is_dir()
    assert (tmp_path / ".spanweave" / "sharing.yaml").is_file()


def test_init_does_not_scaffold_removed_workflow_dirs(tmp_path: Path) -> None:
    """Workflow engine is gone: no runs/, workflows/, daemon/ scaffolding."""
    runner = CliRunner()

    result = runner.invoke(main, ["init", "--repo", str(tmp_path)])

    assert result.exit_code == 0
    assert not (tmp_path / ".spanweave" / "runs").exists()
    assert not (tmp_path / ".spanweave" / "workflows").exists()
    assert not (tmp_path / ".spanweave" / "daemon").exists()


def test_removed_commands_are_no_longer_registered() -> None:
    """Workflow-engine commands must be gone after the ambient-memory pivot."""
    runner = CliRunner()

    for argv in (
        ["run", "--help"],
        ["resume", "--help"],
        ["prompt", "--help"],
        ["cleanup", "--help"],
        ["daemon", "--help"],
        ["ingest", "--help"],
        ["context", "--help"],
    ):
        result = runner.invoke(main, argv)
        assert (
            result.exit_code != 0
        ), f"command {argv[0]!r} should be removed but is still registered"


def test_grep_runs_against_empty_workspace(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(main, ["init", "--repo", str(tmp_path)])

    result = runner.invoke(
        main,
        ["grep", "anything", "--repo", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    payload = _json_output(result.output)
    assert isinstance(payload, dict)
    assert payload["match_count"] == 0
