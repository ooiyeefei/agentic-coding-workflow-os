# Quickstart: Policy Engine

## Verify the feature

1. Run `uv run pytest tests/test_policy.py -v`.
2. Run `uv run ruff check spanweave/policy tests/test_policy.py`.

## Manual spot checks

1. Instantiate `PolicyEngine()` and confirm `requires_approval("rebase-before-pr", {})` returns `True`.
2. Confirm `PolicyEngine().requires_approval("implement", {})` returns `False`.
3. Confirm `PolicyEngine().is_dry_run("git-rebase")` returns `True` and `PolicyEngine().is_dry_run("git-status")` returns `False`.
4. Create a temporary `.spanweave/runs/<run_id>/audit.jsonl` containing a cost total of `4.99`, then confirm `check_cost(run_id, 0.01)` returns `True`.
5. Update the same run log to a total of `5.00`, then confirm `check_cost(run_id, 0.01)` raises `CostCapExceeded`.
