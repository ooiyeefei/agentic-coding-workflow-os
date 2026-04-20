# Contract: atelier.policy Public API

## PolicyEngine

- `PolicyEngine(...).requires_approval(stage, context) -> bool`
- `PolicyEngine(...).is_dry_run(operation) -> bool`
- `PolicyEngine(...).check_cost(run_id, proposed_cost) -> bool`

**Contract**:

- `requires_approval(...)` returns `True` for `rebase-before-pr` and `cleanup-worktree`.
- `requires_approval(...)` returns `False` for non-gated stages and does not raise approval exceptions in Phase 0.
- `is_dry_run(...)` returns `True` for mutating `git-*` operations by default.
- `is_dry_run(...)` returns `False` for known read-only git operations.
- `check_cost(...)` reads current spend from filesystem audit logs before approving the proposed incremental cost.
- `check_cost(...)` returns `True` when projected run and daily totals are less than or equal to their caps.
- `check_cost(...)` raises `CostCapExceeded` when either projected total exceeds its cap.

## CostTracker

- `CostTracker(...).sum_run_cost(run_id) -> Decimal`
- `CostTracker(...).sum_day_cost(day) -> Decimal`

**Contract**:

- Run totals are read from `.atelier/runs/<run_id>/audit.jsonl`.
- Day totals are read from `.atelier/audit/YYYY-MM-DD.jsonl`.
- Cost extraction accepts either direct numeric fields or nested normalized cost objects with `total_usd`.
- Missing audit files are treated as zero totals.
- Malformed JSON lines raise an error rather than being skipped.
