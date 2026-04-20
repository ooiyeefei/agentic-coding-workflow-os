# Feature Specification: Run Graph Tree Ops

**Feature Branch**: `005-rungraph-tree-ops`  
**Created**: 2026-04-20  
**Status**: Draft  
**Input**: User description: "Run Graph filesystem ops: create runs/stages, completion markers, resume cursor, concurrent write locks"

## Clarifications

### Session 2026-04-20

- Q: How should stage directories be named? → A: Stage identifiers are sequence-prefixed slugs such as `001-specify`, `002-plan`, and `003-implement`.
- Q: How should resume handle orphaned or partial stages? → A: Any stage without a completion marker is treated as incomplete and is the next stage to restart.
- Q: Where should the run lock live? → A: Each run stores its writer lock at `.atelier/runs/<run_id>/.lock`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create Canonical Run Trees (Priority: P1)

As a workflow engine, I can create a new run and append ordered stages under it, so every execution has a durable filesystem trace that matches Atelier's canonical run graph layout.

**Why this priority**: The run graph is the persistence primitive for every later workflow stage. If runs and stages are not created consistently, resume, review, and evidence collection all collapse.

**Independent Test**: Create one run and three stages, then verify the run directory and each stage directory exist in the canonical `.atelier/runs/<run_id>/...` layout with ordered stage identifiers.

**Acceptance Scenarios**:

1. **Given** no existing run for an execution, **When** `create_run(issue_ref)` is called, **Then** the system creates `.atelier/runs/<run_id>/` with the canonical run-level files and returns a new run identifier.
2. **Given** an existing run, **When** `create_stage(run_id, "specify")`, `create_stage(run_id, "clarify")`, and `create_stage(run_id, "implement")` are called in order, **Then** the system creates `001-specify`, `002-clarify`, and `003-implement` directories under `.atelier/runs/<run_id>/stages/`.
3. **Given** a stage name that contains spaces or punctuation, **When** a stage is created, **Then** the stored stage identifier is a normalized sequence-prefixed slug.

---

### User Story 2 - Resume From The First Incomplete Stage (Priority: P2)

As a workflow engine resuming work after interruption, I can scan a run and identify the first stage that is not complete, so recovery is deterministic and idempotent.

**Why this priority**: Durable resume is the core behavior that makes the run graph useful instead of a passive log directory.

**Independent Test**: Create three stages, mark the first two complete, and verify the resume cursor returns the third stage. Then remove no markers from a partially created stage and verify that same stage is selected again.

**Acceptance Scenarios**:

1. **Given** a run with three ordered stages and only the first two have completion markers, **When** `next_stage_to_execute(run_id)` runs, **Then** it returns the third stage identifier.
2. **Given** a stage directory exists but its completion marker does not, **When** resume scanning runs, **Then** that stage is treated as incomplete even if other files are present inside it.
3. **Given** every stage in a run has a completion marker, **When** `next_stage_to_execute(run_id)` runs, **Then** it returns `None`.

---

### User Story 3 - Serialize Writers With Reclaimable Locks (Priority: P3)

As a concurrent workflow engine, I can acquire a per-run lock before mutating run graph files, so only one writer updates a run at a time and crashed writers do not permanently strand the run.

**Why this priority**: Without serialization, concurrent stage writes can corrupt the durable lineage that the run graph exists to preserve.

**Independent Test**: Hold a run lock in one process, verify a second process blocks until release, then verify a fresh process can reacquire the same lock after the first holder exits unexpectedly.

**Acceptance Scenarios**:

1. **Given** one process already holds `.atelier/runs/<run_id>/.lock`, **When** a second process enters `run_lock(run_id)`, **Then** it blocks until the first process releases the lock.
2. **Given** a lock holder exits or crashes without explicit cleanup, **When** another process attempts to acquire the same run lock later, **Then** the operating system releases the old lock and the new holder acquires it.
3. **Given** code inside `run_lock(run_id)` raises an exception, **When** the context manager exits, **Then** the lock is released so later work can continue.

### Edge Cases

- What happens when `create_stage` is called for a run whose `stages/` directory does not exist yet?
- What happens when a caller requests a stage name that slugifies to an empty value or collides with an existing stage slug?
- What happens when stages already exist out of numeric order and a new stage must pick the next sequence number?
- What happens when a run contains a partially written stage directory with files but no completion marker?
- What happens when a process is terminated while holding the run lock?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST create runs under `.atelier/runs/<run_id>/`, where `<run_id>` is a time-sortable run identifier.
- **FR-002**: `create_run(issue_ref)` MUST create the canonical run-level layout from the roadmap: `run.md`, `audit.jsonl`, and `stages/` inside `.atelier/runs/<run_id>/`.
- **FR-003**: `create_run(issue_ref)` MUST record the caller-provided `issue_ref` in the run metadata so the run can be traced back to its source issue.
- **FR-004**: `create_stage(run_id, stage_name)` MUST create a new stage directory under `.atelier/runs/<run_id>/stages/` using the next three-digit sequence prefix plus a normalized slug, such as `001-specify`.
- **FR-005**: Each created stage MUST include the canonical stage layout from the roadmap: `stage.md`, `packet.md`, `transcript.jsonl`, `evidence.md`, `evidence.json`, `decisions/`, and `findings/`.
- **FR-006**: `mark_stage_complete(run_id, stage_id)` MUST write a durable completion marker inside the target stage directory without mutating the stage identifier.
- **FR-007**: `list_runs()` MUST return existing runs in lexicographic order so newer time-sortable run identifiers appear after older ones.
- **FR-008**: `list_stages(run_id)` MUST return stage identifiers in execution order.
- **FR-009**: `next_stage_to_execute(run_id)` MUST scan stages in order and return the first stage that does not have a completion marker.
- **FR-010**: Resume scanning MUST treat any stage that lacks a completion marker as incomplete, even if the stage contains other files from a prior partial attempt.
- **FR-011**: `run_lock(run_id)` MUST acquire an exclusive lock using a file stored at `.atelier/runs/<run_id>/.lock`.
- **FR-012**: While one process holds `run_lock(run_id)`, a second process attempting the same lock MUST block instead of acquiring concurrent write access.
- **FR-013**: The lock implementation MUST rely on operating-system-backed file locking so a crashed holder does not leave an unreclaimable stale lock.
- **FR-014**: The run graph implementation MUST preserve the roadmap's `Storage Philosophy` layout exactly for the run and stage files it creates.
- **FR-015**: `tests/test_rungraph.py` MUST cover run creation, ordered stage creation, completion markers, resume selection, dual-lock blocking, and post-crash lock reacquisition.

### Key Entities *(include if feature involves data)*

- **Run**: A durable execution root stored under `.atelier/runs/<run_id>/` with metadata, audit log, stage directories, and a per-run writer lock.
- **Stage**: An ordered execution step stored under `.atelier/runs/<run_id>/stages/<nnn-stage-name>/` with packet, transcript, evidence, and decision/finding subdirectories.
- **Completion Marker**: A file inside a stage directory that indicates the stage completed successfully and should be skipped on resume.
- **Run Lock**: The operating-system-backed lock file stored at `.atelier/runs/<run_id>/.lock` that serializes writers for one run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Creating one run and three stages yields a `.atelier/runs/<run_id>/` tree whose run- and stage-level files match the roadmap's canonical storage layout.
- **SC-002**: After marking only the first two of three created stages complete, `next_stage_to_execute(run_id)` returns the third stage identifier.
- **SC-003**: When a stage directory exists without a completion marker, resume logic selects that stage instead of skipping past it.
- **SC-004**: A second process attempting the same run lock remains blocked until the first lock holder releases it.
- **SC-005**: After a lock-holding process exits unexpectedly, another process can acquire the same run lock without manual stale-lock cleanup.
- **SC-006**: `tests/test_rungraph.py` passes locally and demonstrates both resume correctness and lock serialization behavior.

## Assumptions

- Run identifiers continue to use the project's existing time-sortable ID helpers.
- The roadmap's canonical `.atelier/runs/<run_id>/stages/<nnn-stage-name>/` structure is the source of truth when shorthand issue text omits the `.atelier/` prefix.
- Hidden operational files needed for correctness, such as `.lock` and the chosen completion marker, are allowed in addition to the canonical roadmap files.
- This feature only needs filesystem operations and process-local locking; higher-level workflow orchestration remains out of scope.
