from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner
from spanweave.cli.main import main
from spanweave.git.worktree import create_worktree
from spanweave.rungraph import create_run
from spanweave.util.paths import run_dir


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _make_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-b", "main", str(repo), cwd=tmp_path)
    _git("config", "user.email", "test@spanweave.test", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    (repo / "README.md").write_text("# Test repo\n", encoding="utf-8")
    _git("add", ".", cwd=repo)
    _git("commit", "-m", "Initial commit", cwd=repo)
    return repo


def _json_output(result_output: str) -> object:
    return json.loads(result_output)


def test_help_prints_overview() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "Spanweave control plane" in result.output
    assert "init" in result.output
    assert "run" in result.output
    assert "cleanup" in result.output
    assert "daemon" in result.output
    assert "grep" in result.output
    assert "Examples:" in result.output
    assert "Examples:\n\n    spanweave init --repo ." in result.output


@pytest.mark.parametrize(
    ("argv", "needles"),
    [
            (
                ["run", "--help"],
                [
                    "Examples:",
                    "Invoke 'spanweave run' directly to start a new workflow run.",
                    "Examples:\n\n    spanweave run --issue 42 --repo .",
                ],
            ),
            (
                ["run", "list", "--help"],
                [
                    "Examples:",
                    "Results are ordered newest-first",
                    "Examples:\n\n    spanweave run list --repo .",
                ],
            ),
            (
                ["run", "show", "--help"],
                [
                    "Examples:",
                    "stored run metadata and stage tree",
                    "Examples:\n\n    spanweave run show run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo .",
                ],
            ),
            (
                ["run", "resume", "--help"],
                [
                    "Examples:",
                    "Without --approve this command only reports the current blocked state.",
                    "spanweave run resume run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo . "
                    "--approve",
                ],
            ),
            (
                ["daemon", "start", "--help"],
                [
                    "Examples:",
                    "does not launch a background HTTP process yet",
                    "Examples:\n\n    spanweave daemon start --repo .",
                ],
            ),
            (
                ["daemon", "stop", "--help"],
                [
                    "Examples:",
                    "does not signal a real daemon yet",
                    "Examples:\n\n    spanweave daemon stop --repo .",
                ],
            ),
            (
                ["daemon", "status", "--help"],
                [
                    "Examples:",
                    "Status is read from .spanweave/daemon/state.json",
                    "Examples:\n\n    spanweave daemon status --repo .",
                ],
            ),
            (
                ["cleanup", "--help"],
                [
                    "Examples:",
                    "Cleanup prompts before removing worktrees unless you pass --yes.",
                    "Examples:\n\n    spanweave cleanup run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo .",
                ],
            ),
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
    assert payload["changed"] is True
    assert (tmp_path / ".spanweave" / "workflows" / "speckit-loop.yaml").is_file()
    assert (tmp_path / ".spanweave" / "memory" / "decisions").is_dir()
    assert (tmp_path / ".spanweave" / "daemon").is_dir()


def test_run_start_list_show_and_grep_json(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(main, ["init", "--repo", str(tmp_path)])

    start = runner.invoke(
        main,
        ["run", "--issue", "42", "--repo", str(tmp_path), "--json"],
    )
    assert start.exit_code == 0
    started = _json_output(start.output)
    run_id = started["run_id"]

    list_result = runner.invoke(
        main,
        ["run", "--repo", str(tmp_path), "list", "--json"],
    )
    assert list_result.exit_code == 0
    listed = _json_output(list_result.output)
    assert listed[0]["run_id"] == run_id
    assert listed[0]["status"] == "running"

    show_result = runner.invoke(
        main,
        ["run", "--repo", str(tmp_path), "show", run_id, "--json"],
    )
    assert show_result.exit_code == 0
    shown = _json_output(show_result.output)
    assert shown["run_id"] == run_id
    assert shown["issue_ref"] == "issue #42"
    assert shown["current_stage"] == "001-specify"

    grep_result = runner.invoke(
        main,
        ["grep", "issue #42", "--repo", str(tmp_path), "--json"],
    )
    assert grep_result.exit_code == 0
    grep_payload = _json_output(grep_result.output)
    assert grep_payload["match_count"] >= 1
    assert any(match["path"].endswith("run.md") for match in grep_payload["matches"])


def test_cleanup_prompts_and_removes_run_worktree(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runner = CliRunner()
    repo = _make_git_repo(tmp_path)
    monkeypatch.chdir(repo)

    run_id = create_run("issue #9")
    worktree_path = create_worktree(run_id, repo_root=repo, worktree_base=tmp_path / "worktrees")
    assert worktree_path.exists()

    result = runner.invoke(
        main,
        ["cleanup", run_id, "--repo", str(repo)],
        input="y\n",
    )

    assert result.exit_code == 0
    assert "Removed 1 worktree" in result.output
    assert not worktree_path.exists()


def test_daemon_start_status_stop_placeholder_state(tmp_path: Path) -> None:
    runner = CliRunner()

    status_before = runner.invoke(
        main,
        ["daemon", "status", "--repo", str(tmp_path), "--json"],
    )
    assert status_before.exit_code == 0
    assert _json_output(status_before.output)["state"] == "stopped"

    start = runner.invoke(
        main,
        ["daemon", "start", "--repo", str(tmp_path), "--json"],
    )
    assert start.exit_code == 0
    start_payload = _json_output(start.output)
    assert start_payload["state"] == "running"
    assert (tmp_path / ".spanweave" / "daemon" / "state.json").is_file()

    status_after = runner.invoke(
        main,
        ["daemon", "status", "--repo", str(tmp_path), "--json"],
    )
    assert status_after.exit_code == 0
    assert _json_output(status_after.output)["state"] == "running"

    stop = runner.invoke(
        main,
        ["daemon", "stop", "--repo", str(tmp_path), "--json"],
    )
    assert stop.exit_code == 0
    assert _json_output(stop.output)["state"] == "stopped"


def test_run_show_human_output_includes_stage_tree(tmp_path: Path) -> None:
    runner = CliRunner()
    runner.invoke(main, ["run", "--issue", "77", "--repo", str(tmp_path)])

    run_root = tmp_path / ".spanweave" / "runs"
    run_id = next(path.name for path in run_root.iterdir() if path.is_dir())

    result = runner.invoke(
        main,
        ["run", "--repo", str(tmp_path), "show", run_id],
    )

    assert result.exit_code == 0
    assert "Stages" in result.output
    assert "001-specify [running]" in result.output


@pytest.mark.parametrize(
    ("argv", "expected_message"),
    [
        (
            ["run", "--repo", "{repo}", "show", "fake-id"],
            "Invalid run_id 'fake-id'. Expected a value like 'run_<ULID>'.",
        ),
        (
            ["run", "--repo", "{repo}", "show", "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"],
            "was not found under",
        ),
        (
            ["run", "--repo", "{repo}", "resume", "fake-id"],
            "Invalid run_id 'fake-id'. Expected a value like 'run_<ULID>'.",
        ),
        (
            ["run", "--repo", "{repo}", "resume", "run_01ARZ3NDEKTSV4RRFFQ69G5FAV"],
            "was not found under",
        ),
    ],
)
def test_run_show_and_resume_report_click_errors_for_bad_run_ids(
    tmp_path: Path,
    argv: list[str],
    expected_message: str,
) -> None:
    runner = CliRunner()
    resolved_argv = [str(tmp_path) if token == "{repo}" else token for token in argv]

    result = runner.invoke(main, resolved_argv, catch_exceptions=False)

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert expected_message in result.output


@pytest.mark.parametrize(
    ("argv", "expected_message"),
    [
        (
            ["run", "--repo", "{repo}", "show", "{run_id}"],
            "has unreadable metadata. Malformed YAML in",
        ),
        (
            ["run", "--repo", "{repo}", "list"],
            "has unreadable metadata. Malformed YAML in",
        ),
    ],
)
def test_run_show_and_list_report_click_errors_for_malformed_state_yaml(
    tmp_path: Path,
    argv: list[str],
    expected_message: str,
) -> None:
    runner = CliRunner()
    runner.invoke(main, ["run", "--issue", "81", "--repo", str(tmp_path)])

    run_id = next(
        path.name
        for path in (tmp_path / ".spanweave" / "runs").iterdir()
        if path.is_dir()
    )
    state_path = tmp_path / run_dir(run_id) / "workflow_state.yaml"
    state_path.write_text("workflow: [\n", encoding="utf-8")

    resolved_argv = [
        str(tmp_path) if token == "{repo}" else run_id if token == "{run_id}" else token
        for token in argv
    ]

    result = runner.invoke(main, resolved_argv, catch_exceptions=False)

    assert result.exit_code == 1
    assert "Error:" in result.output
    assert expected_message in result.output
    assert str(state_path) in result.output


def test_resume_help_shows_agent_as_optional() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["resume", "--help"])

    assert result.exit_code == 0
    assert "--agent" in result.output
    # Help text may wrap; check normalized content
    normalized = " ".join(result.output.split())
    assert "Auto- detected if omitted" in normalized or "Auto-detected if omitted" in normalized
    # The no-flag example should be the primary pattern
    assert "spanweave resume --run" in result.output


def test_resume_auto_detects_agent_when_flag_omitted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Confirm resume works without --agent when .claude/ exists (Claude Code detection)."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    # Set up a minimal spanweave workspace with a run
    runner.invoke(main, ["init", "--repo", str(tmp_path)])
    run_root = tmp_path / ".spanweave" / "runs"
    run_root.mkdir(parents=True, exist_ok=True)

    # Start a run to get a valid run_id
    start = runner.invoke(
        main,
        ["run", "--issue", "99", "--repo", str(tmp_path), "--json"],
    )
    assert start.exit_code == 0
    started = _json_output(start.output)
    run_id = started["run_id"]

    # Create .claude/ directory to trigger Claude Code adapter detection
    (tmp_path / ".claude").mkdir(exist_ok=True)

    result = runner.invoke(
        main,
        ["resume", "--run", run_id, "--repo", str(tmp_path), "--json"],
    )

    assert result.exit_code == 0
    payload = _json_output(result.output)
    assert payload["agent"] == "claude-code"
    assert payload["run_id"] == run_id
    assert "prompt" in payload


def test_resume_fails_gracefully_when_no_agent_detected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Confirm resume prints a helpful error when auto-detection fails."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    # Set up a minimal workspace but no agent markers
    runner.invoke(main, ["init", "--repo", str(tmp_path)])
    start = runner.invoke(
        main,
        ["run", "--issue", "100", "--repo", str(tmp_path), "--json"],
    )
    started = _json_output(start.output)
    run_id = started["run_id"]

    # Make sure no .claude/ or AGENTS.md exists at repo root
    claude_dir = tmp_path / ".claude"
    agents_file = tmp_path / "AGENTS.md"
    if claude_dir.exists():
        import shutil
        shutil.rmtree(claude_dir)
    if agents_file.exists():
        agents_file.unlink()

    result = runner.invoke(
        main,
        ["resume", "--run", run_id, "--repo", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "Could not auto-detect agent tool" in result.output
    assert "--agent explicitly" in result.output


def test_run_resume_gate_approval_advances_to_next_stage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    runner.invoke(main, ["run", "--issue", "12", "--repo", str(tmp_path)])
    run_id = next(
        path.name
        for path in (tmp_path / ".spanweave" / "runs").iterdir()
        if path.is_dir()
    )

    state_path = tmp_path / run_dir(run_id) / "workflow_state.yaml"
    state_path.write_text(
        "workflow: speckit-loop\n"
        "cursor: 0\n"
        "status: waiting_approval\n"
        "retry_count: 0\n"
        "context: ''\n"
        "prior_feedback: ''\n"
        "waiting_reason: gate\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        main,
        ["run", "--repo", str(tmp_path), "resume", run_id, "--approve", "--json"],
    )

    assert result.exit_code == 0
    payload = _json_output(result.output)
    assert payload["status"] == "running"
    assert payload["current_stage"] == "002-clarify"
    assert payload["stages"][0]["status"] == "completed"
