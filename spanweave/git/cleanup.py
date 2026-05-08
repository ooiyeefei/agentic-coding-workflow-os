from __future__ import annotations

from pathlib import Path

from spanweave.util.ulid import EntityPrefix, validate_prefixed_id

from .errors import ConfirmationRequiredError
from .worktree import list_worktrees, remove_worktree, worktree_dirname


def cleanup_run_worktrees(
    run_id: str,
    *,
    confirm: bool = False,
    repo_root: Path | None = None,
) -> list[Path]:
    """Remove all worktrees associated with a run.  Requires confirmation."""
    if not confirm:
        raise ConfirmationRequiredError("cleanup_run_worktrees")

    validate_prefixed_id(run_id, EntityPrefix.RUN)

    target_name = worktree_dirname(run_id)
    all_worktrees = list_worktrees(repo_root=repo_root)

    removed: list[Path] = []
    for wt_path in all_worktrees:
        if wt_path.name == target_name:
            remove_worktree(wt_path, confirm=True)
            removed.append(wt_path)

    return removed


__all__ = ["cleanup_run_worktrees"]
