# Feature Specification: Atelier CLI

**Feature Branch**: `013-atelier-cli`  
**Created**: 2026-04-22  
**Status**: Implemented  
**Input**: User description: "Atelier CLI issue: init, run, resume, show, list, cleanup, daemon, and grep commands; prefer click, default to human output with --json, and require confirmation for destructive operations."

## Clarifications

### Session 2026-04-22

- Q: Which CLI framework should Phase 0 use? → A: Use `click` for stability and explicit command wiring.
- Q: What output format should the CLI prefer? → A: Human-readable output is the default, with `--json` for structured machine consumption.
- Q: How should destructive operations behave? → A: Destructive commands must require explicit confirmation.
- Q: How should daemon lifecycle work before W16? → A: The CLI must expose truthful placeholder state instead of pretending the HTTP daemon already exists.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start And Inspect Runs (Priority: P1)

As a power user, I can initialize Atelier in a repository, start a run from an issue reference, and inspect or approve stored run state from the CLI, so the CLI is the primary way to operate Atelier without reaching into Python internals.

**Why this priority**: The CLI is the real product surface. If a user still needs library calls to bootstrap a repo or inspect a run, the product promise is not met.

**Independent Test**: In a temporary repository, run `atelier init`, then `atelier run --issue 42 --repo .`, and finally `atelier run show <run_id> --repo .` or `atelier run resume <run_id> --approve --repo .` on a paused gate. The sequence should create filesystem state, print a run ID, and surface current status and stage information.

**Acceptance Scenarios**:

1. **Given** a repository without `.atelier/`, **When** the user runs `atelier init --repo .`, **Then** the command creates the Phase 0 Atelier directories and reports success without manual file creation.
2. **Given** an initialized repository, **When** the user runs `atelier run --issue 42 --repo .`, **Then** the command creates `.atelier/runs/<run_id>/`, persists workflow state, and prints the run ID plus the current stage.
3. **Given** a repository with runs on disk, **When** the user runs `atelier run list --repo .`, **Then** the CLI prints a human-readable summary that includes run IDs and statuses.
4. **Given** a repository with a paused gate approval, **When** the user runs `atelier run resume <run_id> --approve --repo .`, **Then** the CLI advances the stored workflow state and prints the updated status.

---

### User Story 2 - Search And Inspect Stored Artifacts (Priority: P2)

As a power user or CI script, I can inspect a run's stage tree and grep `.atelier/` artifacts in either human or JSON form, so I can understand current state and evidence without opening files manually.

**Why this priority**: Atelier is only scriptable and demo-friendly if users can inspect run state quickly. Read-only inspection is the next highest-value CLI slice after starting a run.

**Independent Test**: Seed a repository with one or more runs, then verify `atelier run show <run_id>` and `atelier grep <pattern>` work in both human and JSON modes without requiring any live workflow execution.

**Acceptance Scenarios**:

1. **Given** a run with completed and pending stages, **When** the user runs `atelier run show <run_id> --repo .`, **Then** the CLI shows the workflow, current status, created stage progression, and waiting reason when present.
2. **Given** the same repository, **When** the user runs `atelier run show <run_id> --repo . --json`, **Then** the CLI emits parseable JSON describing the run snapshot.
3. **Given** matching text inside `.atelier/` artifacts, **When** the user runs `atelier grep review --repo .`, **Then** the CLI returns matches with enough path and snippet context to locate the evidence.
4. **Given** matching text inside `.atelier/` artifacts, **When** the user runs `atelier grep review --repo . --json`, **Then** the CLI emits parseable JSON for the same matches.

---

### User Story 3 - Clean Up Run Worktrees Safely And Control Daemon State (Priority: P3)

As a user, I can confirm cleanup before removing run worktrees and inspect placeholder daemon state from the same CLI, so destructive or operational actions stay explicit and safe.

**Why this priority**: Cleanup is destructive, and daemon commands must exist before W16 can reuse the syntax. Both are important, but they depend on the run surface existing first.

**Independent Test**: Create a fake run-scoped worktree, run `atelier cleanup <run_id>` with and without confirmation, and verify `atelier daemon start|status|stop` report consistent placeholder state.

**Acceptance Scenarios**:

1. **Given** a run-scoped worktree exists, **When** the user runs `atelier cleanup <run_id> --repo .` and declines confirmation, **Then** the CLI exits without removing anything.
2. **Given** a run-scoped worktree exists, **When** the user runs `atelier cleanup <run_id> --repo . --yes`, **Then** the CLI removes only that run's worktree and reports the removed path or paths.
3. **Given** no real HTTP daemon exists yet, **When** the user runs `atelier daemon start --repo .`, `atelier daemon status --repo . --json`, and `atelier daemon stop --repo .`, **Then** the CLI reports truthful placeholder running/stopped state.

### Edge Cases

- Running `atelier init` in a repository that already contains `.atelier/` should be idempotent and must not overwrite user workflows or audit data.
- `atelier run`, `atelier run resume`, `atelier run show`, and `atelier cleanup` should return clear non-zero errors for invalid or nonexistent runs instead of Python tracebacks.
- `atelier run list` and `atelier grep` should succeed with empty results when a repository has no runs or no matches.
- `atelier grep` should skip unreadable or non-text artifacts rather than failing the whole search.
- `atelier cleanup` should report "nothing to remove" when no run worktree exists and must never touch unrelated worktrees.
- `atelier daemon status` should report `stopped` when no placeholder state file exists.
- Commands that support `--json` should emit JSON only, with no extra human prose mixed into stdout.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a Click-based root command in `atelier/cli/main.py` with top-level commands `init`, `run`, `cleanup`, `daemon`, and `grep`.
- **FR-002**: The system MUST provide substantive help text for the root command and for each subcommand, including `run resume`, `run list`, `run show`, and `daemon start|stop|status`.
- **FR-003**: `atelier init` MUST create missing repo-local directories `.atelier/`, `.atelier/runs/`, `.atelier/audit/`, `.atelier/daemon/`, `.atelier/memory/...`, and `.atelier/workflows/`, and MUST succeed idempotently when they already exist.
- **FR-004**: `atelier run --issue <ref> --repo <path>` MUST resolve the target repository, create a new run, and persist run artifacts under `.atelier/runs/<run_id>/`.
- **FR-005**: `atelier run` MUST print the created `run_id`, workflow name, and current stage.
- **FR-006**: `atelier run resume <run_id>` MUST inspect persisted run state, and `--approve` MUST be the explicit mechanism for resuming across completed gate waits.
- **FR-007**: `atelier run list` MUST derive its output from persisted run directories and workflow state files rather than in-memory process state.
- **FR-008**: `atelier run show <run_id>` MUST present the workflow name, issue reference, run status, created stage progression, and waiting reason when present.
- **FR-009**: `atelier grep <pattern>` MUST search repo-local `.atelier/` text artifacts and return file, line, and snippet context.
- **FR-010**: Commands that return structured data (`init`, `run`, `run resume`, `run list`, `run show`, `cleanup`, `daemon`, and `grep`) MUST support `--json` and emit parseable machine-readable output.
- **FR-011**: Human-readable output MUST remain the default for interactive use and demos.
- **FR-012**: `atelier cleanup <run_id>` MUST require explicit confirmation before live deletion unless the operator passes `--yes`.
- **FR-013**: `atelier cleanup <run_id>` MUST remove only worktrees associated with the specified run and MUST never delete unrelated worktrees.
- **FR-014**: `atelier daemon start|stop|status` MUST manage truthful placeholder daemon lifecycle state that W16 can reuse without changing command syntax.
- **FR-015**: Read-only commands and `--help` invocations MUST avoid importing heavy runtime dependencies unless the selected command actually needs them.
- **FR-016**: `init`, `run`, `cleanup`, `daemon`, and `grep` MUST accept `--repo` so users can target repositories other than the current working directory.
- **FR-017**: `tests/test_cli.py` MUST cover help text, repository initialization, run start/resume, list/show JSON output, grep search results, cleanup confirmation, and daemon lifecycle status.

### Key Entities *(include if feature involves data)*

- **Run Snapshot**: The persisted run summary used by `run`, `run resume`, `run list`, and `run show`, including run ID, issue reference, workflow name, status, created stage list, and waiting state.
- **Stage Entry**: A created stage directory rendered with CLI-facing completion or current status.
- **Workspace Scaffold**: The created and pre-existing Atelier paths reported back to the user after `atelier init`.
- **Grep Match**: A structured search result containing file path, line number, and snippet from a matched `.atelier/` artifact.
- **Daemon Status Record**: The repo-scoped placeholder daemon state reported by `daemon start|stop|status`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `atelier --help` and each top-level command help render without placeholder-only text.
- **SC-002**: Running `atelier init` in a temporary repo creates the expected `.atelier` directories, and a second run completes without destroying existing contents.
- **SC-003**: Running `atelier run --issue 42 --repo .` returns a valid run ID and creates matching files under `.atelier/runs/<run_id>/`.
- **SC-004**: `atelier run list --json` and `atelier run show <run_id> --json` return parseable JSON that includes run ID and status fields.
- **SC-005**: `atelier cleanup <run_id>` cannot delete a worktree without confirmation, and `--yes` removes only the targeted worktree after explicit operator intent.
- **SC-006**: `atelier daemon status` reports consistent stopped/running state across a start → status → stop sequence.
- **SC-007**: `atelier grep <pattern> --json` returns parseable match data without mixing in human-readable output.

## Assumptions

- W11's workflow engine remains the source of truth for creating and resuming run state; the CLI orchestrates it rather than replacing it.
- Phase 0 CLI state remains filesystem-only under a repo-local `.atelier/` directory.
- The default workflow name remains `speckit-loop` unless the user explicitly selects another workflow later.
- W16 will reuse the daemon command syntax and repo-scoped placeholder state introduced by W15 instead of renaming the surface.
- JSON output is required for scripting and verification in Phase 0, but human-readable output remains the primary interactive mode.
