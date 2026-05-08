# Tasks: Tool Adapter Layer

**Input**: Design documents from `/specs/015-tool-adapter-layer/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are required for this feature because the acceptance criteria depend on deterministic fixture coverage.

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create the feature documentation set in `specs/015-tool-adapter-layer/`
- [X] T002 Create the adapter package skeleton in `spanweave/adapters/`
- [X] T003 [P] Create fixture directories in `tests/fixtures/adapters/`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T004 Implement manifest schema and loading helpers in `spanweave/adapters/base.py`
- [X] T005 Implement shared transcript normalization and heuristic extraction helpers in `spanweave/adapters/base.py`
- [X] T006 Implement shared run-state and ADR summary helpers for packet formatting in `spanweave/adapters/base.py`

---

## Phase 3: User Story 1 - Ingest Agent Session State Into Typed Memory (Priority: P1)

**Goal**: Convert Claude Code, Codex, and markdown transcripts into typed memory records.

**Independent Test**: Fixture transcripts produce expected `Decision` counts and can be written to `.spanweave/memory/`.

- [X] T007 [P] [US1] Add Claude Code fixture transcript in `tests/fixtures/adapters/claude/projects/sample-project/session.jsonl`
- [X] T008 [P] [US1] Add Codex fixture transcript in `tests/fixtures/adapters/codex/sessions/2026/04/23/rollout-sample.jsonl`
- [X] T009 [P] [US1] Add generic markdown transcript fixture in `tests/fixtures/adapters/generic/transcript.md`
- [X] T010 [US1] Implement Claude Code transcript ingestion in `spanweave/adapters/claude_code.py`
- [X] T011 [US1] Implement Codex transcript ingestion in `spanweave/adapters/codex.py`
- [X] T012 [US1] Implement generic markdown transcript ingestion in `spanweave/adapters/generic.py`
- [X] T013 [US1] Add ingestion and persistence coverage in `tests/test_adapters.py`

---

## Phase 4: User Story 2 - Format Context Packets For The Target Tool (Priority: P2)

**Goal**: Produce tool-native packets from stored memory plus run context.

**Independent Test**: Claude Code and Codex packets include prior decisions, ADRs, and run state while referencing the right tool convention files.

- [X] T014 [P] [US2] Add Claude Code packet formatting in `spanweave/adapters/claude_code.py`
- [X] T015 [P] [US2] Add Codex packet formatting in `spanweave/adapters/codex.py`
- [X] T016 [P] [US2] Add generic packet formatting in `spanweave/adapters/generic.py`
- [X] T017 [US2] Add formatting coverage in `tests/test_adapters.py`

---

## Phase 5: User Story 3 - Detect The Active Tool And Validate Adapter Manifests (Priority: P3)

**Goal**: Detect Claude Code vs Codex and validate shipped manifests.

**Independent Test**: Temporary repositories and env-var combinations distinguish the adapters correctly, and manifest YAML files validate.

- [X] T018 [P] [US3] Add Claude Code manifest in `spanweave/adapters/manifests/claude-code.yaml`
- [X] T019 [P] [US3] Add Codex manifest in `spanweave/adapters/manifests/codex.yaml`
- [X] T020 [US3] Implement detection logic and package exports in `spanweave/adapters/__init__.py`
- [X] T021 [US3] Add detection and manifest validation coverage in `tests/test_adapters.py`

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T022 [P] Update task completion status in `specs/015-tool-adapter-layer/tasks.md`
- [X] T023 Run `pytest tests/test_adapters.py -q`
- [X] T024 Run the relevant broader verification command if the focused tests pass cleanly
