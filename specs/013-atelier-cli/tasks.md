# Tasks: Atelier CLI

**Input**: Design documents from `/specs/013-atelier-cli/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md  
**Tests**: Tests are required for this feature because the acceptance criteria explicitly require command help, JSON output, destructive-safety, and daemon lifecycle coverage.  
**Organization**: Tasks are grouped by user story so repo bootstrap, run control, inspection, cleanup, and daemon lifecycle remain independently traceable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the feature-local documentation and the focused CLI verification surface

- [X] T001 Create the CLI feature documentation set in `specs/013-atelier-cli/`
- [X] T002 Create focused CliRunner coverage in `tests/test_cli.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Replace the placeholder scaffold with the shared CLI structure every command needs

- [X] T003 Update `atelier/cli/main.py` to register the real root command tree and shared CLI context
- [X] T004 [P] Create shared human/JSON rendering helpers in `atelier/cli/formatters.py`
- [X] T005 [P] Create command registration exports in `atelier/cli/commands/__init__.py`

**Checkpoint**: The CLI has a real root group, shared output handling, and a command package ready for implementation.

---

## Phase 3: User Story 1 - Start And Inspect Runs (Priority: P1) 🎯 MVP

**Goal**: Let a user bootstrap repo-local Atelier state and start or resume workflows from the CLI

**Independent Test**: In a temp repo, `atelier init`, `atelier run --issue 42 --repo .`, and `atelier run --repo . resume <run_id> --approve` create and surface persisted run state without direct library calls.

### Tests for User Story 1

- [X] T006 [P] [US1] Add CliRunner coverage for `atelier init`, `atelier run --issue`, and `atelier run resume` in `tests/test_cli.py`

### Implementation for User Story 1

- [X] T007 [US1] Implement repository initialization in `atelier/cli/commands/init.py`
- [X] T008 [US1] Implement workflow start behavior in `atelier/cli/commands/run.py`
- [X] T009 [US1] Implement paused-run resume and `--approve` handling in `atelier/cli/commands/run.py`

**Checkpoint**: A user can initialize a repo, launch a workflow, and continue an existing run from the CLI.

---

## Phase 4: User Story 2 - Inspect Runs And Search Artifacts (Priority: P2)

**Goal**: Let users and scripts inspect persisted run state and search `.atelier/` artifacts

**Independent Test**: With fixture run directories on disk, `atelier run list`, `atelier run show <run_id>`, and `atelier grep <pattern>` work in both human and JSON modes without any live workflow execution.

### Tests for User Story 2

- [X] T010 [P] [US2] Add CliRunner coverage for `atelier run list`, `atelier run show`, and `atelier grep` human/JSON output in `tests/test_cli.py`

### Implementation for User Story 2

- [X] T011 [US2] Implement persisted run summaries in `atelier/cli/commands/list.py`
- [X] T012 [US2] Implement run tree and status rendering in `atelier/cli/commands/show.py`
- [X] T013 [US2] Implement structured `.atelier/` search in `atelier/cli/commands/grep.py`

**Checkpoint**: Run inspection and artifact search work without opening files manually.

---

## Phase 5: User Story 3 - Clean Up Run Worktrees Safely (Priority: P3)

**Goal**: Let users confirm destructive cleanup instead of deleting worktrees blindly

**Independent Test**: Against a fake run worktree, `atelier cleanup <run_id>` refuses unsafe deletion without confirmation, and `atelier cleanup <run_id> --yes` removes only the targeted worktree.

### Tests for User Story 3

- [X] T014 [P] [US3] Add CliRunner coverage for `atelier cleanup` prompt and `--yes` behavior in `tests/test_cli.py`

### Implementation for User Story 3

- [X] T015 [US3] Implement confirmation-aware cleanup flow in `atelier/cli/commands/cleanup.py`
- [X] T016 [US3] Integrate run-scoped worktree removal from `atelier/git/cleanup.py` in `atelier/cli/commands/cleanup.py`

**Checkpoint**: Cleanup is safe by default and only deletes worktrees after explicit user intent.

---

## Phase 6: User Story 4 - Control Daemon Lifecycle From The CLI (Priority: P4)

**Goal**: Provide stable `start`, `stop`, and `status` daemon commands for future non-CLI surfaces

**Independent Test**: `atelier daemon start`, `atelier daemon status`, and `atelier daemon stop` report consistent repo-scoped placeholder state in both human and JSON modes.

### Tests for User Story 4

- [X] T017 [P] [US4] Add CliRunner coverage for `atelier daemon start|stop|status` in `tests/test_cli.py`

### Implementation for User Story 4

- [X] T018 [US4] Implement daemon lifecycle command handling in `atelier/cli/commands/daemon.py`
- [X] T019 [US4] Add repo-scoped placeholder status reporting in `atelier/cli/commands/daemon.py`

**Checkpoint**: The CLI exposes a stable daemon surface that W16 can reuse.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validate help text, lazy imports, and full CLI behavior

- [X] T020 Audit `atelier/cli/main.py` and `atelier/cli/commands/*.py` for help quality, lazy imports, and shared `--json` behavior
- [X] T021 Run `python3 -m pytest tests/test_cli.py -q`
- [X] T022 Run lint on `atelier/cli/` and `tests/test_cli.py`
- [X] T023 Run regression coverage for `tests/test_git.py`, `tests/test_rungraph.py`, `tests/test_workflow.py`, and `tests/test_cli.py`

---

## Dependencies & Execution Order

- Setup must complete before implementation work begins.
- Foundational work blocks every user story because the root command tree, shared context, and formatter behavior are reused everywhere.
- User Story 1 is the MVP and lands first because run creation/resume defines the main CLI value.
- User Story 2 follows the User Story 1 output contract so list/show align with run snapshots.
- User Story 3 depends on the run ID and repo-resolution conventions established in User Story 1.
- User Story 4 can begin after foundational work because it is operationally separate from run execution.
- Polish happens last.

## Parallel Opportunities

- `T004` and `T005` can proceed in parallel once the root command shape is agreed.
- `T006`, `T010`, `T014`, and `T017` can be written early to keep a test-first loop.
- After foundational work, `T011`, `T012`, and `T013` can proceed together because they touch separate command modules.
- `T018` and `T019` can be implemented together once the daemon status contract is fixed.

## Implementation Strategy

1. Replace the placeholder root CLI with the real command tree and shared formatter behavior.
2. Land User Story 1 so Atelier can bootstrap a repo and start workflows from the CLI.
3. Add read-only inspection commands for demos and scripting.
4. Add safety-first cleanup.
5. Finish with daemon lifecycle commands, then validate help text, tests, and destructive safeguards.
