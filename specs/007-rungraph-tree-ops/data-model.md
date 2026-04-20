# Data Model: Run Graph Tree Ops

## RunRecord

- **Purpose**: Represents the root metadata and filesystem location for one workflow run.
- **Fields**:
  - `run_id`: Time-sortable run identifier used as the directory name
  - `issue_ref`: Caller-provided issue or source reference stored in `run.md`
  - `path`: `.atelier/runs/<run_id>/`
  - `lock_path`: `.atelier/runs/<run_id>/.lock`
- **Validation rules**:
  - `run_id` must satisfy the project's existing run ID validation rules.
  - `path` must remain under `.atelier/runs/`.
  - `lock_path` must be colocated with the run directory.

## StageRecord

- **Purpose**: Represents one ordered stage within a run.
- **Fields**:
  - `stage_id`: Sequence-prefixed slug such as `001-specify`
  - `sequence`: Integer execution order derived from the `stage_id` prefix
  - `stage_name`: Caller-supplied human-readable name normalized into the slug suffix
  - `path`: `.atelier/runs/<run_id>/stages/<stage_id>/`
- **Validation rules**:
  - `stage_id` must have a three-digit numeric prefix followed by a non-empty slug.
  - `sequence` must be the next available stage number for the run.
  - `path` must remain under the parent run's `stages/` directory.

## StageLayout

- **Purpose**: Captures the canonical files and directories created for each stage.
- **Fields**:
  - `stage_md`: `stage.md`
  - `packet_md`: `packet.md`
  - `transcript_jsonl`: `transcript.jsonl`
  - `evidence_md`: `evidence.md`
  - `evidence_json`: `evidence.json`
  - `decisions_dir`: `decisions/`
  - `findings_dir`: `findings/`
  - `completion_marker`: `.complete`
- **Validation rules**:
  - All canonical files except `.complete` are created when the stage is created.
  - `.complete` exists only after successful completion is recorded.

## RunLock

- **Purpose**: Represents the exclusive writer lock for a run.
- **Fields**:
  - `path`: `.atelier/runs/<run_id>/.lock`
  - `mode`: Exclusive blocking advisory lock
  - `holder_lifecycle`: Bound to the operating-system file descriptor lifetime
- **Validation rules**:
  - Only one process may hold the lock at a time.
  - A terminated holder must not require manual stale-lock cleanup before reacquisition.
