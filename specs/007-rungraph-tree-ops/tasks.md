# Tasks: Run Graph Tree Ops

**Input**: Design documents from `/specs/007-rungraph-tree-ops/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: This feature requires pytest coverage for run creation, stage ordering, completion markers, resume selection, dual-lock blocking, and post-crash lock reacquisition.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the public surface and test target for the new run graph slice.

- [x] T001 Create the run graph feature task scaffold in `specs/007-rungraph-tree-ops/tasks.md`
- [x] T002 Prepare public rungraph exports in `spanweave/rungraph/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish common helpers and invariants used by all user stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Create shared rungraph path and metadata helpers in `spanweave/rungraph/tree.py`
- [x] T004 Create completion-scan helper in `spanweave/rungraph/cursor.py`
- [x] T005 Create blocking per-run lock context manager in `spanweave/rungraph/lock.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Create Canonical Run Trees (Priority: P1) 🎯 MVP

**Goal**: Create canonical `.spanweave/runs/<run_id>/` trees and ordered stage directories.

**Independent Test**: Create one run and three stages, then inspect the real filesystem tree for canonical files and ordered stage IDs.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T006 [P] [US1] Add run and stage creation layout tests in `tests/test_rungraph.py`

### Implementation for User Story 1

- [x] T007 [US1] Implement `create_run()` and `list_runs()` in `spanweave/rungraph/tree.py`
- [x] T008 [US1] Implement `create_stage()` and `list_stages()` in `spanweave/rungraph/tree.py`
- [x] T009 [US1] Export rungraph tree helpers from `spanweave/rungraph/__init__.py`

**Checkpoint**: User Story 1 should create canonical run and stage trees and be testable independently

---

## Phase 4: User Story 2 - Resume From The First Incomplete Stage (Priority: P2)

**Goal**: Record stage completion and resume deterministically from the first incomplete stage.

**Independent Test**: Mark only the first two of three stages complete and verify the cursor returns the third stage; leave another stage partial without a completion marker and verify it is still chosen.

### Tests for User Story 2 ⚠️

- [x] T010 [P] [US2] Add completion marker and resume cursor tests in `tests/test_rungraph.py`

### Implementation for User Story 2

- [x] T011 [US2] Implement `mark_stage_complete()` in `spanweave/rungraph/tree.py`
- [x] T012 [US2] Implement `next_stage_to_execute()` in `spanweave/rungraph/cursor.py`
- [x] T013 [US2] Export the resume cursor from `spanweave/rungraph/__init__.py`

**Checkpoint**: User Stories 1 and 2 should now support ordered creation plus idempotent resume

---

## Phase 5: User Story 3 - Serialize Writers With Reclaimable Locks (Priority: P3)

**Goal**: Prevent concurrent writes to a run and recover cleanly after a holder exits.

**Independent Test**: Hold a lock in one subprocess, confirm a second subprocess blocks, then confirm a later subprocess can reacquire the same lock after the first exits.

### Tests for User Story 3 ⚠️

- [x] T014 [P] [US3] Add subprocess-based lock contention and crash-recovery tests in `tests/test_rungraph.py`

### Implementation for User Story 3

- [x] T015 [US3] Implement `run_lock()` with blocking exclusive file locking in `spanweave/rungraph/lock.py`
- [x] T016 [US3] Ensure run creation provisions `.lock` and export the lock helper from `spanweave/rungraph/__init__.py`

**Checkpoint**: All user stories should now be independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across the new run graph slice.

- [x] T017 Run `uv run pytest tests/test_rungraph.py -v`
- [x] T018 Run `uv run ruff check spanweave/rungraph tests/test_rungraph.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: Depend on Foundational completion
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Starts after Foundational and provides the base filesystem tree
- **User Story 2 (P2)**: Depends on User Story 1's stage creation behavior
- **User Story 3 (P3)**: Depends on User Story 1's run directory creation and lock file location

### Within Each User Story

- Tests MUST be written and fail before implementation
- Tree creation before resume scanning
- Run creation before lock acquisition tests

### Parallel Opportunities

- `T006`, `T010`, and `T014` all extend `tests/test_rungraph.py`, so they should run sequentially despite being test tasks
- Foundational module stubs in `tree.py`, `cursor.py`, and `lock.py` can be developed with minimal overlap once interfaces are fixed
- Polish verification commands can run after implementation is complete

---

## Parallel Example: User Story 1

```bash
Task: "Implement create_run() and list_runs() in spanweave/rungraph/tree.py"
Task: "Implement create_stage() and list_stages() in spanweave/rungraph/tree.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup
2. Complete Foundational
3. Complete User Story 1
4. Validate canonical run and stage layout

### Incremental Delivery

1. Add canonical run and stage creation
2. Add completion markers and resume scanning
3. Add blocking lock behavior and crash recovery
4. Run the focused validation commands

### Parallel Team Strategy

1. Align on the shared tree and lock contracts first
2. Split tree, cursor, and lock work once the interfaces are stable
3. Reunify in `tests/test_rungraph.py` for end-to-end verification

---

## Notes

- The `.spanweave` storage tree is the source of truth for correctness
- Stage IDs are directory names of the form `<nnn>-<slug>`
- Incomplete stages are defined solely by the absence of `.complete`
- Lock tests must assert real blocking behavior across processes, not mocked calls
