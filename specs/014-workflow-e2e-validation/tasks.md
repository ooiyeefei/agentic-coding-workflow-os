# Tasks: Workflow E2E Validation

**Input**: Design documents from `/specs/014-workflow-e2e-validation/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/integration-suite.md  
**Tests**: Tests are required because the feature is itself an integration and CI validation layer.  
**Organization**: Tasks are grouped by user story so the full workflow run, pairwise component boundaries, and CI automation remain independently traceable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the feature-local documentation set and integration test scaffolding

- [X] T001 Create the W24 documentation set in `specs/014-workflow-e2e-validation/`
- [X] T002 Create the integration test package skeleton in `tests/integration/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the shared harness that every integration scenario uses

- [X] T003 Implement shared isolated repo fixtures and persona-mode selection in `tests/integration/conftest.py`
- [X] T004 [P] Define deterministic mock persona, reviewer, evidence, memory, and ADR helpers in `tests/integration/conftest.py`

**Checkpoint**: The repo has a reusable integration harness that can execute workflow scenarios without shared state.

---

## Phase 3: User Story 1 - Validate The Full Workflow Run (Priority: P1) 🎯 MVP

**Goal**: Prove the shipped `speckit-loop` workflow completes end-to-end against the demo fixtures

**Independent Test**: `uv run pytest tests/integration/test_e2e_workflow.py -q`

### Tests for User Story 1

- [X] T005 [P] [US1] Add the full end-to-end workflow test in `tests/integration/test_e2e_workflow.py`

### Implementation for User Story 1

- [X] T006 [US1] Wire packet, transcript, evidence, memory, ADR, and approval handling into the E2E harness in `tests/integration/conftest.py`
- [X] T007 [US1] Verify all stage artifacts, completion markers, and ADR outputs in `tests/integration/test_e2e_workflow.py`

**Checkpoint**: The default workflow is validated against the real demo fixtures and filesystem outputs.

---

## Phase 4: User Story 2 - Verify Component Boundaries In Pairs (Priority: P2)

**Goal**: Localize regressions across the highest-risk subsystem boundaries

**Independent Test**: `uv run pytest tests/integration/test_component_integration.py -q`

### Tests for User Story 2

- [X] T008 [P] [US2] Add compiler-to-persona and persona-to-evidence integration checks in `tests/integration/test_component_integration.py`
- [X] T009 [P] [US2] Add workflow-to-rungraph and ADR-synthesis integration checks in `tests/integration/test_component_integration.py`

### Implementation for User Story 2

- [X] T010 [US2] Reuse the shared harness from `tests/integration/conftest.py` so component tests assert against real repository modules instead of bespoke fixtures

**Checkpoint**: The riskiest subsystem contracts have focused coverage in addition to the single E2E path.

---

## Phase 5: User Story 3 - Keep Validation Running On Every PR (Priority: P3)

**Goal**: Mirror the integration gate locally and in GitHub Actions

**Independent Test**: Review `.github/workflows/ci.yaml`, run `./scripts/run-e2e.sh`, and confirm the script defaults to mock mode while CI exposes separate lint/type/unit/integration checks.

### Tests for User Story 3

- [X] T011 [P] [US3] Add CI workflow definition in `.github/workflows/ci.yaml`
- [X] T012 [P] [US3] Add the local one-command runner in `scripts/run-e2e.sh`

### Implementation for User Story 3

- [X] T013 [US3] Ensure the local script and CI use equivalent integration commands and default mock behavior

**Checkpoint**: Contributors and PRs use the same validation path.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the feature against repository-wide quality gates

- [X] T014 Run `uv run pytest tests/integration/test_component_integration.py tests/integration/test_e2e_workflow.py -q`
- [X] T015 Run `uv run ruff check .` and `bash -n scripts/run-e2e.sh`
- [X] T016 Run `uv run pyright atelier/compiler atelier/evidence atelier/git atelier/memory atelier/personas atelier/workflow tests/integration`
- [X] T017 Run `uv run pytest tests -q`

---

## Dependencies & Execution Order

- Phase 1 must finish before shared harness work begins.
- Phase 2 blocks the user stories because the same fixture layer powers E2E and component integration coverage.
- User Story 1 lands first because it is the Phase 0 release gate.
- User Story 2 reuses the same harness but narrows the assertions to component boundaries.
- User Story 3 follows once the integration commands are stable enough to codify in CI and the local runner.
- Polish happens last.

## Parallel Opportunities

- `T004` can proceed while the base fixtures in `T003` are being finalized.
- `T008` and `T009` can be developed in parallel because they target separate test cases inside the same module.
- `T011` and `T012` can proceed in parallel once the core integration commands are fixed.

## Implementation Strategy

1. Build one shared harness that composes the real repository modules in isolated temporary repos.
2. Use that harness to prove the full `speckit-loop` flow works against the demo fixtures.
3. Add focused component integration tests to make regressions diagnosable.
4. Mirror the stable commands in a GitHub Actions workflow and a one-command local runner.
5. Finish by running the full repo validation gates and leaving the tasks marked complete.
