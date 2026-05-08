# Research: Typed Memory Records

## Decision 1: Model typed memory as one strict base record plus three concrete record types

- **Decision**: Use one shared Pydantic base model for common frontmatter fields and derive `Decision`, `ReviewFinding`, and `RejectedAlternative` as concrete record types with fixed `type` literals and record-specific identifier prefixes.
- **Rationale**: This keeps validation rules consistent while still returning concrete types for downstream consumers such as ADR synthesis and reviewer context lookup.
- **Alternatives considered**:
  - Three unrelated models with duplicated field definitions: rejected because it increases schema drift risk.
  - One untyped generic record model: rejected because the roadmap explicitly treats these record kinds as distinct typed primitives.

## Decision 2: Serialize frontmatter manually and use python-frontmatter for metadata parsing

- **Decision**: Build the markdown file text manually with YAML frontmatter so the stored body remains byte-stable, and use `python-frontmatter` on reads to validate and parse the frontmatter metadata.
- **Rationale**: The library is the required metadata parser, but its built-in dump/load path normalizes body content in ways that can strip trailing newlines. Manual serialization preserves the markdown body exactly while keeping frontmatter parsing on the supported library.
- **Alternatives considered**:
  - Use `frontmatter.dumps(...)` for writes: rejected because it normalizes body formatting and weakens round-trip fidelity.
  - Avoid `python-frontmatter` entirely: rejected because the feature brief explicitly calls for it on the read path.

## Decision 3: Use filesystem collections under `.spanweave/memory/` and derive filenames from record IDs

- **Decision**: Persist records under `.spanweave/memory/decisions/`, `.spanweave/memory/findings/`, and `.spanweave/memory/rejected_alternatives/`, with filenames generated from the record identifier as `<type-slug>_<ulid>.md`.
- **Rationale**: This matches the roadmap storage layout, keeps queries grep-friendly, and makes record locations human-readable without a database.
- **Alternatives considered**:
  - Store every record type in one flat directory: rejected because the roadmap already treats directory structure as schema.
  - Require callers to pass the full destination filename: rejected because it leaks naming policy into every caller.

## Decision 4: Apply redaction to the fully rendered markdown before atomic write

- **Decision**: Redact the serialized markdown text immediately before `atomic_write(...)`.
- **Rationale**: Redaction at the persistence boundary ensures secrets never land on disk in either frontmatter or body content and matches the project's stated Phase 0 redaction strategy.
- **Alternatives considered**:
  - Redact only the body field: rejected because secrets could still appear in metadata fields.
  - Redact at read time: rejected because it still writes secrets to disk first.

## Decision 5: Keep listing/query support simple and recursive

- **Decision**: Implement `list_records(...)` as a recursive `.md` scan rooted at `.spanweave/memory/`, followed by in-process filtering on parsed record metadata.
- **Rationale**: This preserves the filesystem-first architecture and is sufficient for the small Phase 0 corpus size.
- **Alternatives considered**:
  - Introduce SQLite or an index cache now: rejected because the roadmap explicitly keeps the core storage layer file-native in Phase 0.
  - Require callers to preselect directories and filter manually: rejected because downstream stages need one reusable query helper.
