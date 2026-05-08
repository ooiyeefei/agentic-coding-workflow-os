"""Regression coverage for the integration harness's main-ref guard.

GitHub Actions checks out PR branches as the local HEAD without creating a
local ``main`` ref. ``create_worktree`` hard-codes ``main`` as the base
branch, so without ``ensure_main_ref`` the integration suite fails on every
PR with ``fatal: invalid reference: main`` while passing on main itself.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.integration.conftest import ensure_main_ref


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def _make_repo_on_pr_branch(repo: Path) -> None:
    """Build a repo whose HEAD is a non-main branch with no local main ref."""
    repo.mkdir()
    _git("init", "-b", "feature", cwd=repo)
    _git("config", "user.email", "test@example.invalid", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git("add", "seed.txt", cwd=repo)
    _git("commit", "-m", "seed", cwd=repo)


def test_ensure_main_ref_creates_missing_main_from_head(tmp_path: Path) -> None:
    """On a CI-style PR checkout, the helper creates main pointing at HEAD."""
    repo = tmp_path / "pr_checkout"
    _make_repo_on_pr_branch(repo)

    # Precondition: 'main' ref absent.
    pre = _git("show-ref", "--verify", "--quiet", "refs/heads/main", cwd=repo)
    assert pre.returncode != 0, "test setup did not actually omit 'main'"

    ensure_main_ref(repo)

    # Postcondition: 'main' ref exists.
    post = _git("show-ref", "--verify", "--quiet", "refs/heads/main", cwd=repo)
    assert post.returncode == 0, "ensure_main_ref did not create the missing ref"

    # And ``git worktree add ... main`` no longer fails — directly proves the
    # fix unblocks the integration harness's create_worktree call site.
    worktree = tmp_path / "wt_check"
    add = _git(
        "worktree", "add", "-b", "spanweave/test-run", str(worktree), "main", cwd=repo
    )
    assert add.returncode == 0, f"worktree add still fails: {add.stderr}"


def test_ensure_main_ref_is_noop_when_main_exists(tmp_path: Path) -> None:
    """On a main checkout the helper must not redirect or replace the ref."""
    repo = tmp_path / "main_checkout"
    repo.mkdir()
    _git("init", "-b", "main", cwd=repo)
    _git("config", "user.email", "test@example.invalid", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git("add", "seed.txt", cwd=repo)
    _git("commit", "-m", "seed", cwd=repo)

    before = _git("rev-parse", "main", cwd=repo).stdout.strip()
    ensure_main_ref(repo)
    after = _git("rev-parse", "main", cwd=repo).stdout.strip()

    assert before == after, "ensure_main_ref must not move the existing ref"
