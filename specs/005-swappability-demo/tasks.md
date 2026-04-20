# Tasks: Swappability Demo

**Input**: Design documents from `/specs/005-swappability-demo/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/swap-demo.md  
**Tests**: Tests are required for this feature because the acceptance criteria depend on deterministic fixture generation, capability gating, and Evidence Pack rendering.  
**Organization**: Tasks are grouped by user story so the dual-backend run, capability-failure proof, and narration remain independently traceable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the demo file surface and focused verification module

- [X] T001 Create the demo test surface in `tests/test_swap_demo.py`
- [X] T002 Create the narration shell and output directories in `demo/swap-demo.md` and `demo/swap-demo-output/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the shared runner primitives used by every demo path

- [X] T003 Implement configuration loading, manifest resolution, and fixture generation in `demo/swap-demo.py`
- [X] T004 Implement markdown Evidence Pack rendering and filesystem write helpers in `demo/swap-demo.py`

**Checkpoint**: The demo script can prepare a shared workspace and knows how to render run results into the owned output paths.

---

## Phase 3: User Story 1 - Run The Same Review Twice (Priority: P1) 🎯 MVP

**Goal**: Execute the same review loop against Claude and Codex/OpenAI backends

**Independent Test**: Run the demo in mock mode and confirm both generated Evidence Packs find the planted off-by-one bug through the same tool-driven review loop.

### Tests for User Story 1

- [X] T005 [P] [US1] Add fixture, tool-loop, and mock-backend tests in `tests/test_swap_demo.py`

### Implementation for User Story 1

- [X] T006 [US1] Implement the shared reviewer prompt loading and tool definitions in `demo/swap-demo.py`
- [X] T007 [US1] Implement the dual-backend review loop, live/mock backend selection, and successful-run summary in `demo/swap-demo.py`
- [X] T008 [US1] Write the captured Claude and Codex Evidence Packs by running `demo/swap-demo.py`

**Checkpoint**: `demo/swap-demo.py` writes `demo/swap-demo-output/claude/evidence.md` and `demo/swap-demo-output/codex/evidence.md`, and both packs identify the planted bug.

---

## Phase 4: User Story 2 - Prove Capability Gating Works (Priority: P2)

**Goal**: Surface the incompatible-model failure path instead of silently degrading

**Independent Test**: Run the script's unsupported-model check and confirm it reports `UnsupportedCapabilityError` for a model without `tool_use`.

### Tests for User Story 2

- [X] T009 [P] [US2] Add capability-gating and unsupported-manifest tests in `tests/test_swap_demo.py`

### Implementation for User Story 2

- [X] T010 [US2] Implement the `tool_use=True` guardrail and incompatible-manifest proof path in `demo/swap-demo.py`
- [X] T011 [US2] Include the incompatible-model result in the console summary and Evidence Pack metadata handling in `demo/swap-demo.py`

**Checkpoint**: The demo visibly shows both successful runs and the expected manifest-gated failure case.

---

## Phase 5: User Story 3 - Narrate The Demo In Under One Minute (Priority: P3)

**Goal**: Give the presenter a concise, high-signal script for the live beat

**Independent Test**: Read `demo/swap-demo.md` aloud and confirm it fits within 60 seconds while naming the swap, the bug, and the guardrail.

### Implementation for User Story 3

- [X] T012 [US3] Write the final narration script in `demo/swap-demo.md`
- [X] T013 [US3] Align the generated Evidence Packs and narration wording so the live demo can compare them side by side

**Checkpoint**: The script and the artifacts tell the same story without extra explanation.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the feature end to end and sync completion state

- [X] T014 Run focused pytest coverage for `tests/test_swap_demo.py`
- [X] T015 Run `demo/swap-demo.py` in the best available mode and verify the expected output files
- [X] T016 Confirm `demo/swap-demo.md` fits within the timing target and update this task file to reflect completed work

---

## Dependencies & Execution Order

- Phase 1 must complete before foundational work.
- Phase 2 blocks all user stories because the workspace, config, and evidence writer are shared.
- User Story 1 is the MVP and must land before the capability-failure proof and narration polishing.
- User Story 2 depends on the same runner skeleton as User Story 1 but can proceed once the shared loop exists.
- User Story 3 depends on the generated artifacts because the narration needs to match the actual demo flow.
- Polish happens last.

## Parallel Opportunities

- `T005` and `T009` can be written before or alongside implementation to keep the runner honest.
- Once the fixture and renderer exist, the narration drafting in `T012` can proceed while the unsupported-manifest proof is being finalized.

## Implementation Strategy

1. Build the runtime workspace and evidence renderer first.
2. Prove the dual-backend success path in mock mode.
3. Add the incompatible-manifest guardrail and summary reporting.
4. Finalize the narration to match the generated artifacts.
5. Run tests, generate outputs, and mark every completed task in this file.
