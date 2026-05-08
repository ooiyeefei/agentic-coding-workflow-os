# Contract: spanweave.util Public API

## ULID Helpers

- `new_run_id() -> str`
- `new_stage_id() -> str`
- `new_packet_id() -> str`
- `new_action_id() -> str`
- `new_evidence_id() -> str`
- `new_decision_id() -> str`

**Contract**:

- Each function returns a string in the form `<prefix>_<ulid>`.
- The returned ULID suffix is valid and lex-sortable by creation time.
- Prefixes are fixed per function and never configurable at call time.

## Path Helpers

- `run_dir(run_id) -> Path`
- `stage_dir(run_id, stage_seq, stage_name) -> Path`
- `packet_path(run_id, stage_seq, stage_name) -> Path`
- `evidence_md_path(run_id, stage_seq, stage_name) -> Path`
- `evidence_json_path(run_id, stage_seq, stage_name) -> Path`
- `transcript_path(run_id, stage_seq, stage_name) -> Path`
- `audit_log_path(run_id) -> Path`

**Contract**:

- Every function returns a `pathlib.Path`.
- Invalid IDs, invalid stage sequences, and invalid stage names raise validation errors.
- Stage-scoped paths resolve underneath `.spanweave/runs/<run_id>/stages/<NNN-slug>/`.
- The audit log path resolves to `.spanweave/runs/<run_id>/audit.jsonl`.

## Filesystem Helpers

- `safe_mkdir(path) -> Path`
- `atomic_write(path, content) -> Path`

**Contract**:

- `safe_mkdir` creates the directory if needed and succeeds when called repeatedly.
- `atomic_write` writes to a temporary sibling file and atomically replaces the destination in the final step.
- If the final replacement step fails, existing destination content remains unchanged.
- `atomic_write` guarantees atomic replacement semantics for the destination path but does not promise universal power-loss durability across all platforms or filesystems.
