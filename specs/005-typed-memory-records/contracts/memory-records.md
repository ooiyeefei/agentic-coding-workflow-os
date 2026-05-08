# Contract: spanweave.memory Persistence API

## Record Schemas

- `Decision(...)`
- `ReviewFinding(...)`
- `RejectedAlternative(...)`

**Contract**:

- Each record exposes frontmatter fields `id`, `type`, `version`, `run_id`, `stage_id`, `timestamp`, `related_issues`, `related_adrs`, `tags`, `confidence`, and `source`, plus a markdown `body`.
- Unknown fields are rejected during validation.
- `run_id`, `stage_id`, and record identifiers validate their ULID payloads.
- `id` and `timestamp` may be omitted by callers but are always present on persisted records.

## Writer

- `write_record(record, path) -> Path`

**Contract**:

- Accepts a concrete typed record plus a base memory path or collection path.
- Persists the record as one markdown file with YAML frontmatter and markdown body.
- Applies redaction before calling `atomic_write(...)`.
- Uses a deterministic filename derived from the record identifier and returns the final file path.

## Reader

- `read_record(path) -> Record`
- `list_records(path=Path(".spanweave/memory"), *, type=None, filters=None, **criteria) -> list[Record]`

**Contract**:

- `read_record(...)` parses YAML frontmatter with `python-frontmatter`, preserves the raw markdown body, and returns the concrete typed record.
- `list_records(...)` recursively scans markdown files from the supplied root and returns typed record instances.
- `list_records(...)` supports filtering by record type and frontmatter metadata, including tag subset filtering.
- Unsupported record types, malformed frontmatter, or invalid identifiers raise validation errors rather than producing partially typed records.
