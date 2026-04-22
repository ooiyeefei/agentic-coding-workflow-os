# Data Model: Atelier CLI

## WorkspaceScaffold

- **Purpose**: Reports what `atelier init` created versus what already existed.
- **Fields**:
  - `repo_root`: repository initialized by the command
  - `atelier_root`: repo-local Atelier directory
  - `created_dirs`: directories created during the invocation
  - `created_files`: files created during the invocation
  - `changed`: whether the invocation created anything
- **Validation rules**:
  - Every reported path must be inside `repo_root`.
  - `created_dirs` and `created_files` must not overlap.

## RunSnapshot

- **Purpose**: Captures the persisted state surfaced by `run`, `run resume`, `run list`, and `run show`.
- **Fields**:
  - `run_id`: run identifier
  - `issue_ref`: user-supplied issue reference
  - `workflow_name`: workflow loaded for the run
  - `status`: current run status
  - `stage_ids`: ordered list of created stage IDs
  - `current_stage_id`: current stage when the run is active or waiting
  - `last_transition`: last transition kind recorded by the workflow engine
  - `waiting_reason`: waiting reason when the run is paused
- **Validation rules**:
  - `run_id` must be a valid Atelier run ID.
  - `status` must match the persisted workflow state enum.
  - `current_stage_id` must appear in `stage_ids` whenever a current stage exists.

## GrepMatch

- **Purpose**: Represents one textual match returned by `atelier grep`.
- **Fields**:
  - `path`: matched artifact path relative to `repo_root`
  - `line_number`: 1-based line number of the match
  - `snippet`: matching line content
- **Validation rules**:
  - `line_number` must be positive.
  - `path` must resolve under the selected repository root.

## CleanupResult

- **Purpose**: Describes the worktrees removed by `atelier cleanup`.
- **Fields**:
  - `run_id`: run whose worktrees are being removed
  - `removed_count`: number of worktrees removed
  - `removed_paths`: removed worktree paths
- **Validation rules**:
  - `removed_paths` must map only to the specified run's worktree naming scheme.
  - Live deletion only happens after explicit confirmation or `--yes`.

## DaemonStatusRecord

- **Purpose**: Captures the repo-scoped placeholder daemon lifecycle state surfaced by `daemon start|stop|status`.
- **Fields**:
  - `repo_root`: repository whose daemon state is being managed
  - `state_file`: path to the daemon placeholder state file
  - `state`: `running` or `stopped`
  - `mode`: always `placeholder` in this slice
  - `updated_at`: last state-change timestamp when present
  - `note`: explanatory text that the real HTTP daemon still belongs to W16
- **Validation rules**:
  - `state` is `running` or `stopped`.
  - `mode` stays `placeholder` until W16 introduces the real daemon runtime.
