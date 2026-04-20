# Tasks: Typed Memory Records

**Input**: Design documents from `/specs/005-typed-memory-records/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/memory-records.md  
**Tests**: Tests are required for this feature because the acceptance criteria explicitly require round-trip persistence, tag filtering, and write-time redaction.  
**Organization**: Tasks are grouped by user story so persistence, reading, and querying stay independently testable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the focused verification surface and feature module exports

- [X] T001 Create the focused memory persistence test module in `tests/test_memory.py`
- [X] T002 Create the public exports for `atelier/memory/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define the shared record schema and the supporting redaction boundary

- [X] T003 Create the redaction entrypoint needed by the writer in `atelier/security/redaction.py` and `atelier/security/__init__.py`
- [X] T004 Create the shared record models and validation helpers in `atelier/memory/records.py`

**Checkpoint**: Typed record validation and the write-time redaction dependency both exist.

---

## Phase 3: User Story 1 - Persist A Typed Memory Record (Priority: P1) 🎯 MVP

**Goal**: Write one typed record to the filesystem with YAML frontmatter, markdown body, atomic replacement, and write-time redaction

**Independent Test**: Construct a `Decision`, write it to a temporary memory root, and confirm the file path, frontmatter, body structure, and redacted content all match expectations.

### Tests for User Story 1

- [X] T005 [P] [US1] Add writer and redaction tests in `tests/test_memory.py`

### Implementation for User Story 1

- [X] T006 [US1] Implement markdown serialization and destination path resolution in `atelier/memory/writer.py`
- [X] T007 [US1] Wire record-specific collection and filename helpers into `atelier/memory/records.py` and `atelier/memory/writer.py`

**Checkpoint**: Writing a typed record produces one redacted markdown file in the expected collection.

---

## Phase 4: User Story 2 - Read A Typed Memory Record Back Into A Schema (Priority: P2)

**Goal**: Reconstruct persisted markdown records as validated typed models while preserving the markdown body

**Independent Test**: Write a record fixture with headings, lists, and fenced code blocks, read it back, and confirm field-by-field equality for the non-secret round-trip case.

### Tests for User Story 2

- [X] T008 [P] [US2] Add round-trip read tests with markdown body preservation in `tests/test_memory.py`

### Implementation for User Story 2

- [X] T009 [US2] Implement frontmatter parsing and typed record reconstruction in `atelier/memory/reader.py`

**Checkpoint**: `read_record(...)` returns concrete typed records with preserved markdown bodies.

---

## Phase 5: User Story 3 - Query Typed Records By Type And Metadata (Priority: P3)

**Goal**: List persisted records recursively and filter them by type and frontmatter metadata without a database

**Independent Test**: Write mixed record fixtures with different tags and types, run `list_records(type="Decision", tags=["safety-critical"])`, and confirm only the expected Decision records are returned.

### Tests for User Story 3

- [X] T010 [P] [US3] Add recursive listing and metadata filter tests in `tests/test_memory.py`

### Implementation for User Story 3

- [X] T011 [US3] Implement recursive record discovery and filter evaluation in `atelier/memory/reader.py`

**Checkpoint**: `list_records(...)` returns the expected filtered subset from a filesystem-backed fixture set.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the slice end-to-end and sync task state

- [X] T012 Update any remaining memory package exports and module docstrings in `atelier/memory/__init__.py`
- [X] T013 Run focused pytest coverage for `tests/test_memory.py`
- [X] T014 Run lint checks for `atelier/memory`, `atelier/security`, and `tests/test_memory.py`

---

## Dependencies & Execution Order

- Setup must complete before foundational work.
- Foundational work blocks all user stories because record validation and redaction are shared prerequisites.
- User Story 1 must complete before User Story 2 and User Story 3 because there must be persisted fixtures to read and query.
- User Story 2 and User Story 3 can proceed after User Story 1, though they still share the same test module and should land sequentially in one branch.
- Polish happens last.

## Parallel Opportunities

- `T005`, `T008`, and `T010` can be written before implementation to preserve a test-first loop.
- `T003` and `T004` touch different modules and can be designed in parallel.
- Once the core schema exists, read-path and query-path test cases can be prepared while the writer implementation settles.

## Implementation Strategy

1. Establish the strict record schema and the redaction dependency first.
2. Prove the write path, including filename policy and write-time redaction.
3. Add read-path reconstruction with exact markdown body preservation.
4. Finish with recursive listing and metadata filtering.
5. Validate with focused pytest and lint, then mark completed tasks in this file.
