# Research: Atelier CLI

## Decision 1: Use Click instead of Typer

- **Decision**: Implement the CLI with `click`.
- **Rationale**: The W15 clarification explicitly prefers Click for stability and explicit command wiring. The existing scaffold already uses Click, so staying there avoids churn and keeps help, groups, and prompts predictable.
- **Alternatives considered**:
  - Typer: rejected because it adds extra magic without solving a Phase 0 problem.
  - Custom `argparse`: rejected because it would replace an already-installed dependency and add avoidable boilerplate.

## Decision 2: Treat `atelier run` as "create and surface the stored run"

- **Decision**: `atelier run --issue <ref>` creates a run and returns the stored run snapshot immediately; `atelier run resume <run_id>` only advances state where the persisted workflow already allows a safe approval transition.
- **Rationale**: The current workflow engine exposes `start()` and `resume()`, but the production execution backends for real persona/reviewer/evidence execution are not wired through the CLI yet. Returning the stored run snapshot is truthful and still useful.
- **Alternatives considered**:
  - Drive the workflow immediately to the next wait/terminal state: rejected because it would promise more execution plumbing than the repo currently exposes through the CLI.
  - Advance exactly one stage per invocation: rejected because it exposes engine mechanics instead of a user-friendly task flow.

## Decision 3: Use human-readable output by default and `--json` on structured commands

- **Decision**: Keep human-readable output as the default, and add `--json` to commands that report structured state: `init`, `run`, `run resume`, `run list`, `run show`, `cleanup`, `daemon`, and `grep`.
- **Rationale**: The issue brief calls out power-user UX and CI scriptability. Human output supports demos and interactive use; `--json` keeps the same commands usable in automation without introducing a second API surface.
- **Alternatives considered**:
  - JSON by default: rejected because it makes everyday CLI use and demos harder to scan.
  - Separate `json-*` commands: rejected because it duplicates the command surface and fractures documentation.

## Decision 4: Keep repo targeting explicit

- **Decision**: Repo-scoped commands accept `--repo PATH` where the command surface makes sense and resolve `.atelier/` relative to that repository.
- **Rationale**: The acceptance example already uses `atelier run --issue 42 --repo .`, and the current codebase stores state in repo-relative paths. Explicit repo targeting works cleanly in scripts.
- **Alternatives considered**:
  - Hidden reliance on the current working directory only: rejected because it makes automation and multi-repo use awkward.
  - A complicated global repo context shared across every subcommand: rejected because the actual W15 surface stays simpler with explicit per-command options.

## Decision 5: Make initialization idempotent and cleanup confirmation-safe

- **Decision**: `atelier init` creates missing `.atelier/` directories without overwriting existing user state, while `atelier cleanup` requires either an interactive confirmation prompt or `--yes`.
- **Rationale**: The project principles require filesystem-first state and human-in-the-loop destructive gates. Idempotent init prevents unnecessary prompts, while cleanup must be conservative because it removes worktrees.
- **Alternatives considered**:
  - Make `init` fail when `.atelier/` already exists: rejected because it turns a safe bootstrap command into a nuisance.
  - Add an unimplemented `--dry-run` mode only because the roadmap mentions it: rejected for W15 because the shipped CLI should describe only behavior that actually exists.

## Decision 6: Manage daemon lifecycle through truthful placeholder state

- **Decision**: `atelier daemon start|stop|status` manages repository-scoped placeholder state instead of inventing a real HTTP listener or PID-based supervisor.
- **Rationale**: W15 needs a stable operational CLI surface before W16 fills in the HTTP server details. Truthful placeholder state is safer than pretending the daemon already exists.
- **Alternatives considered**:
  - Make daemon commands no-ops until W16: rejected because it leaves the CLI contract undefined.
  - Fake a process-backed supervisor: rejected because the repo does not yet implement a real daemon runtime surface to supervise.

## Decision 7: Implement `grep` in Python over `.atelier/` text artifacts

- **Decision**: `atelier grep <pattern>` searches repo-local `.atelier/` text artifacts in Python instead of shelling out to an external grep tool.
- **Rationale**: Python-based search keeps the command portable, makes JSON output straightforward, and aligns with the filesystem-first design.
- **Alternatives considered**:
  - Shell out to `rg`: rejected because it adds an external runtime dependency and makes structured output harder to control.
  - Restrict search to audit logs only: rejected because users also need to inspect `run.md`, workflow state, and other text artifacts.
