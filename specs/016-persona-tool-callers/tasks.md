# Tasks: Persona Tool Callers

**Input**: Design documents from `/specs/016-persona-tool-callers/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are included because the acceptance criteria require new caller coverage and existing backward compatibility.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 [P] Create caller contract tests in tests/test_persona_callers.py

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T002 Add atelier/personas/callers.py with AgentToolCaller and DirectAPICaller skeletons
- [x] T003 Update exports in atelier/personas/__init__.py

## Phase 3: User Story 1 - Generate Agent Tool Prompts (Priority: P1)

**Goal**: Main persona stages can generate paste-ready prompts for external agent tools.

**Independent Test**: `pytest tests/test_persona_callers.py -k agent_tool`

- [x] T004 [US1] Implement tool adapter resolution in atelier/personas/callers.py
- [x] T005 [US1] Implement AgentToolCaller prompt composition and stdout printing in atelier/personas/callers.py
- [x] T006 [US1] Add Persona.respond_via_tool() in atelier/personas/base.py

## Phase 4: User Story 2 - Preserve Direct API Compatibility (Priority: P2)

**Goal**: Existing direct model-call persona behavior remains available and test-compatible.

**Independent Test**: `pytest tests/test_personas.py tests/test_persona_callers.py -k direct`

- [x] T007 [US2] Extract Persona direct response internals in atelier/personas/base.py
- [x] T008 [US2] Implement DirectAPICaller delegation in atelier/personas/callers.py
- [x] T009 [US2] Keep Persona.respond() default behavior backward compatible in atelier/personas/base.py

## Phase 5: User Story 3 - Use Correct Callers In Workflow Execution (Priority: P3)

**Goal**: Default workflow wiring uses AgentToolCaller for main stages while direct caller remains available for auxiliary work.

**Independent Test**: `pytest tests/test_workflow.py tests/test_persona_callers.py`

- [x] T010 [US3] Add default dependency construction using AgentToolCaller in atelier/workflow/engine.py
- [x] T011 [US3] Preserve explicit StageExecutorDeps injection behavior in atelier/workflow/engine.py

## Final Phase: Polish & Cross-Cutting Concerns

- [x] T012 Run targeted tests for persona callers, personas, and workflow
- [x] T013 Review implementation for prompt clarity and no accidental API calls in AgentToolCaller

## Dependencies & Execution Order

- Setup and foundational tasks precede all user stories.
- US1 and US2 both touch caller/base behavior and should be implemented sequentially.
- US3 depends on US1 caller availability.

## Parallel Opportunities

- T001 can be drafted while implementation skeletons are created.

## Implementation Strategy

1. Add failing tests that define the caller behavior.
2. Implement caller module and persona base delegation.
3. Wire workflow defaults without changing the stage protocol.
4. Run the targeted test suite and mark completed tasks.
