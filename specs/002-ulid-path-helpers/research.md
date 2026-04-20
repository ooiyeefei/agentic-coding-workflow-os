# Research: ULID Path Helpers

## Decision 1: Use `python-ulid` as the sole ULID source

- **Decision**: Wrap the existing `python-ulid` dependency instead of hand-rolling ULID generation.
- **Rationale**: The dependency is already declared in `pyproject.toml`, and using a single upstream generator reduces collision and ordering risk in a foundational module.
- **Alternatives considered**:
  - Manual ULID implementation: rejected because it would duplicate a solved problem and enlarge the maintenance surface.
  - UUID-based IDs with separate timestamps: rejected because the run graph specifically relies on lex-sortable identifiers.

## Decision 2: Standardize on underscore-prefixed entity IDs

- **Decision**: Generate IDs in the form `<entity>_<ulid>`, such as `run_01HX...` and `stage_01HX...`.
- **Rationale**: The prompt explicitly prefers underscores, and the separator keeps the entity prefix easy to parse without affecting the sortable ULID suffix.
- **Alternatives considered**:
  - Hyphen separators: rejected because the feature clarification explicitly preferred underscores.
  - Bare ULIDs without prefixes: rejected because downstream readers need self-describing identifiers.

## Decision 3: Build paths with `pathlib.Path` plus validation at the boundary

- **Decision**: Return `Path` objects for all run graph locations and validate IDs, stage sequences, and stage names before constructing paths.
- **Rationale**: `Path` provides platform-correct separators automatically, and boundary validation prevents malformed run graph layouts from leaking into later modules.
- **Alternatives considered**:
  - Raw string concatenation: rejected because it is brittle across operating systems and easier to misuse.
  - Validation only in callers: rejected because a foundational helper should defend its own contract.

## Decision 4: Normalize stage directory names to `NNN-slug`

- **Decision**: Render stage directories as a zero-padded three-digit sequence followed by a normalized lowercase slug.
- **Rationale**: The roadmap example uses `001-specify`, and zero-padded sequence prefixes keep stage directories naturally ordered in file listings.
- **Alternatives considered**:
  - Preserve original stage names verbatim: rejected because spaces and punctuation can produce unstable paths.
  - Use only stage IDs for directories: rejected because human-readable stage names are valuable during inspection.

## Decision 5: Implement atomic replacement with a temporary sibling file and a final replace

- **Decision**: Write content to a uniquely named temporary file in the destination directory, then replace the destination in the final step.
- **Rationale**: Same-directory replacement preserves atomic replacement semantics on the common local filesystems this repository targets, and the failure-mode test directly maps to this flow.
- **Alternatives considered**:
  - Write directly to the destination: rejected because a crash can leave partial content.
  - Temporary files in another directory: rejected because cross-filesystem moves break atomic replacement guarantees.
  - Universal power-loss durability claims: rejected because filesystem and platform guarantees vary beyond this feature's scope.
