from __future__ import annotations


class WorktreeError(Exception):
    """Base error for git worktree operations."""


class ConfirmationRequiredError(WorktreeError):
    """Raised when a destructive operation is called without explicit confirmation."""

    def __init__(self, operation: str) -> None:
        super().__init__(f"confirmation required for destructive operation: {operation}")
        self.operation = operation


class RebaseAnalysisError(Exception):
    """Raised when rebase analysis encounters an unexpected git error."""


__all__ = ["ConfirmationRequiredError", "RebaseAnalysisError", "WorktreeError"]
