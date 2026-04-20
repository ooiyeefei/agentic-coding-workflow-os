# Tasks: Secret Redaction

**Input**: Design documents from `/specs/006-secret-redaction/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/redaction.md  
**Tests**: Tests are required because the acceptance criteria explicitly require 30+ positive cases, 10+ negative cases, and exact behavior for key examples.  
**Organization**: Tasks are grouped by user story so core secret redaction, context preservation, and custom pattern support stay independently traceable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the feature-local module and focused test surface

- [X] T001 Create the focused redaction test module in `tests/test_redaction.py`
- [X] T002 [P] Create the pattern catalog and redaction module stubs in `atelier/security/patterns.py` and `atelier/security/redaction.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define named built-in patterns and shared marker helpers before story-specific behavior

- [X] T003 Define the ordered built-in pattern catalog and marker names in `atelier/security/patterns.py`
- [X] T004 Implement shared marker rendering and redaction-pass helpers in `atelier/security/redaction.py`

**Checkpoint**: Named redaction markers and the core substitution flow exist for all user stories.

---

## Phase 3: User Story 1 - Redact Known Secrets Before Persistence (Priority: P1) 🎯 MVP

**Goal**: Redact common credential shapes from persisted text in one pass

**Independent Test**: Run positive secret-bearing cases covering env assignments, known token prefixes, bearer tokens, AWS access keys, and GCP service-account material, and confirm each secret substring is replaced with an audit-visible marker.

### Tests for User Story 1

- [X] T005 [P] [US1] Add 30+ positive redaction cases in `tests/test_redaction.py`

### Implementation for User Story 1

- [X] T006 [US1] Implement built-in secret replacement behavior in `atelier/security/redaction.py`

**Checkpoint**: Representative secrets are redacted with `[REDACTED:<pattern-name>]` markers.

---

## Phase 4: User Story 2 - Preserve Useful Context While Avoiding False Positives (Priority: P2)

**Goal**: Keep logs readable by preserving safe text and URL/header shape

**Independent Test**: Run safe passthrough, URL credential, bearer-header, idempotence, and false-positive checks and confirm surrounding context remains readable.

### Tests for User Story 2

- [X] T007 [P] [US2] Add 10+ negative and shape-preservation cases in `tests/test_redaction.py`

### Implementation for User Story 2

- [X] T008 [US2] Implement case-insensitive env-name handling, URL credential redaction, and false-positive guards in `atelier/security/redaction.py`

**Checkpoint**: Safe text remains unchanged and structured values preserve useful context after redaction.

---

## Phase 5: User Story 3 - Extend Coverage With Extra Patterns (Priority: P3)

**Goal**: Let callers append custom regexes without changing the built-in catalog

**Independent Test**: Supply one or more caller-defined extra patterns and confirm they redact custom tokens using stable `extra-pattern-*` markers while built-in behavior still works.

### Tests for User Story 3

- [X] T009 [P] [US3] Add custom-pattern coverage in `tests/test_redaction.py`

### Implementation for User Story 3

- [X] T010 [US3] Implement `extra_patterns` support with stable ordinal marker labels in `atelier/security/redaction.py`

**Checkpoint**: Custom regexes extend the redactor without breaking built-in coverage.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the feature end-to-end and sync task state

- [X] T011 Run `uv run pytest tests/test_redaction.py -v`, `uv run ruff check atelier/security/patterns.py atelier/security/redaction.py tests/test_redaction.py`, and `uv run pyright atelier/security/patterns.py atelier/security/redaction.py tests/test_redaction.py`
- [X] T012 Update completed task markers in `specs/006-secret-redaction/tasks.md`

---

## Dependencies & Execution Order

- Setup must complete before foundational work.
- Foundational work blocks all user stories because named markers and the ordered pattern catalog are shared infrastructure.
- User Story 1 must complete before the later stories because built-in secret detection is the MVP.
- User Story 2 depends on User Story 1 because context-preserving behavior refines the same redaction paths.
- User Story 3 depends on the foundational substitution flow but can land after User Story 1 and User Story 2 in the same branch.
- Polish happens last.

## Parallel Opportunities

- `T001` and `T002` touch different files and can start in parallel.
- `T005`, `T007`, and `T009` are all test-writing tasks in the same module and should still land sequentially in one branch, but each represents a distinct story-level slice.
- Once `T003` is done, parts of `T004` and `T005` can proceed in parallel conceptually because marker names are fixed.

## Implementation Strategy

1. Establish the module/test scaffolding and the named pattern catalog first.
2. Write the positive secret cases and implement the core redaction behavior for the MVP.
3. Add preservation and false-positive coverage, then refine the redactor to keep URL and prose context visible.
4. Add caller-supplied extra pattern coverage and implementation.
5. Finish with focused pytest, ruff, and pyright validation, then mark the tasks complete.
