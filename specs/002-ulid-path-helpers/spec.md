# Feature Specification: ULID Path Helpers

**Feature Branch**: `002-ulid-path-helpers`  
**Created**: 2026-04-20  
**Status**: Draft  
**Input**: User description: "ULID-prefixed ID generators, validated Spanweave filesystem path constructors, atomic write helpers"

## Clarifications

### Session 2026-04-20

- Q: What separator should prefixed entity identifiers use? → A: Use underscore-prefixed IDs such as `run_<ulid>` and `stage_<ulid>`.
- Q: How should filesystem paths remain portable across operating systems? → A: Return `pathlib.Path` objects throughout and avoid manual slash-delimited string concatenation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate Sortable Run Graph IDs (Priority: P1)

As an Spanweave subsystem, I can request a new identifier for any run graph entity so I can create records that are unique, time-sortable, and self-describing.

**Why this priority**: Every downstream run graph operation depends on stable identifiers. If this layer is wrong, later worktrees inherit invalid identities.

**Independent Test**: Generate IDs for each supported entity type, verify the expected prefixes and ULID structure, and confirm lexicographic ordering matches generation order for sequential IDs.

**Acceptance Scenarios**:

1. **Given** a caller needs a new run identifier, **When** it requests one, **Then** it receives a value that starts with `run_` followed by a valid ULID.
2. **Given** a caller requests multiple IDs in sequence for the same entity type, **When** those IDs are sorted lexicographically, **Then** the sorted order matches the order they were generated.
3. **Given** a caller needs identifiers for stage, packet, action, evidence, and decision entities, **When** it requests those IDs, **Then** each response uses the correct entity-specific prefix.

---

### User Story 2 - Build Canonical Run Graph Paths (Priority: P2)

As an Spanweave subsystem, I can derive canonical filesystem locations for run graph artifacts so every component stores data in the same predictable tree.

**Why this priority**: Shared path construction keeps the filesystem layout consistent across run graph, evidence, audit, and workflow code.

**Independent Test**: Build paths for a valid run and stage, confirm they resolve to the expected `.spanweave/runs/...` locations, and verify invalid identifiers or stage metadata are rejected.

**Acceptance Scenarios**:

1. **Given** a valid run identifier, **When** a caller requests the run directory, **Then** it receives a path rooted at `.spanweave/runs/<run_id>/`.
2. **Given** a valid run identifier, stage sequence, and stage name, **When** a caller requests the stage directory, **Then** it receives a path ending in `stages/NNN-stage-name/` with a zero-padded sequence.
3. **Given** valid run and stage inputs, **When** a caller requests packet, evidence, transcript, or audit log paths, **Then** each returned value points to the canonical file location under that run tree.
4. **Given** invalid identifiers or malformed stage metadata, **When** a caller requests a path, **Then** the helper fails fast instead of producing a malformed filesystem location.

---

### User Story 3 - Persist Files Without Partial Overwrites (Priority: P3)

As an Spanweave subsystem, I can create directories and replace files atomically so interrupted local writes or final replacement failures do not partially overwrite run graph artifacts.

**Why this priority**: Run graph artifacts are the system of record. Partial writes would undermine replayability and audit guarantees.

**Independent Test**: Create nested directories idempotently, overwrite a file through the atomic writer, and simulate a replacement failure to confirm the destination file remains unchanged.

**Acceptance Scenarios**:

1. **Given** a directory path that may or may not exist, **When** a caller invokes the directory helper repeatedly, **Then** the directory exists afterward and no duplicate-create error is raised.
2. **Given** a target file and replacement content, **When** a caller invokes the atomic write helper successfully, **Then** the destination contains the full new content and no temporary file remains.
3. **Given** an existing destination file, **When** the final replacement step fails after the temporary file is written, **Then** the destination file still contains its original content.

### Edge Cases

- Unsupported entity prefixes must never be accepted as valid IDs for path construction.
- Stage sequence values below `1` must be rejected instead of generating malformed directory names.
- Stage names containing uppercase letters, spaces, or punctuation must normalize to a stable filesystem-safe slug.
- Atomic writes must use a temporary file in the destination directory so the replacement step stays on the same filesystem boundary.
- Temporary files from failed atomic writes should not become the canonical destination path.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST generate new prefixed identifiers for runs, stages, packets, actions, evidence items, and decisions.
- **FR-002**: Each generated identifier MUST use an underscore separator between the entity prefix and the ULID value.
- **FR-003**: Generated identifiers MUST remain lexicographically sortable by creation order when created sequentially.
- **FR-004**: The system MUST provide canonical path constructors for run directories, stage directories, packet artifacts, evidence markdown, evidence JSON, transcripts, and audit logs.
- **FR-005**: All path constructors MUST return path objects rather than raw concatenated strings.
- **FR-006**: Stage directory paths MUST encode the sequence as a zero-padded three-digit prefix followed by a normalized stage slug.
- **FR-007**: Path constructors MUST reject invalid identifiers, invalid stage sequences, and malformed stage names instead of returning malformed paths.
- **FR-008**: The directory helper MUST ensure a target directory exists and MUST be safe to call repeatedly for the same path.
- **FR-009**: The atomic write helper MUST write replacement data to a temporary sibling file before atomically replacing the destination.
- **FR-010**: A replacement failure during atomic write MUST leave any pre-existing destination content unchanged.
- **FR-011**: Automated verification MUST exercise the full public utility surface, including error paths and replacement-failure behavior.

### Key Entities *(include if feature involves data)*

- **Prefixed Entity ID**: A self-describing identifier composed of an entity prefix and a ULID body, used for runs, stages, packets, actions, evidence, and decisions.
- **Stage Locator**: The pair of stage sequence and stage name that determines a canonical stage directory within a run.
- **Run Graph Artifact Path**: A canonical filesystem location for a packet, evidence file, transcript, audit log, or directory within `.spanweave/runs/`.
- **Atomic Write Operation**: A file replacement flow that writes to a temporary sibling file and then replaces the final destination in one step.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A caller can generate 100 sequential IDs for the same entity type and lexicographically sort them with no ordering mismatches.
- **SC-002**: A caller can derive every documented run graph path from valid inputs without performing manual path-string assembly.
- **SC-003**: Invalid IDs, stage sequences, and stage names are consistently rejected by automated verification.
- **SC-004**: Automated verification demonstrates that a simulated replacement failure leaves the destination file bytes unchanged.
- **SC-005**: The utility test suite achieves 100% coverage across the `spanweave/util/` public surface.

## Assumptions

- The Spanweave run graph lives under a repository-relative `.spanweave/` directory.
- Stage sequences are 1-based and rendered with three digits in canonical directory names.
- Stage names are normalized into lowercase hyphenated slugs for filesystem safety.
- The feature guarantees atomic replacement semantics and destination preservation on replacement failure, not universal power-loss durability across every platform or filesystem.
- These helpers form a foundational shared library and are expected to be imported by later worktrees.
