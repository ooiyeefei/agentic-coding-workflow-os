# Tasks: Context Compiler

**Input**: Design documents from `/specs/006-context-compiler/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/compiler.md  
**Tests**: Tests are required for this feature because the acceptance criteria explicitly require deterministic compilation, budget trimming, deduplication, and the impossible-budget error path.  
**Organization**: Tasks are grouped by user story so packet assembly, budget enforcement, and provenance remain independently testable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the focused compiler package surface and dedicated tests

- [X] T001 Create the compiler package exports in `atelier/compiler/__init__.py`
- [X] T002 Create the focused compiler verification module in `tests/test_compiler.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define the shared source, provenance, and budget contracts used by all stories

- [X] T003 Implement typed source models in `atelier/compiler/sources.py`
- [X] T004 [P] Implement provenance models and footer helpers in `atelier/compiler/provenance.py`
- [X] T005 [P] Implement token estimation and `BudgetExceededError` in `atelier/compiler/budget.py`

**Checkpoint**: Source typing, provenance structures, and budget helpers exist for the compiler core to build on.

---

## Phase 3: User Story 1 - Compile A Priority-Aware Packet (Priority: P1) 🎯 MVP

**Goal**: Compile deterministic packets from an objective plus prioritized sources

**Independent Test**: Run the compiler with stable fixtures under a roomy budget and confirm the packet body and provenance stay byte-for-byte identical across repeated runs.

### Tests for User Story 1

- [X] T006 [P] [US1] Add deterministic within-budget compilation tests in `tests/test_compiler.py`

### Implementation for User Story 1

- [X] T007 [US1] Implement objective normalization and deterministic source ordering in `atelier/compiler/compiler.py`
- [X] T008 [US1] Implement packet block rendering and packet assembly in `atelier/compiler/compiler.py`

**Checkpoint**: The compiler can build a stable packet when all content fits.

---

## Phase 4: User Story 2 - Enforce Budget By Dropping Lower Tiers First (Priority: P2)

**Goal**: Respect token budgets by trimming predictable lower-priority content

**Independent Test**: Re-run the same fixtures under tighter budgets and confirm nice-tier blocks drop before should-tier blocks and must-only overflow raises.

### Tests for User Story 2

- [X] T009 [P] [US2] Add tight-budget and impossible-budget tests in `tests/test_compiler.py`

### Implementation for User Story 2

- [X] T010 [US2] Implement budget-aware trimming across nice and should tiers in `atelier/compiler/compiler.py`
- [X] T011 [US2] Integrate must-tier overflow checks in `atelier/compiler/compiler.py` and `atelier/compiler/budget.py`

**Checkpoint**: Lower tiers are trimmed deterministically and must-tier overflow fails fast.

---

## Phase 5: User Story 3 - Preserve Provenance And Deduplicate Sources (Priority: P3)

**Goal**: Remove duplicated blocks and expose packet provenance clearly

**Independent Test**: Compile fixtures with duplicate `source_id` values and confirm only the first occurrence is kept while the footer and sidecar list included sources exactly once.

### Tests for User Story 3

- [X] T012 [P] [US3] Add duplicate-source and provenance footer assertions in `tests/test_compiler.py`

### Implementation for User Story 3

- [X] T013 [US3] Implement exact `source_id` deduplication in `atelier/compiler/compiler.py`
- [X] T014 [US3] Implement provenance sidecar generation and footer rendering in `atelier/compiler/compiler.py` and `atelier/compiler/provenance.py`

**Checkpoint**: Packet output is deduplicated and auditable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the slice end-to-end and sync task state

- [X] T015 Run focused pytest coverage for `tests/test_compiler.py`
- [X] T016 Run lint checks for `atelier/compiler` and `tests/test_compiler.py`

---

## Dependencies & Execution Order

- Setup must complete before foundational work.
- Foundational work blocks all user stories because compiler assembly depends on source typing, provenance structures, and budget helpers.
- User Story 1 must complete before User Story 2 and User Story 3 because stable packet assembly is the base behavior.
- User Story 2 and User Story 3 can proceed after User Story 1, though both update the same compiler core and should land sequentially in one branch.
- Polish happens last.

## Parallel Opportunities

- `T004` and `T005` can proceed in parallel once the source model shape from `T003` is fixed.
- `T006`, `T009`, and `T012` can be written before implementation to preserve a test-first loop.
- `T014` can proceed after the provenance model exists, while parts of compiler assembly are already in place.

## Implementation Strategy

1. Create the source, provenance, and budget contracts first.
2. Prove deterministic packet assembly under a roomy budget.
3. Add lower-tier trimming and must-tier overflow protection.
4. Finish with deduplication and the provenance footer.
5. Validate with focused pytest and lint checks, then mark completed tasks in this file.
