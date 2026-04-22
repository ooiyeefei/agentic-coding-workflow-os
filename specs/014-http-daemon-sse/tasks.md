# Tasks: HTTP Daemon + SSE

**Input**: Design documents from `/specs/014-http-daemon-sse/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/daemon-http.md  
**Tests**: Tests are required because the acceptance criteria explicitly require AsyncClient coverage for creation, inspection, SSE streaming, approval, and the local auth boundary.  
**Organization**: Tasks are grouped by user story so the HTTP read/write contract stays independently traceable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the feature documentation and the focused daemon verification surface

- [X] T001 Create the daemon feature documentation set in `specs/014-http-daemon-sse/`
- [X] T002 Create focused AsyncClient coverage scaffolding in `tests/test_daemon.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the shared daemon app, auth boundary, and audit streaming primitives reused by every story

- [X] T003 Implement the FastAPI app factory, daemon config, secret resolution, localhost/CORS enforcement, and runnable daemon entrypoint in `atelier/daemon/server.py` and `atelier/daemon/__main__.py`
- [X] T004 [P] Implement run loading, create, and approve route helpers in `atelier/daemon/routes.py`
- [X] T005 [P] Implement audit-tail parsing and SSE event formatting in `atelier/daemon/events.py`

**Checkpoint**: The daemon has an app factory, a stable security boundary, and reusable route/event helpers.

---

## Phase 3: User Story 1 - Create And Inspect Runs Over HTTP (Priority: P1) 🎯 MVP

**Goal**: Let non-CLI clients create runs and fetch current run metadata over HTTP

**Independent Test**: `POST /runs` followed by `GET /runs/<run_id>` returns the persisted run snapshot from repo-local state.

### Tests for User Story 1

- [X] T006 [P] [US1] Add AsyncClient coverage for `POST /runs` and `GET /runs/<run_id>` in `tests/test_daemon.py`

### Implementation for User Story 1

- [X] T007 [US1] Implement `POST /runs` and `GET /runs/<run_id>` in `atelier/daemon/routes.py`

**Checkpoint**: Clients can create and inspect runs without invoking the CLI.

---

## Phase 4: User Story 2 - Stream Audit Events Live With SSE (Priority: P2)

**Goal**: Let non-CLI clients subscribe to per-run audit events as they are appended

**Independent Test**: `GET /runs/<run_id>/events` emits existing and newly appended audit events over SSE in an in-process test.

### Tests for User Story 2

- [X] T008 [P] [US2] Add AsyncClient SSE coverage for `GET /runs/<run_id>/events` in `tests/test_daemon.py`

### Implementation for User Story 2

- [X] T009 [US2] Implement the SSE events route in `atelier/daemon/routes.py`
- [X] T010 [US2] Finalize live audit tail streaming behavior in `atelier/daemon/events.py`

**Checkpoint**: Future dashboard and IDE clients can observe live run events over HTTP.

---

## Phase 5: User Story 3 - Approve A Gated Stage Over HTTP (Priority: P3)

**Goal**: Let non-CLI clients approve runs blocked on completed gate waits

**Independent Test**: A seeded gate-waiting run advances after `POST /runs/<run_id>/approve`, and ineligible runs return conflicts.

### Tests for User Story 3

- [X] T011 [P] [US3] Add AsyncClient coverage for successful and rejected approval requests plus the auth boundary in `tests/test_daemon.py`

### Implementation for User Story 3

- [X] T012 [US3] Implement `POST /runs/<run_id>/approve` in `atelier/daemon/routes.py`

**Checkpoint**: Future plugin clients can unblock human-gated stages over HTTP.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate contract details, security defaults, and focused daemon quality gates

- [X] T013 Audit `atelier/daemon/server.py`, `atelier/daemon/routes.py`, `atelier/daemon/events.py`, and `atelier/daemon/__main__.py` for consistent error handling and local-only security behavior
- [X] T014 Run `uv run pytest tests/test_daemon.py -q`
- [X] T015 Run `uv run ruff check atelier/daemon tests/test_daemon.py`

---

## Dependencies & Execution Order

- Setup tasks come first.
- Foundational tasks block all user stories because every route depends on the app factory, auth, and event helpers.
- User Story 1 is the MVP because it defines the create/read contract.
- User Story 2 depends on the foundational SSE helper but not on approval.
- User Story 3 depends on the run metadata and workflow helpers established by User Story 1.
- Polish happens last.

## Parallel Opportunities

- `T004` and `T005` can proceed in parallel after the app factory contract is fixed.
- `T006`, `T008`, and `T011` can be written early to drive implementation.
- Within User Story 2, route wiring and event-tail refinement can proceed together once the stream contract is agreed.

## Implementation Strategy

1. Establish the daemon app factory and local auth boundary.
2. Land the run creation and inspection contract first.
3. Add SSE tailing for live audit visibility.
4. Add gate approval once the shared run read model is in place.
5. Validate with focused AsyncClient tests and linting.
