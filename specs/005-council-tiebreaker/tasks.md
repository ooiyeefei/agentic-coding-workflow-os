# Tasks: Council Tiebreaker

**Input**: Design documents from `/specs/005-council-tiebreaker/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/council.md  
**Tests**: Tests are required for this feature because the acceptance criteria explicitly require majority-vote, tie, capability, concurrency, and persistence checks.  
**Organization**: Tasks are grouped by user story so the council result, capability enforcement, and audit trail stay independently traceable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the focused council test surface and package scaffolding

- [X] T001 Create the focused council verification module in `tests/test_council.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the shared schema and memory plumbing the council depends on

- [X] T002 Create the council schema models in `spanweave/council/schema.py`
- [X] T003 Create the council report memory writer and exports in `spanweave/memory/council.py` and `spanweave/memory/__init__.py`
- [X] T004 Create council package exports in `spanweave/council/__init__.py`

**Checkpoint**: The repository has a stable council schema and a minimal persistence path before voting logic lands.

---

## Phase 3: User Story 1 - Break A Deadlock By Majority Vote (Priority: P1) 🎯 MVP

**Goal**: Return the majority verdict or `HUMAN_REQUIRED` from a three-voter panel

**Independent Test**: Mock three voters, verify 2-1 majority returns the winning verdict, and confirm 1-1-1 returns `HUMAN_REQUIRED`.

### Tests for User Story 1

- [X] T005 [P] [US1] Add majority-for-coder, majority-for-reviewer, and 1-1-1 tie tests in `tests/test_council.py`

### Implementation for User Story 1

- [X] T006 [US1] Implement vote tallying and report assembly in `spanweave/council/tiebreaker.py`

**Checkpoint**: The council produces deterministic outcomes for the core deadlock scenarios.

---

## Phase 4: User Story 2 - Enforce Capability-Gated Voting (Priority: P2)

**Goal**: Resolve all three voters through W02 and reject incompatible models before any provider call

**Independent Test**: Inject manifests so one model lacks required capabilities and confirm the council raises `UnsupportedCapabilityError`; also verify the three successful votes run concurrently.

### Tests for User Story 2

- [X] T007 [P] [US2] Add capability-enforcement and concurrency tests in `tests/test_council.py`

### Implementation for User Story 2

- [X] T008 [US2] Implement model resolution, adapter binding, strict verdict parsing, and concurrent voter dispatch in `spanweave/council/tiebreaker.py`

**Checkpoint**: The council uses W02 honestly and executes the full three-model panel concurrently.

---

## Phase 5: User Story 3 - Persist An Auditable Council Report (Priority: P3)

**Goal**: Write one filesystem-backed `CouncilReport` record with the full vote breakdown

**Independent Test**: Run the council with mocked voters and a temporary memory directory, then confirm a report file is written and contains all three votes plus the final verdict.

### Tests for User Story 3

- [X] T009 [P] [US3] Add council report persistence tests in `tests/test_council.py`

### Implementation for User Story 3

- [X] T010 [US3] Implement council report serialization in `spanweave/memory/council.py` and wire report persistence into `spanweave/council/tiebreaker.py`

**Checkpoint**: Every completed council run leaves an auditable memory artifact behind.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the council slice end-to-end and sync task state

- [X] T011 Run focused pytest coverage for `tests/test_council.py`
- [X] T012 Run lint and type checks for `spanweave/council`, `spanweave/memory`, and `tests/test_council.py`

---

## Dependencies & Execution Order

- Setup must complete before foundational work.
- Foundational work blocks all user stories because voting logic depends on the shared council schema and memory writer.
- User Story 1 must complete before User Story 2 and User Story 3 because majority/tie handling is the core council behavior.
- User Story 2 and User Story 3 can proceed after User Story 1, although both still touch `spanweave/council/tiebreaker.py` and should land sequentially in one branch.
- Polish happens last.

## Parallel Opportunities

- `T005`, `T007`, and `T009` can be written before implementation to preserve a test-first loop.
- `T002` and `T003` can be designed in parallel because schema and persistence responsibilities are separate files.
- Once the shared schema exists, persistence formatting in `spanweave/memory/council.py` can progress in parallel with parts of the voting logic.

## Implementation Strategy

1. Create the council schema and minimal memory writer first.
2. Prove majority and tie handling with focused tests.
3. Add W02-backed model resolution, capability checks, strict verdict validation, and concurrent dispatch.
4. Finish by persisting the council report and validating the generated memory artifact.
5. Run focused pytest, lint, and type checks, then mark completed tasks in this file.
