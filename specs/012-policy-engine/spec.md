# Feature Specification: Policy Engine

**Feature Branch**: `012-policy-engine`  
**Created**: 2026-04-20  
**Status**: Draft  
**Input**: User description: "policy engine with approval gates, dry-run defaults, cost caps, all hardcoded for Phase 0"

## Clarifications

### Session 2026-04-20

- Q: How should Phase 0 track spend against policy limits? → A: Aggregate cost per run from W13-style audit JSONL records and compare proposed incremental cost against both the run total and the current day's total.
- Q: How should approval requirements be signaled back to the workflow engine? → A: `requires_approval(...)` returns a boolean gate decision; the orchestrator decides how to pause and request human approval.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Block Destructive Stages Behind Approval (Priority: P1)

As a workflow engine, I can ask the policy layer whether a stage requires human approval, so destructive transitions stay separate from workflow sequencing logic.

**Why this priority**: Approval gates are the highest-risk part of this slice. If destructive stages can proceed without a clear policy decision, the system can auto-rebase or auto-cleanup by mistake.

**Independent Test**: Instantiate the policy engine and assert that destructive stages return `True` while normal stages return `False`.

**Acceptance Scenarios**:

1. **Given** the stage name `rebase-before-pr`, **When** the workflow asks `requires_approval(...)`, **Then** the policy engine returns `True`.
2. **Given** the stage name `cleanup-worktree`, **When** the workflow asks `requires_approval(...)`, **Then** the policy engine returns `True`.
3. **Given** the stage name `implement`, **When** the workflow asks `requires_approval(...)`, **Then** the policy engine returns `False`.

---

### User Story 2 - Default Git Mutations To Dry Run (Priority: P2)

As an orchestrator, I can query whether an operation should run in dry-run mode by default, so Phase 0 stays conservative around git mutations without embedding policy rules in each command handler.

**Why this priority**: Dry-run defaults reduce blast radius for destructive git operations and are part of the product's "steering without locking" posture.

**Independent Test**: Ask the policy engine about mutating and read-only git operations and verify mutating operations default to dry-run while read-only operations do not.

**Acceptance Scenarios**:

1. **Given** the operation `git-rebase`, **When** the workflow asks `is_dry_run(...)`, **Then** the policy engine returns `True`.
2. **Given** the operation `git-push`, **When** the workflow asks `is_dry_run(...)`, **Then** the policy engine returns `True`.
3. **Given** the operation `git-status`, **When** the workflow asks `is_dry_run(...)`, **Then** the policy engine returns `False`.

---

### User Story 3 - Enforce Run And Daily Cost Caps (Priority: P3)

As an orchestrator, I can check whether a proposed incremental LLM cost fits inside Phase 0 spend limits, so a run stops before exceeding allowed budget.

**Why this priority**: Cost governance is the Phase 0 policy primitive that prevents a bad loop from burning unbounded spend.

**Independent Test**: Create run-scoped and day-scoped audit logs, then verify `check_cost(...)` accepts totals below or equal to the cap and raises once the projected total exceeds it.

**Acceptance Scenarios**:

1. **Given** a run with $4.99 already accrued, **When** `check_cost(run_id, 0.01)` is called, **Then** it returns `True` because the projected total equals the $5.00 cap.
2. **Given** a run with $5.00 already accrued, **When** `check_cost(run_id, 0.01)` is called, **Then** it raises `CostCapExceeded` because the projected total exceeds the run cap.
3. **Given** the current day has $49.99 accrued across all runs, **When** `check_cost(run_id, 0.02)` is called, **Then** it raises `CostCapExceeded` because the projected daily total exceeds the $50.00 cap.

### Edge Cases

- What happens when a run has no audit log yet? The engine should treat current spend as zero.
- What happens when the daily aggregate log for the current date does not exist yet? The engine should treat daily spend as zero.
- How does the tracker handle audit entries without any cost payload? They should be ignored rather than counted as zero-value policy events.
- How does the tracker handle malformed JSON lines in an audit log? It should fail loudly instead of silently undercounting spend.
- How does the dry-run policy handle unknown git operations? Phase 0 should default unknown `git-*` operations to dry-run unless they are explicitly known to be read-only.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide `spanweave/policy/engine.py` with a `PolicyEngine` class exposing `requires_approval(stage, context)`, `is_dry_run(operation)`, and `check_cost(run_id, proposed_cost)`.
- **FR-002**: `requires_approval(stage, context)` MUST return `True` for `rebase-before-pr` and `cleanup-worktree`.
- **FR-003**: `requires_approval(stage, context)` MUST return `False` for non-gated stages such as `implement`.
- **FR-004**: `is_dry_run(operation)` MUST return `True` by default for mutating `git-*` operations in Phase 0.
- **FR-005**: `is_dry_run(operation)` MUST return `False` for explicitly read-only git operations and for non-git operations that do not have a dry-run default.
- **FR-006**: The system MUST define Phase 0 hardcoded defaults in `spanweave/policy/defaults.py`, including approval-gated stages, dry-run behavior, and spend caps of $5.00 per run and $50.00 per day.
- **FR-007**: The system MUST provide `spanweave/policy/cost_tracker.py` that reads append-only JSONL audit logs from the filesystem and sums current cost for a run and for a day without requiring any database.
- **FR-008**: The cost tracker MUST read per-run logs from `.spanweave/runs/<run_id>/audit.jsonl` and daily logs from `.spanweave/audit/YYYY-MM-DD.jsonl`.
- **FR-009**: The cost tracker MUST accept W13-style audit entries where cost appears either as a direct numeric field or as a nested normalized cost object containing `total_usd`.
- **FR-010**: `check_cost(run_id, proposed_cost)` MUST compare the proposed incremental cost against both the projected run total and the projected current-day total.
- **FR-011**: `check_cost(run_id, proposed_cost)` MUST return `True` when the projected totals are less than or equal to the configured caps.
- **FR-012**: `check_cost(run_id, proposed_cost)` MUST raise `CostCapExceeded` when either projected total exceeds the configured run or daily cap.
- **FR-013**: `tests/test_policy.py` MUST cover approval gates, dry-run defaults, run-cap boundaries at $4.99, $5.00, and $5.01, and a daily-cap failure path.

### Key Entities *(include if feature involves data)*

- **PolicyDefaults**: The hardcoded Phase 0 set of approval-gated stages, dry-run decisions, and monetary caps.
- **PolicyDecisionContext**: Optional workflow metadata supplied to `requires_approval(...)`; retained for future expansion but ignored by hardcoded Phase 0 gate rules.
- **AuditCostRecord**: A single JSONL audit entry that may contribute cost through a top-level numeric field or a nested normalized cost object.
- **CostSnapshot**: The current run total, current-day total, proposed incremental cost, and projected totals used to decide whether a cap is exceeded.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `tests/test_policy.py` passes locally.
- **SC-002**: `requires_approval("rebase-before-pr", ctx)` returns `True` and `requires_approval("implement", ctx)` returns `False`.
- **SC-003**: `is_dry_run("git-rebase")` returns `True` and `is_dry_run("git-status")` returns `False`.
- **SC-004**: A projected run total of $5.00 passes policy, while a projected run total of $5.01 raises `CostCapExceeded`.
- **SC-005**: A projected daily total above $50.00 raises `CostCapExceeded`.

## Assumptions

- W13 will write append-only JSONL audit events to both per-run and daily log locations, and those files remain the source of truth for Phase 0 cost aggregation.
- The workflow engine will interpret `requires_approval(...) == True` as "pause and request human approval" rather than expecting an exception-based control flow.
- Cost caps apply to normalized USD totals, using `total_usd` when available and summing line items only when a direct total is absent.
- Phase 0 keeps all policy values hardcoded in Python; config-driven overrides are intentionally deferred.
