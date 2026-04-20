# Tasks: UAT Persona Integration

**Input**: Design documents from `/specs/008-uat-persona-integration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/uat-persona.md

**Tests**: Focused pytest coverage is required for this feature because the external UAT skill is not present in-repo.

**Organization**: Tasks are grouped by user story so the subprocess path, Evidence Pack mapping, and error-handling behavior remain independently testable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the persona prompt and public package surface for the UAT slice

- [X] T001 Create the shipped UAT prompt in .atelier/defaults/personas/uat.md
- [X] T002 Update persona package exports in atelier/personas/__init__.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the minimal shared models needed by all UAT stories

- [X] T003 Create minimal Evidence Pack models in atelier/evidence/schema.py and atelier/evidence/__init__.py
- [X] T004 Create focused secret redaction support in atelier/security/redaction.py and atelier/security/__init__.py

**Checkpoint**: Persona code can now return structured evidence safely

---

## Phase 3: User Story 1 - Run Real UAT Against The Target App (Priority: P1) 🎯 MVP

**Goal**: Execute the external UAT subprocess with resolved app context and credentials

**Independent Test**: A mocked subprocess invocation proves the runner launches the external skill with the expected inputs and that `UAT.respond(...)` preserves persona routing metadata.

### Tests for User Story 1

- [X] T005 [P] [US1] Add capability-routing and subprocess invocation tests in tests/test_uat.py

### Implementation for User Story 1

- [X] T006 [US1] Implement request parsing, skill resolution, and credential loading in atelier/personas/uat_runner.py
- [X] T007 [US1] Implement the UAT persona orchestration in atelier/personas/uat.py

**Checkpoint**: UAT can launch a real subprocess-backed run against a target app

---

## Phase 4: User Story 2 - Convert UAT Output Into Structured Evidence (Priority: P2)

**Goal**: Parse UAT output into summary, findings, and execution evidence

**Independent Test**: A mocked UAT report is converted into the expected Evidence Pack summary and findings, with stdout and stderr captured separately.

### Tests for User Story 2

- [X] T008 [P] [US2] Add report-parsing and Evidence Pack mapping tests in tests/test_uat.py

### Implementation for User Story 2

- [X] T009 [US2] Implement report parsing and Evidence Pack construction in atelier/personas/uat_runner.py

**Checkpoint**: UAT output is reusable by downstream workflow stages

---

## Phase 5: User Story 3 - Keep UAT Persona Capability-Gated And Transparent (Priority: P3)

**Goal**: Surface failures, redaction, and timeout behavior without silent fallbacks

**Independent Test**: Invalid skill-path and credential-redaction tests prove the persona fails loudly and does not leak secrets into evidence.

### Tests for User Story 3

- [X] T010 [P] [US3] Add invalid-skill-path, timeout, and credential-redaction tests in tests/test_uat.py

### Implementation for User Story 3

- [X] T011 [US3] Implement clear execution-error handling and timeout behavior in atelier/personas/uat_runner.py

**Checkpoint**: UAT behavior is safe, explicit, and reviewable

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final integration verification

- [X] T012 Run focused pytest verification for tests/test_uat.py

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup must complete before shared exports are available.
- Foundational tasks block all user-story work because Evidence Pack and redaction support are shared.
- User stories then proceed in priority order, though their test tasks can be written in parallel.
- Polish depends on all story tasks completing.

### User Story Dependencies

- **User Story 1 (P1)**: Depends on foundational evidence/redaction support.
- **User Story 2 (P2)**: Depends on User Story 1's runner skeleton.
- **User Story 3 (P3)**: Depends on the runner and parser from the earlier stories.

### Parallel Opportunities

- T005, T008, and T010 can be written in parallel because they focus on distinct behaviors inside the same test module.
- T003 and T004 can proceed in parallel because they touch separate packages.

## Implementation Strategy

### MVP First

1. Finish Setup and Foundational phases.
2. Complete User Story 1 so the persona can run the external UAT skill at all.
3. Add User Story 2 to make the result consumable as evidence.
4. Add User Story 3 to harden failure handling and redaction.
5. Run the focused test suite.

## Notes

- The external `ccc/skills/uat-testing` asset is not present in this repository, so tests must mock subprocess execution rather than shelling into a real sibling checkout.
- Credential redaction is required anywhere execution evidence is surfaced, even before broader W10 integration lands.
