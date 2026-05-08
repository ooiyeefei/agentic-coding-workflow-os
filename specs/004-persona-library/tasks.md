# Tasks: Persona Library

**Input**: Design documents from `/specs/004-persona-library/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/personas.md  
**Tests**: Tests are required for this feature because the acceptance criteria explicitly require routing checks, prompt validation, and structured persona responses.  
**Organization**: Tasks are grouped by user story so routing, structured responses, and Reviewer prompt discipline stay independently traceable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the default prompt locations and focused persona test surface

- [X] T001 Create the persona defaults directory and prompt files in `.spanweave/defaults/personas/coder.md` and `.spanweave/defaults/personas/reviewer.md`
- [X] T002 Create the focused persona verification module in `tests/test_personas.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Align adjacent LLM metadata and create the shared persona contract

- [X] T003 Update shipped manifest capability metadata and adjacent W02 expectations in `.spanweave/defaults/models/gpt-5.yaml`, `spanweave/llm/adapter.py`, and `tests/test_llm_adapter.py`
- [X] T004 Create shared persona models, prompt loading, and exports in `spanweave/personas/base.py` and `spanweave/personas/__init__.py`

**Checkpoint**: Persona routing can rely on compatible default manifests and one shared base contract.

---

## Phase 3: User Story 1 - Route Personas To Compatible Models (Priority: P1) 🎯 MVP

**Goal**: Bind Coder and Reviewer to the first compatible manifest via W02 routing

**Independent Test**: Instantiate Coder and Reviewer against shipped or injected manifests, verify successful routing, and confirm Reviewer raises `UnsupportedCapabilityError` when only incompatible manifests are available.

### Tests for User Story 1

- [X] T005 [P] [US1] Add routing success and failure tests in `tests/test_personas.py`

### Implementation for User Story 1

- [X] T006 [US1] Implement lazy manifest selection and adapter binding in `spanweave/personas/base.py`
- [X] T007 [US1] Implement Coder and Reviewer initialization plumbing in `spanweave/personas/coder.py` and `spanweave/personas/reviewer.py`

**Checkpoint**: `Coder()` and `Reviewer()` resolve compatible manifests through W02 on default or injected inputs.

---

## Phase 4: User Story 2 - Produce Structured Persona Responses (Priority: P2)

**Goal**: Return one structured `AgentResponse` shape and give Coder next-command guidance

**Independent Test**: Inject a mock adapter, call `respond(...)` on each persona, and verify the returned object preserves normalized response fields plus persona metadata and Coder command guidance.

### Tests for User Story 2

- [X] T008 [P] [US2] Add `respond(...)` shape and Coder next-command tests in `tests/test_personas.py`

### Implementation for User Story 2

- [X] T009 [US2] Implement context-packet serialization and `AgentResponse` construction in `spanweave/personas/base.py`
- [X] T010 [US2] Implement Coder skill discovery and Phase 0 fallback sequencing in `spanweave/personas/coder.py`

**Checkpoint**: Persona responses are normalized and Coder can identify the next `/speckit.*` command even without W05.

---

## Phase 5: User Story 3 - Enforce Execution-Mandatory Review Discipline (Priority: P3)

**Goal**: Ship a strict Reviewer prompt plus opt-in devil's-advocate scaffolding

**Independent Test**: Validate the shipped Reviewer prompt text, compare default vs devil's-advocate prompts, and confirm the default flag remains off.

### Tests for User Story 3

- [X] T011 [P] [US3] Add execution-mandatory prompt and devil's-advocate tests in `tests/test_personas.py`

### Implementation for User Story 3

- [X] T012 [US3] Author the Coder and Reviewer prompt definitions in `.spanweave/defaults/personas/coder.md` and `.spanweave/defaults/personas/reviewer.md`
- [X] T013 [US3] Implement Reviewer prompt augmentation and convenience review entrypoint in `spanweave/personas/reviewer.py`

**Checkpoint**: Reviewer prompt discipline is explicit, testable, and configurable through `devil_advocate_mode`.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the slice end-to-end and sync task state

- [X] T014 Run focused pytest coverage for `tests/test_personas.py` and `tests/test_llm_adapter.py`
- [X] T015 Run lint and type checks for `spanweave/personas/`, `tests/test_personas.py`, and adjacent LLM updates

---

## Dependencies & Execution Order

- Setup must complete before foundational work.
- Foundational work blocks all user stories because persona routing depends on shared prompt loading and compatible manifest metadata.
- User Story 1 must complete before User Story 2 and User Story 3 because successful routing is the base requirement for any persona behavior.
- User Story 2 and User Story 3 can proceed after User Story 1, though both still share the same test module and should land sequentially in one branch.
- Polish happens last.

## Parallel Opportunities

- `T005`, `T008`, and `T011` can be written before implementation to preserve a test-first loop.
- `T012` can proceed in parallel with parts of `T013` once the prompt contract is fixed.
- Adjacent LLM test updates in `T003` can be prepared while the persona base contract in `T004` is being designed.

## Implementation Strategy

1. Align the shipped manifest metadata and shared persona contract first.
2. Prove default and failure-path routing with focused tests.
3. Add structured `respond(...)` behavior and Coder skill sequencing.
4. Finish with the Reviewer prompt discipline and devil's-advocate toggle.
5. Validate with focused pytest, lint, and type checks, then mark completed tasks in this file.
