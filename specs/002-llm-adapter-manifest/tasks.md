# Tasks: LLM Adapter Manifest

**Input**: Design documents from `/specs/002-llm-adapter-manifest/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/llm-adapter.md  
**Tests**: Tests are required for this feature because the acceptance criteria explicitly require mocked adapter tests and capability-routing assertions.  
**Organization**: Tasks are grouped by user story so routing, adapter normalization, and shipped defaults remain independently traceable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the feature artifacts and defaults directory layout

- [X] T001 Create the spec-driven feature artifacts in specs/002-llm-adapter-manifest/
- [X] T002 Create the default model manifest directory in .atelier/defaults/models/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define the shared contract and manifest models used by every provider adapter

- [X] T003 Create normalized adapter input and output models in atelier/llm/adapter.py
- [X] T004 Create capability models, loaders, and routing logic in atelier/llm/capabilities.py
- [X] T005 Update atelier/llm/__init__.py exports to expose the new adapter surface

**Checkpoint**: Shared abstractions are in place and provider implementations can target a stable contract.

---

## Phase 3: User Story 1 - Route Personas To Compatible Models (Priority: P1) 🎯 MVP

**Goal**: Match persona requirements against declarative manifests without hardcoded model strings

**Independent Test**: Build manifests in memory, route a compatible requirement successfully, and raise `UnsupportedCapabilityError` for an incompatible requirement.

### Tests for User Story 1

- [X] T006 [P] [US1] Add capability match success and failure tests in tests/test_llm_adapter.py

### Implementation for User Story 1

- [X] T007 [US1] Implement `UnsupportedCapabilityError` and manifest matching helpers in atelier/llm/capabilities.py
- [X] T008 [US1] Add shipped manifest YAML files in .atelier/defaults/models/

**Checkpoint**: Capability routing is deterministic and validated by tests.

---

## Phase 4: User Story 2 - Generate Normalized Responses Across Providers (Priority: P2)

**Goal**: Return one response shape from Anthropic and OpenAI adapters

**Independent Test**: Mock both SDK clients, call `generate(...)`, and confirm provider responses normalize to the same response fields.

### Tests for User Story 2

- [X] T009 [P] [US2] Add mocked Anthropic adapter tests in tests/test_llm_adapter.py
- [X] T010 [P] [US2] Add mocked OpenAI adapter tests in tests/test_llm_adapter.py

### Implementation for User Story 2

- [X] T011 [US2] Implement the Anthropic adapter in atelier/llm/anthropic.py
- [X] T012 [US2] Implement the OpenAI adapter in atelier/llm/openai.py
- [X] T013 [US2] Add shared response-cost construction helpers in atelier/llm/adapter.py

**Checkpoint**: Both providers honor the same abstraction contract and return normalized usage and cost data.

---

## Phase 5: User Story 3 - Ship Default Model Manifests For Phase 0 (Priority: P3)

**Goal**: Keep provider model identifiers and pricing in declarative defaults

**Independent Test**: Load the shipped YAML files and confirm adapters use manifest-provided model ids and pricing.

### Tests for User Story 3

- [X] T014 [P] [US3] Add manifest loader and per-call cost assertions in tests/test_llm_adapter.py

### Implementation for User Story 3

- [X] T015 [US3] Wire manifest pricing into normalized response cost fields in atelier/llm/adapter.py, atelier/llm/anthropic.py, and atelier/llm/openai.py
- [X] T016 [US3] Validate the shipped manifest files through loader coverage in atelier/llm/capabilities.py and tests/test_llm_adapter.py

**Checkpoint**: Default manifests are first-class inputs to routing and cost accounting.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [X] T017 Run the focused pytest suite for tests/test_llm_adapter.py
- [X] T018 Verify source files outside .atelier/defaults/models/ do not embed default provider model ids for this feature

---

## Dependencies & Execution Order

- Setup must complete before foundational work.
- Foundational work blocks all user stories.
- User Story 1 must complete before User Stories 2 and 3 because the adapters depend on the shared capability contract.
- User Story 2 and User Story 3 can proceed after the foundational phase, but final validation should happen after both are complete.
- Polish happens last.

## Parallel Opportunities

- `T006`, `T009`, `T010`, and `T014` can be written before implementation to preserve a test-first loop.
- `T011` and `T012` touch different provider adapter files and can proceed in parallel once the shared contract exists.
- YAML manifest authoring in `T008` can happen in parallel with adapter implementation after the capability schema is finalized.

## Implementation Strategy

1. Define the shared contract and capability matcher first.
2. Prove routing behavior with unit tests before wiring providers.
3. Implement the Anthropic and OpenAI adapters against the shared contract.
4. Add default manifests and cost-accounting assertions.
5. Finish by running the focused pytest suite and checking for hardcoded model ids.
