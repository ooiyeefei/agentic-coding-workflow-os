# Tasks: Policy Engine

**Input**: Design documents from `/specs/012-policy-engine/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/policy.md  
**Tests**: Tests are required for this feature because the acceptance criteria explicitly require approval-gate, dry-run, and cost-cap boundary coverage.  
**Organization**: Tasks are grouped by user story so approval gates, dry-run defaults, and cost caps remain independently traceable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the feature-local documentation and focused verification surface

- [X] T001 Create the policy feature documentation set in `specs/012-policy-engine/`
- [X] T002 Create the focused policy verification module in `tests/test_policy.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish hardcoded defaults and package exports shared by all policy behavior

- [X] T003 Create hardcoded Phase 0 policy defaults in `atelier/policy/defaults.py`
- [X] T004 Update `atelier/policy/__init__.py` to export the policy engine and related exceptions

**Checkpoint**: Shared defaults and package exports are available for all policy stories.

---

## Phase 3: User Story 1 - Block Destructive Stages Behind Approval (Priority: P1) 🎯 MVP

**Goal**: Provide approval-gate decisions for destructive workflow stages

**Independent Test**: Instantiate the policy engine and verify approval-required and non-gated stages return the expected boolean values.

### Tests for User Story 1

- [X] T005 [P] [US1] Add approval-gate assertions in `tests/test_policy.py`

### Implementation for User Story 1

- [X] T006 [US1] Implement approval-gate behavior in `atelier/policy/engine.py`

**Checkpoint**: The workflow layer can query which stages require human approval.

---

## Phase 4: User Story 2 - Default Git Mutations To Dry Run (Priority: P2)

**Goal**: Provide conservative dry-run defaults for git operations

**Independent Test**: Query mutating and read-only git operations and verify dry-run decisions match the Phase 0 policy.

### Tests for User Story 2

- [X] T007 [P] [US2] Add dry-run default assertions in `tests/test_policy.py`

### Implementation for User Story 2

- [X] T008 [US2] Implement dry-run decision logic in `atelier/policy/engine.py`

**Checkpoint**: Mutating git operations default to dry-run without contaminating workflow code.

---

## Phase 5: User Story 3 - Enforce Run And Daily Cost Caps (Priority: P3)

**Goal**: Prevent run and daily spend from exceeding Phase 0 limits

**Independent Test**: Populate temporary audit logs and verify run-cap boundary behavior plus a daily-cap failure path.

### Tests for User Story 3

- [X] T009 [P] [US3] Add cost-cap boundary and daily-cap tests in `tests/test_policy.py`

### Implementation for User Story 3

- [X] T010 [P] [US3] Implement JSONL cost aggregation in `atelier/policy/cost_tracker.py`
- [X] T011 [US3] Implement cost-cap enforcement and `CostCapExceeded` in `atelier/policy/engine.py`

**Checkpoint**: Projected run and day totals are checked before new spend is approved.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the slice and sync task state

- [X] T012 Run focused pytest coverage for `tests/test_policy.py`
- [X] T013 Run lint checks for `atelier/policy/` and `tests/test_policy.py`

---

## Dependencies & Execution Order

- Setup must complete before foundational work.
- Foundational work blocks all user stories because the shared defaults and exports are used throughout the policy module.
- User Story 1 must land before User Story 2 and User Story 3 because approval-gate decisions define the main `PolicyEngine` surface.
- User Story 2 and User Story 3 can proceed after User Story 1, though both still share `atelier/policy/engine.py` and should land sequentially in one branch.
- Polish happens last.

## Parallel Opportunities

- `T005`, `T007`, and `T009` can be written before implementation to preserve a test-first loop.
- `T010` can proceed in parallel with parts of `T011` once the cost snapshot contract is fixed.
- Documentation work in `T001` and the focused test scaffold in `T002` are independent.

## Implementation Strategy

1. Establish hardcoded defaults and package exports.
2. Prove approval gates first because they are the MVP behavior.
3. Add dry-run defaults for git mutations.
4. Finish with the JSONL-backed cost tracker and cap enforcement.
5. Validate with focused pytest and lint, then mark completed tasks in this file.
