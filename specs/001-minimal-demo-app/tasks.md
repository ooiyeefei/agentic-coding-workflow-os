# Tasks: Minimal Demo App

**Input**: Design documents from `/specs/001-minimal-demo-app/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/demo-app.openapi.yaml

**Tests**: Tests are required for this feature because the acceptance criteria call for at least four tests covering auth and CRUD happy paths.

**Organization**: Tasks are grouped by user story to keep the login flow, protected API, and browser walkthrough independently traceable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish project metadata and local run instructions

- [ ] T001 Create Python project metadata and dependencies in demo/app/pyproject.toml
- [ ] T002 Create demo credential defaults and short local run instructions in demo/app/.env.example and demo/app/README.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the shared app skeleton that every story relies on

- [ ] T003 Create environment-backed settings loading in demo/app/app/config.py
- [ ] T004 Create the in-memory session and notes store in demo/app/app/store.py
- [ ] T005 Implement the FastAPI app shell and shared route helpers in demo/app/app/main.py
- [ ] T006 [P] Create the login page template in demo/app/app/templates/login.html
- [ ] T007 [P] Create the notes page template in demo/app/app/templates/notes.html

**Checkpoint**: A runnable app skeleton exists and the remaining work can focus on user stories.

---

## Phase 3: User Story 1 - Sign In To The Demo (Priority: P1) 🎯 MVP

**Goal**: Establish browser login, logout, and session protection

**Independent Test**: Open the login page, sign in with the demo account, and confirm the authenticated page is reachable while protected routes reject anonymous requests.

### Tests for User Story 1

- [ ] T008 [P] [US1] Add authentication and unauthorized access tests in demo/app/tests/test_app.py

### Implementation for User Story 1

- [ ] T009 [US1] Implement login and logout handlers in demo/app/app/main.py
- [ ] T010 [US1] Implement session cookie validation for protected routes in demo/app/app/main.py and demo/app/app/store.py

**Checkpoint**: Login works and route protection is enforced.

---

## Phase 4: User Story 2 - Manage Notes Through A Protected API (Priority: P2)

**Goal**: Provide authenticated list, create, and delete note operations

**Independent Test**: After signing in, call the notes API to list notes, create one note, delete it, and verify the list reflects each change.

### Tests for User Story 2

- [ ] T011 [P] [US2] Add protected notes list, create, and delete tests in demo/app/tests/test_app.py

### Implementation for User Story 2

- [ ] T012 [US2] Implement note list and create endpoints in demo/app/app/main.py
- [ ] T013 [US2] Implement note create and delete storage operations in demo/app/app/store.py
- [ ] T014 [US2] Implement note delete endpoint in demo/app/app/main.py

**Checkpoint**: The protected CRUD API is complete and testable.

---

## Phase 5: User Story 3 - Walk Through The Feature In A Browser (Priority: P3)

**Goal**: Make the authenticated feature easy to demo visually

**Independent Test**: Sign in from the browser, add a note from the notes page, observe it render, delete it from the page, and confirm the list updates.

### Tests for User Story 3

- [ ] T015 [P] [US3] Add page-level behavior tests for redirects and rendered content in demo/app/tests/test_app.py

### Implementation for User Story 3

- [ ] T016 [US3] Render login and notes pages with server-side context in demo/app/app/main.py
- [ ] T017 [US3] Implement notes page browser interactions in demo/app/app/templates/notes.html

**Checkpoint**: The app can be demonstrated end-to-end in a browser.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and demo readiness

- [ ] T018 Update package exports in demo/app/app/__init__.py
- [ ] T019 Validate local run/test commands against the finished app in demo/app/README.md
- [ ] T020 Run the full pytest suite for demo/app and resolve any failures

---

## Dependencies & Execution Order

- Setup must finish before foundational work.
- Foundational work blocks every user story.
- User Story 1 must finish before User Stories 2 and 3 because both depend on authenticated access.
- User Story 2 should finish before the User Story 3 browser walkthrough so the page can call a stable notes API.
- Polish happens last.

## Parallel Opportunities

- `T006` and `T007` can run in parallel because they modify different template files.
- `T008`, `T011`, and `T015` can each be written before their implementation tasks to preserve a test-first loop.
- Once `T005` is in place, template work can proceed in parallel with store refinements.

## Implementation Strategy

1. Build the smallest runnable FastAPI shell first.
2. Make authentication correct and test it before expanding the API.
3. Add the protected notes endpoints and their tests.
4. Layer the browser interactions on top of the working API.
5. Finish by proving the local commands and test suite work as documented.
