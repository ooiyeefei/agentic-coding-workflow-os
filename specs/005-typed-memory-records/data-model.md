# Data Model: Typed Memory Records

## MemoryRecord

- **Purpose**: Represents one persisted knowledge-plane record with typed frontmatter plus a markdown body.
- **Fields**:
  - `id`: Canonical record identifier in the form `<record-prefix>_<ulid>`
  - `type`: Concrete record type discriminator (`Decision`, `ReviewFinding`, or `RejectedAlternative`)
  - `version`: Schema version persisted in frontmatter for future migrations
  - `run_id`: Owning run identifier
  - `stage_id`: Owning stage identifier
  - `timestamp`: UTC creation timestamp
  - `related_issues`: Related issue identifiers
  - `related_adrs`: Related ADR identifiers or slugs
  - `tags`: Queryable tag list
  - `confidence`: Optional confidence score between `0.0` and `1.0`
  - `source`: Provenance label for the record author or producer
  - `body`: Raw markdown payload
- **Validation rules**:
  - Unknown fields are forbidden.
  - `id`, `run_id`, and `stage_id` must contain valid ULID payloads with the expected prefixes.
  - `timestamp` is timezone-aware UTC when generated internally.
  - `body` must be non-empty and is preserved exactly as stored on disk.

## Decision

- **Purpose**: Captures a durable workflow or architecture decision.
- **Fields**:
  - Inherits all `MemoryRecord` fields.
- **Validation rules**:
  - `type` is fixed to `Decision`.
  - `id` prefix is fixed to `decision_`.

## ReviewFinding

- **Purpose**: Captures a review observation, defect, or warning that later stages may query or aggregate.
- **Fields**:
  - Inherits all `MemoryRecord` fields.
- **Validation rules**:
  - `type` is fixed to `ReviewFinding`.
  - `id` prefix is fixed to `review_finding_`.

## RejectedAlternative

- **Purpose**: Captures an option that was considered and explicitly not chosen.
- **Fields**:
  - Inherits all `MemoryRecord` fields.
- **Validation rules**:
  - `type` is fixed to `RejectedAlternative`.
  - `id` prefix is fixed to `rejected_alternative_`.

## MemoryQuery

- **Purpose**: Represents the supported filter set for filesystem-backed record listing.
- **Fields**:
  - `type`: Optional concrete record type filter
  - `tags`: Optional tag subset filter
  - `run_id`: Optional owning run filter
  - `stage_id`: Optional owning stage filter
  - `source`: Optional provenance filter
  - `related_issues`: Optional related issue subset filter
  - `related_adrs`: Optional related ADR subset filter
  - `confidence_min`: Optional lower bound for confidence
- **Validation rules**:
  - Tag and related-reference filters are treated as subset matches.
  - Unknown filter keys are rejected to keep query behavior explicit.
