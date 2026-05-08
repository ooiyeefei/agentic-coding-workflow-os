# Data Model: ULID Path Helpers

## PrefixedEntityId

- **Purpose**: Represents a run graph identifier that combines an entity prefix with a ULID body.
- **Fields**:
  - `prefix`: One of `run`, `stage`, `packet`, `action`, `evidence`, `decision`
  - `ulid`: A valid ULID string
  - `value`: Canonical serialized form `<prefix>_<ulid>`
- **Validation rules**:
  - Prefix must match the expected entity set.
  - Separator is always a single underscore.
  - ULID portion must be syntactically valid.

## StageLocator

- **Purpose**: Identifies the human-readable stage directory within a run.
- **Fields**:
  - `run_id`: A valid `run_*` identifier
  - `stage_seq`: Positive integer rendered as three digits
  - `stage_name`: Caller-supplied stage label normalized into a filesystem-safe slug
  - `directory_name`: Canonical `NNN-slug` representation
- **Validation rules**:
  - `stage_seq` must be `>= 1`
  - `stage_name` must contain at least one alphanumeric character after normalization

## RunGraphArtifactPath

- **Purpose**: Represents a canonical filesystem location underneath `.spanweave/runs/<run_id>/`.
- **Variants**:
  - Run directory
  - Stage directory
  - Packet file
  - Evidence markdown file
  - Evidence JSON file
  - Transcript JSONL file
  - Audit log JSONL file
- **Validation rules**:
  - All returned locations are `Path` objects
  - Stage-scoped artifacts must live under the normalized stage directory
  - Run-scoped audit logs live directly beneath the run directory

## AtomicWriteOperation

- **Purpose**: Captures the safe replacement lifecycle for a destination file.
- **Fields**:
  - `destination`: Final output path
  - `temporary_path`: Sibling temporary file path in the same directory
  - `content`: Text or bytes payload to write
- **State transitions**:
  - `prepared` → destination directory exists
  - `written` → temporary file contains complete payload
  - `replaced` → temporary file becomes destination
  - `failed` → final replacement did not occur; destination content remains unchanged
