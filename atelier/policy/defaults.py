from __future__ import annotations

from decimal import Decimal

APPROVAL_REQUIRED_STAGES = frozenset(
    {
        "cleanup-worktree",
        "rebase-before-pr",
    }
)

READ_ONLY_GIT_OPERATIONS = frozenset(
    {
        "git-diff",
        "git-fetch",
        "git-log",
        "git-show",
        "git-status",
    }
)

RUN_COST_CAP_USD = Decimal("5.00")
DAILY_COST_CAP_USD = Decimal("50.00")


def requires_approval(stage: str) -> bool:
    return stage.strip().casefold() in APPROVAL_REQUIRED_STAGES


def is_dry_run(operation: str) -> bool:
    normalized = operation.strip().casefold()
    if normalized in READ_ONLY_GIT_OPERATIONS:
        return False
    return normalized.startswith("git-")


__all__ = [
    "APPROVAL_REQUIRED_STAGES",
    "DAILY_COST_CAP_USD",
    "READ_ONLY_GIT_OPERATIONS",
    "RUN_COST_CAP_USD",
    "is_dry_run",
    "requires_approval",
]
