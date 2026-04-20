# Tasks: Evidence Pack

**Input**: Design documents from `/specs/006-evidence-pack/`  
**Prerequisites**: plan.md, research.md, data-model.md, contracts/evidence-pack.md, quickstart.md

## Phase 1: Setup

- [x] T001 Create the Evidence Pack feature documentation set in `specs/006-evidence-pack/`

## Phase 2: Foundational

- [x] T002 Define the Evidence Pack schema contract in `atelier/evidence/schema.py`
- [x] T003 Export the public evidence API from `atelier/evidence/__init__.py`

## Phase 3: User Story 1 - Write Replayable Evidence Files (Priority: P1)

**Goal**: Persist one Evidence Pack as both JSON and Markdown under the canonical stage directory.

**Independent Test**: `generate(...)` creates both files under `.atelier/runs/<run_id>/stages/<stage_id>/` and preserves coherent outputs when replacing existing artifacts.

- [x] T004 [US1] Implement path validation, redacted rendering, and transactional dual-file writes in `atelier/evidence/generator.py`

## Phase 4: User Story 2 - Preserve a Stable Machine Schema (Priority: P2)

**Goal**: Expose a machine-validated JSON contract with explicit versioning and finding-to-execution linkage.

**Independent Test**: Serialize and parse an `EvidencePack` fixture and confirm equivalence.

- [x] T005 [US2] Add schema versioning, finding linkage, audit ULID validation, and confidence bounds in `atelier/evidence/schema.py`

## Phase 5: User Story 3 - Render Dense Human Markdown (Priority: P3)

**Goal**: Render human-readable Markdown suitable for terminals, PRs, and demo screenshots.

**Independent Test**: Compare rendered Markdown for a fixed fixture to a checked-in golden file.

- [x] T006 [US3] Create the Jinja2 Markdown template in `atelier/evidence/templates/evidence.md.j2`
- [x] T007 [P] [US3] Add golden Markdown output in `tests/golden/evidence.md`
- [x] T008 [US3] Add round-trip and rendering verification in `tests/test_evidence.py`

## Final Phase: Polish & Cross-Cutting Concerns

- [x] T009 Validate the implementation with `pytest tests/test_evidence.py -v` and `ruff check atelier/evidence tests/test_evidence.py`

## Dependencies

- `T002` depends on `T001`
- `T003` depends on `T002`
- `T004` depends on `T002`
- `T005` depends on `T002`
- `T006` depends on `T002`
- `T007` depends on `T006`
- `T008` depends on `T004`, `T005`, and `T006`
- `T009` depends on `T003` through `T008`

## Parallel Example

- After `T006`, `T007` can be prepared in parallel with `T008` because the golden file content is derived from the fixed fixture shape.

## Implementation Strategy

- Land the schema first so both JSON and Markdown rendering use one validated source of truth.
- Implement transactional file generation before adding tests so replacement semantics are covered by the final verification pass.
- Freeze fixture inputs for the Markdown golden test to keep the rendered artifact stable across runs.
