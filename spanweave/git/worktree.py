from __future__ import annotations

import subprocess
from pathlib import Path

from spanweave.util.ulid import EntityPrefix, validate_prefixed_id

from .errors import ConfirmationRequiredError, WorktreeError

_WORKTREES_DIR = "worktrees"


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def _main_repo_root(from_path: Path) -> Path:
    """Find the main repository root from any path inside a worktree."""
    top = _git("rev-parse", "--show-toplevel", cwd=from_path)
    if top.returncode != 0:
        raise WorktreeError(f"not inside a git repository: {from_path}")
    worktree_root = Path(top.stdout.strip())

    common = _git("rev-parse", "--git-common-dir", cwd=worktree_root)
    if common.returncode != 0:
        raise WorktreeError(f"not inside a git repository: {from_path}")

    git_common = Path(common.stdout.strip())
    if not git_common.is_absolute():
        git_common = (worktree_root / git_common).resolve()
    return git_common.parent


def worktree_dirname(run_id: str) -> str:
    return run_id


def create_worktree(
    run_id: str,
    base_branch: str = "main",
    *,
    repo_root: Path | None = None,
    worktree_base: Path | None = None,
) -> Path:
    """Create a new git worktree and branch for a run."""
    validate_prefixed_id(run_id, EntityPrefix.RUN)

    root = repo_root or _main_repo_root(Path.cwd())
    parent = worktree_base if worktree_base is not None else root.parent / _WORKTREES_DIR
    parent.mkdir(parents=True, exist_ok=True)

    worktree_path = parent / worktree_dirname(run_id)
    branch_name = f"spanweave/{run_id}"

    result = _git(
        "worktree", "add", "-b", branch_name,
        str(worktree_path), base_branch,
        cwd=root,
    )
    if result.returncode != 0:
        raise WorktreeError(f"failed to create worktree: {result.stderr.strip()}")

    return worktree_path


def remove_worktree(worktree_path: Path, *, confirm: bool = False) -> None:
    """Remove a git worktree.  Requires explicit confirmation."""
    if not confirm:
        raise ConfirmationRequiredError("remove_worktree")

    resolved = Path(worktree_path).resolve()
    if not resolved.exists():
        raise WorktreeError(f"worktree path does not exist: {resolved}")

    main_root = _main_repo_root(resolved)
    result = _git("worktree", "remove", str(resolved), cwd=main_root)
    if result.returncode != 0:
        raise WorktreeError(f"failed to remove worktree: {result.stderr.strip()}")


def list_worktrees(*, repo_root: Path | None = None) -> list[Path]:
    """List all worktree paths for the repository."""
    root = repo_root or _main_repo_root(Path.cwd())
    result = _git("worktree", "list", "--porcelain", cwd=root)
    if result.returncode != 0:
        raise WorktreeError(f"failed to list worktrees: {result.stderr.strip()}")

    paths: list[Path] = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line.removeprefix("worktree ")))
    return paths


__all__ = ["create_worktree", "list_worktrees", "remove_worktree", "worktree_dirname"]
