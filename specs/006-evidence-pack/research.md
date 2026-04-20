# Research: Evidence Pack

## Decision 1: Fix the JSON contract with `schema_version: "1.0"`

- **Decision**: Treat `schema_version` as a required literal field with the fixed value `"1.0"`.
- **Rationale**: The Evidence Pack is intended to become an open, machine-consumable format. A required version field gives future consumers an explicit compatibility gate instead of relying on implicit field shape detection.
- **Alternatives considered**:
  - Omit a version field: rejected because forward compatibility becomes guesswork.
  - Allow arbitrary semantic versions immediately: rejected because the first implementation only needs one stable schema version.

## Decision 2: Link execution evidence to findings by `finding_id`

- **Decision**: Add a stable `finding_id` to each finding and store related `finding_ids` on each command output record.
- **Rationale**: One command can support multiple findings and one finding can be supported by multiple commands over time. A list-based reference model preserves those relationships cleanly in JSON and Markdown without forcing consumers to scrape prose.
- **Alternatives considered**:
  - Store only positional indexes: rejected because ordering changes would break references.
  - Embed command output directly inside each finding: rejected because shared execution evidence would be duplicated.

## Decision 3: Validate `run_id` with existing helpers and constrain `stage_id` to canonical stage labels

- **Decision**: Reuse existing run-id validation through `atelier.util.run_dir(...)` and accept only safe stage directory labels like `001-review`.
- **Rationale**: The repo already established the run-id contract and run-tree location. Matching that contract keeps W08 aligned with W03/W09 instead of inventing a second path scheme.
- **Alternatives considered**:
  - Accept any string for `stage_id`: rejected because path traversal and inconsistent stage naming would leak into persisted artifacts.

## Decision 4: Write both files as one logical transaction with rollback

- **Decision**: Stage both output files in the destination directory, then replace destinations with rollback support if the second replace fails.
- **Rationale**: Atomic single-file writes are not enough here; an Evidence Pack is incomplete if JSON and Markdown disagree. Best-effort rollback keeps the stage directory coherent.
- **Alternatives considered**:
  - Call single-file atomic writes twice: rejected because a mid-write failure can leave mismatched artifacts.
  - Rename the entire stage directory: rejected because the stage may already contain other files that should remain untouched.

## Decision 5: Apply local redaction to execution output now

- **Decision**: Redact obvious secrets in execution stdout and stderr during generation before rendering or JSON serialization.
- **Rationale**: The generator is the last point before persistence, so it is the safest place to guarantee no secret-bearing output lands on disk. W10 can later centralize or expand the rules without changing the Evidence Pack contract.
- **Alternatives considered**:
  - Leave redaction entirely for W10: rejected because the W08 acceptance criteria already require redacted evidence output.
