from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from atelier.cli.main import main
from atelier.git.worktree import create_worktree
from atelier.rungraph import create_run
from atelier.util.paths import run_dir
from click.testing import CliRunner


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
    _git("config", "user.email", "test@atelier.test", cwd=repo)
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
    assert "Atelier control plane" in result.output
    assert "init" in result.output
    assert "run" in result.output
    assert "cleanup" in result.output
    assert "daemon" in result.output
    assert "grep" in result.output
    assert "Examples:" in result.output
    assert "Examples:\n\n    atelier init --repo ." in result.output


@pytest.mark.parametrize(
    ("argv", "needles"),
    [
            (
                ["run", "--help"],
                [
                    "Examples:",
                    "Invoke 'atelier run' directly to start a new workflow run.",
                    "Examples:\n\n    atelier run --issue 42 --repo .",
                ],
            ),
            (
                ["run", "list", "--help"],
                [
                    "Examples:",
                    "Results are ordered newest-first",
                    "Examples:\n\n    atelier run list --repo .",
                ],
            ),
            (
                ["run", "show", "--help"],
                [
                    "Examples:",
                    "stored run metadata and stage tree",
                    "Examples:\n\n    atelier run show run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo .",
                ],
            ),
            (
                ["run", "resume", "--help"],
                [
                    "Examples:",
                    "Without --approve this command only reports the current blocked state.",
                    "atelier run resume run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo . "
                    "--approve",
                ],
            ),
            (
                ["daemon", "start", "--help"],
                [
                    "Examples:",
                    "does not launch a background HTTP process yet",
                    "Examples:\n\n    atelier daemon start --repo .",
                ],
            ),
            (
                ["daemon", "stop", "--help"],
                [
                    "Examples:",
                    "does not signal a real daemon yet",
                    "Examples:\n\n    atelier daemon stop --repo .",
                ],
            ),
            (
                ["daemon", "status", "--help"],
                [
                    "Examples:",
                    "Status is read from .atelier/daemon/state.json",
                    "Examples:\n\n    atelier daemon status --repo .",
                ],
            ),
            (
                ["cleanup", "--help"],
                [
                    "Examples:",
                    "Cleanup prompts before removing worktrees unless you pass --yes.",
                    "Examples:\n\n    atelier cleanup run_01ARZ3NDEKTSV4RRFFQ69G5FAV --repo .",
                ],
            ),
            (
                ["init", "--help"],
                [
                    "Examples:",
                    "idempotent and does not overwrite existing workspace files",
                    "Examples:\n\n    atelier init --repo .",
                ],
            ),
            (
                ["grep", "--help"],
                [
                    "Examples:",
                    "pattern is treated as a Python regular expression",
                    "Examples:\n\n    atelier grep 'issue #42' --repo .",
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


def test_init_scaffolds_atelier_workspace(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["init", "--repo", str(tmp_path), "--json"])

    assert result.exit_code == 0
    payload = _json_output(result.output)
    assert payload["changed"] is True
    assert (tmp_path / ".atelier" / "workflows" / "speckit-loop.yaml").is_file()
    assert (tmp_path / ".atelier" / "memory" / "decisions").is_dir()
    assert (tmp_path / ".atelier" / "daemon").is_dir()


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
    assert (tmp_path / ".atelier" / "daemon" / "state.json").is_file()

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

    run_root = tmp_path / ".atelier" / "runs"
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

    run_id = next(path.name for path in (tmp_path / ".atelier" / "runs").iterdir() if path.is_dir())
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


def test_run_resume_gate_approval_advances_to_next_stage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    runner.invoke(main, ["run", "--issue", "12", "--repo", str(tmp_path)])
    run_id = next(path.name for path in (tmp_path / ".atelier" / "runs").iterdir() if path.is_dir())

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
