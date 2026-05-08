# Tasks: ULID Path Helpers

**Input**: Design documents from `/specs/002-ulid-path-helpers/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/util-api.md

**Tests**: Tests are required for this feature because the acceptance criteria require complete verification of the utility surface and 100% coverage.

**Organization**: Tasks are grouped by user story so ID generation, path construction, and atomic replacement semantics remain independently testable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the utility surface and targeted verification files

- [x] T001 Update the public utility export surface in spanweave/util/__init__.py
- [x] T002 Create targeted test modules in tests/test_ulid.py, tests/test_paths.py, and tests/test_fs.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared validation and naming behavior used by later tasks

- [x] T003 Create prefixed ULID parsing and validation helpers in spanweave/util/ulid.py
- [x] T004 Create shared run graph path validation and stage slug normalization in spanweave/util/paths.py

**Checkpoint**: Shared validation primitives are in place for the remaining stories.

---

## Phase 3: User Story 1 - Generate Sortable Run Graph IDs (Priority: P1) 🎯 MVP

**Goal**: Provide stable prefixed IDs for every supported run graph entity

**Independent Test**: Generate IDs for each entity type, verify prefixes and ULID validity, and prove lexicographic ordering across sequential run IDs.

### Tests for User Story 1

- [x] T005 [P] [US1] Add prefixed ID generation and ordering tests in tests/test_ulid.py

### Implementation for User Story 1

- [x] T006 [US1] Implement public prefixed ID generator functions in spanweave/util/ulid.py

**Checkpoint**: All run graph entity IDs can be generated and validated.

---

## Phase 4: User Story 2 - Build Canonical Run Graph Paths (Priority: P2)

**Goal**: Provide validated `Path` constructors for the canonical `.spanweave` tree

**Independent Test**: Build run, stage, packet, evidence, transcript, and audit log paths from valid inputs and confirm invalid values fail fast.

### Tests for User Story 2

- [x] T007 [P] [US2] Add canonical path and validation tests in tests/test_paths.py

### Implementation for User Story 2

- [x] T008 [US2] Implement canonical run and stage path constructors in spanweave/util/paths.py
- [x] T009 [US2] Implement artifact-specific path helpers in spanweave/util/paths.py

**Checkpoint**: Canonical run graph locations are deterministic and validated.

---

## Phase 5: User Story 3 - Persist Files Without Partial Overwrites (Priority: P3)

**Goal**: Create idempotent directory creation and atomic file replacement

**Independent Test**: Call `safe_mkdir` repeatedly, replace file content with `atomic_write`, and simulate replacement failure to confirm the destination stays unchanged.

### Tests for User Story 3

- [x] T010 [P] [US3] Add directory creation and atomic write failure-mode tests in tests/test_fs.py

### Implementation for User Story 3

- [x] T011 [US3] Implement safe directory creation in spanweave/util/fs.py
- [x] T012 [US3] Implement same-directory atomic file replacement in spanweave/util/fs.py

**Checkpoint**: Filesystem helpers preserve destination integrity across success and failure cases.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification and cleanup across the shared utility surface

- [x] T013 Run the targeted utility verification suite for spanweave/util in tests/test_ulid.py, tests/test_paths.py, and tests/test_fs.py
- [x] T014 Confirm 100% coverage, lint, and type-check results for spanweave/util

---

## Dependencies & Execution Order

- Phase 1 must finish before foundational work.
- Phase 2 blocks all user story implementation because it defines the shared validation behavior.
- User Story 1 should land before User Story 2 so path validators can reuse ID parsing logic.
- User Story 2 should land before User Story 3 only insofar as shared naming conventions must be stable.
- Polish runs after all story phases are complete.

## Parallel Opportunities

- `T005`, `T007`, and `T010` can be written before their implementation tasks to preserve a test-first loop.
- `T008` and `T009` can be split conceptually once shared validation exists, though they touch the same file and should merge sequentially.
- The three test modules are independent and can evolve without file conflicts.

## Implementation Strategy

1. Establish the shared validation surface and the test skeletons first.
2. Implement prefixed ULID helpers and prove ordering behavior.
3. Layer path construction on top of validated IDs and stage naming rules.
4. Finish with filesystem safety helpers and explicit failure-mode coverage.
5. Run the full targeted verification suite and lock in 100% coverage.
