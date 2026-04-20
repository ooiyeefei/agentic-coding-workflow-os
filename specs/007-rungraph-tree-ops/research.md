# Research: Run Graph Tree Ops

## Decision 1: Store run graph state under `.atelier/runs/` and create the full canonical tree eagerly

- **Decision**: Create runs and stages directly under `.atelier/runs/<run_id>/` and materialize the roadmap's canonical files and directories at creation time.
- **Rationale**: The roadmap defines the filesystem tree as the durable schema. Creating the full skeleton up front makes later stages idempotent, keeps resume logic simple, and gives downstream features predictable file locations.
- **Alternatives considered**:
  - Create only the minimal files needed for this issue: rejected because it would drift from the roadmap's stated canonical layout and force later features to backfill structure inconsistently.
  - Store run graph state outside `.atelier/`: rejected because the roadmap's storage philosophy is explicit that `.atelier/` is the source of truth.

## Decision 2: Use sequence-prefixed slug directories as stage identifiers

- **Decision**: Treat the stage identifier returned by `create_stage(...)` as the on-disk stage directory name, formatted as `<nnn>-<slug>`.
- **Rationale**: The clarified requirement explicitly calls for names like `001-specify`, and lexicographic ordering then matches execution order without extra metadata.
- **Alternatives considered**:
  - Generate separate ULID-based stage identifiers: rejected because it conflicts with the requested stage naming convention and would complicate resume ordering.
  - Let callers supply the full numeric prefix: rejected because sequence assignment belongs in the run graph layer and must stay canonical.

## Decision 3: Use a hidden `.complete` marker for stage completion

- **Decision**: Mark a completed stage by writing a hidden `.complete` file inside the stage directory.
- **Rationale**: A hidden marker avoids colliding with the canonical roadmap files while keeping completion checks cheap and explicit.
- **Alternatives considered**:
  - Encode completion inside `stage.md`: rejected because resume would then need content parsing instead of a simple file existence check.
  - Use a directory rename to signal completion: rejected because renaming stage directories would break stable stage identifiers.

## Decision 4: Treat any stage without `.complete` as incomplete, even if other files exist

- **Decision**: Resume scanning returns the first ordered stage missing its `.complete` marker and does not try to infer partial progress from packet, transcript, or evidence files.
- **Rationale**: The user explicitly clarified that orphaned partial stages should restart. A single completion signal is easier to reason about than file-by-file heuristics.
- **Alternatives considered**:
  - Attempt partial recovery based on which stage files exist: rejected because it would introduce ambiguous state and hidden coupling to later workflow stages.
  - Delete incomplete stage directories automatically: rejected because it would destroy potentially useful evidence from an interrupted run.

## Decision 5: Use `fcntl.flock` on `.lock` for writer serialization

- **Decision**: Implement `run_lock(run_id)` with `fcntl.flock` on `.atelier/runs/<run_id>/.lock`.
- **Rationale**: `fcntl` is in the Python standard library on the target Unix-like platforms, provides kernel-managed blocking semantics, and automatically releases locks when the holding process exits.
- **Alternatives considered**:
  - Add `portalocker`: rejected because the issue explicitly allows `fcntl`, and avoiding a new dependency keeps the change smaller.
  - Use a purely advisory PID file without kernel locks: rejected because stale lock recovery after crashes would be harder and less reliable.
