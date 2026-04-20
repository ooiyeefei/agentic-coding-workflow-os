# Contract: atelier.rungraph Public API

## Tree Operations

- `create_run(issue_ref: str) -> str`
- `create_stage(run_id: str, stage_name: str) -> str`
- `mark_stage_complete(run_id: str, stage_id: str) -> None`
- `list_runs() -> list[str]`
- `list_stages(run_id: str) -> list[str]`

**Contract**:

- `create_run(...)` creates `.atelier/runs/<run_id>/` and materializes `run.md`, `audit.jsonl`, `stages/`, and `.lock`.
- `create_stage(...)` appends the next ordered stage under `.atelier/runs/<run_id>/stages/` using the `<nnn>-<slug>` format.
- Each created stage contains `stage.md`, `packet.md`, `transcript.jsonl`, `evidence.md`, `evidence.json`, `decisions/`, and `findings/`.
- `mark_stage_complete(...)` creates the stage's `.complete` marker without renaming the stage or mutating other stage identifiers.
- `list_runs()` and `list_stages(run_id)` return lexicographically sorted identifiers.

## Resume Cursor

- `next_stage_to_execute(run_id: str) -> str | None`

**Contract**:

- Scans stage identifiers in execution order.
- Returns the first stage missing `.complete`.
- Returns `None` only when every stage has `.complete`.

## Run Lock

- `run_lock(run_id: str)`

**Contract**:

- Acquires an exclusive blocking lock on `.atelier/runs/<run_id>/.lock`.
- Prevents a second concurrent writer from entering until the first lock holder exits the context.
- Allows reacquisition after holder termination because the operating system releases the abandoned lock.
