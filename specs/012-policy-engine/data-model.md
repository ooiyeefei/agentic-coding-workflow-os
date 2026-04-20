# Data Model: Policy Engine

## PolicyDefaults

- **Purpose**: Represents the hardcoded Phase 0 policy rules.
- **Fields**:
  - `approval_required_stages`: Set of stage names that require human approval
  - `read_only_git_operations`: Set of git operations that never need dry-run protection
  - `run_cost_cap_usd`: Inclusive run-level cap
  - `daily_cost_cap_usd`: Inclusive day-level cap
- **Validation rules**:
  - Caps must be non-negative USD amounts.
  - Approval stages are compared case-sensitively against canonical workflow stage names.

## AuditCostRecord

- **Purpose**: Represents one parsed JSONL audit event that may contribute spend.
- **Fields**:
  - `run_id`: Run identifier when present
  - `event_type`: Audit event type such as `LLM_CALL` or `COST_ACCRUED`
  - `timestamp`: Event timestamp when present
  - `cost_total_usd`: Extracted numeric total cost for that event when present
- **Validation rules**:
  - Records without an extractable cost do not affect policy totals.
  - Malformed JSON is invalid and stops aggregation.

## CostSnapshot

- **Purpose**: Captures the budget state used for one policy decision.
- **Fields**:
  - `run_id`: The run being evaluated
  - `current_run_total_usd`: Current aggregated spend for that run
  - `current_day_total_usd`: Current aggregated spend for the current day
  - `proposed_cost_usd`: Incremental cost being evaluated
  - `projected_run_total_usd`: Run total after the proposed cost
  - `projected_day_total_usd`: Day total after the proposed cost
- **Validation rules**:
  - Projected totals equal current totals plus proposed cost.
  - All monetary values are non-negative.

## CostCapExceeded

- **Purpose**: Represents a failed policy decision caused by a run or daily cap breach.
- **Fields**:
  - `scope`: Either `run` or `day`
  - `cap_usd`: The configured cap for that scope
  - `current_total_usd`: The total already accrued before the proposed cost
  - `proposed_cost_usd`: The incremental cost that triggered the breach
  - `projected_total_usd`: The projected total that exceeds the cap
- **Validation rules**:
  - `projected_total_usd` must be greater than `cap_usd`.
  - `scope` must identify the first violated cap that was detected.
