# Feature Specification: Typed Memory Records

**Feature Branch**: `005-typed-memory-records`  
**Created**: 2026-04-20  
**Status**: Draft  
**Input**: User description: "typed memory records (Decision, ReviewFinding, RejectedAlternative) with frontmatter + markdown body, filesystem-first persistence"

## Clarifications

### Session 2026-04-20

- Q: Which fields are required vs optional? → A: `run_id`, `stage_id`, `source`, and `body` are required inputs; `id` and `timestamp` are generated when omitted but must always be persisted; `version` defaults to `1`; `related_issues`, `related_adrs`, and `tags` default to empty lists; `confidence` is optional and nullable.
- Q: Which frontmatter format should typed memory records use? → A: YAML frontmatter is required for all record files.
- Q: How should schema evolution work in Phase 0? → A: Each record stores a `version` field in frontmatter, and Phase 0 does not perform migrations.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Persist A Typed Memory Record (Priority: P1)

As an Atelier workflow stage, I can persist a typed memory record to the filesystem as one markdown file with YAML frontmatter and a markdown body, so decisions and review artifacts become grep-able and committable.

**Why this priority**: Without a stable write path, the knowledge plane does not exist and later ADR, review, and audit features have no durable substrate.

**Independent Test**: Construct a `Decision`, write it to a temporary memory root, and confirm the resulting file exists under the expected record directory with valid YAML frontmatter, preserved markdown structure, and redacted secret-like content.

**Acceptance Scenarios**:

1. **Given** a valid `Decision` record with run and stage identifiers, **When** `write_record(...)` persists it, **Then** the writer creates one markdown file under the Decision collection using the record ULID in the filename.
2. **Given** a record body that contains secret-like text such as `OPENAI_API_KEY=sk-xxx`, **When** the record is written, **Then** the file content on disk contains redacted text instead of the raw secret.
3. **Given** a record file already exists at the destination path, **When** the writer persists updated content, **Then** the write completes atomically and leaves no sibling temporary files behind.

---

### User Story 2 - Read A Typed Memory Record Back Into A Schema (Priority: P2)

As a downstream automation component, I can read a persisted memory record back into a typed schema, so later stages can derive ADRs and context from structured records instead of reparsing raw prose.

**Why this priority**: Read support is the second half of persistence. If records cannot round-trip back into typed models, the filesystem becomes archival only and not operational.

**Independent Test**: Write a `Decision` containing headings, lists, and fenced code blocks, read it back with `read_record(...)`, and confirm every structured field and the markdown body match the written record.

**Acceptance Scenarios**:

1. **Given** a markdown file with YAML frontmatter and `type: Decision`, **When** `read_record(path)` runs, **Then** it returns a validated `Decision` instance.
2. **Given** a record body with multi-line markdown formatting, **When** the record is read back, **Then** the body text matches the stored markdown exactly.
3. **Given** a record file with unsupported `type` metadata or invalid identifiers, **When** `read_record(path)` runs, **Then** it raises a validation error instead of returning a partially typed record.

---

### User Story 3 - Query Typed Records By Type And Metadata (Priority: P3)

As a future compiler or ADR synthesizer, I can list typed memory records by record type and metadata filters, so later features can answer questions like "show all safety-critical decisions for this run" without a database.

**Why this priority**: Filesystem-first only works if query-time filtering stays practical. Typed records must support simple derivations directly from the directory tree and frontmatter metadata.

**Independent Test**: Write a mix of `Decision` and `ReviewFinding` records with different tags, run IDs, and stages, then confirm `list_records(...)` returns only the expected subset for a tag-filtered Decision query.

**Acceptance Scenarios**:

1. **Given** multiple record files of different types under the memory root, **When** `list_records(type="Decision")` runs, **Then** it only returns Decision records.
2. **Given** Decision records with different tag sets, **When** `list_records(type="Decision", tags=["safety-critical"])` runs, **Then** it only returns Decision records that include the requested tag.
3. **Given** no records match the requested filters, **When** `list_records(...)` runs, **Then** it returns an empty list rather than failing.

### Edge Cases

- What happens when a file is missing frontmatter, has malformed YAML, or declares an unsupported record type?
- What happens when a record `id` prefix does not match its declared `type`, or the ULID payload is invalid?
- What happens when a record body contains blank lines, fenced code blocks, or trailing newlines that must survive a round-trip unchanged?
- What happens when tags, related issue references, or ADR references are omitted and should default to empty lists?
- What happens when the writer receives a base memory directory versus a type-specific collection directory?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define Pydantic models for `Decision`, `ReviewFinding`, and `RejectedAlternative` in `atelier/memory/records.py`.
- **FR-002**: Each record model MUST persist frontmatter fields `id`, `type`, `version`, `run_id`, `stage_id`, `timestamp`, `related_issues`, `related_adrs`, `tags`, `confidence`, and `source`, plus a markdown `body`.
- **FR-003**: Record schemas MUST reject unknown fields and validate `run_id`, `stage_id`, and record identifier ULID payloads.
- **FR-004**: The system MUST generate `id` and `timestamp` automatically when callers omit them, while still persisting those values in frontmatter.
- **FR-005**: The system MUST use YAML frontmatter for every typed memory record file.
- **FR-006**: The system MUST write records under a filesystem-first memory root using type-specific collections for decisions, review findings, and rejected alternatives.
- **FR-007**: `write_record(record, path)` MUST serialize one record to markdown, apply secret redaction before write, and persist the result with atomic replacement semantics.
- **FR-008**: The writer MUST use the record ULID in the filename pattern `<type-slug>_<ulid>.md`.
- **FR-009**: `read_record(path)` MUST parse YAML frontmatter with `python-frontmatter`, preserve the raw markdown body, and return the appropriate typed record model.
- **FR-010**: `list_records(...)` MUST scan persisted markdown files recursively from the memory root and return typed record instances.
- **FR-011**: `list_records(...)` MUST support filtering by record type and frontmatter metadata, including tags.
- **FR-012**: The persistence layer MUST not introduce database dependencies or non-filesystem storage for this Phase 0 slice.
- **FR-013**: `tests/test_memory.py` MUST cover round-trip persistence, list filtering, and write-time redaction.

### Key Entities *(include if feature involves data)*

- **MemoryRecord**: Shared typed record shape containing frontmatter metadata plus a markdown body.
- **Decision**: A typed memory record that captures a concrete workflow or architectural decision.
- **ReviewFinding**: A typed memory record that captures a reviewer-observed issue, concern, or validation result.
- **RejectedAlternative**: A typed memory record that captures an explicitly rejected option so later ADR synthesis can explain tradeoffs.
- **MemoryQuery**: A lightweight filter set used to select records by type and frontmatter metadata without a database.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `uv run pytest tests/test_memory.py -v` passes locally.
- **SC-002**: Writing a `Decision` record creates exactly one markdown file in the expected typed collection with valid YAML frontmatter and markdown body content.
- **SC-003**: `read_record(path)` returns a `Decision` whose structured fields and markdown body match the written record for a non-secret round-trip fixture.
- **SC-004**: `list_records(type="Decision", tags=["safety-critical"])` returns only the expected tagged Decision records for the fixture set.
- **SC-005**: A record body containing `OPENAI_API_KEY=sk-xxx` is redacted on disk and no raw secret substring remains in the persisted file.

## Assumptions

- The canonical memory root for Phase 0 is `.atelier/memory/`.
- Type-specific collections map to `decisions/`, `findings/`, and `rejected_alternatives/`.
- Later phases may add more record types and migrations, but Phase 0 only needs a stored `version` field and no migration engine.
- Filtering remains in-process and filesystem-backed; no secondary index or database is introduced in this slice.
