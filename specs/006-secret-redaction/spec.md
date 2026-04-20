# Feature Specification: Secret Redaction

**Feature Branch**: `005-secret-redaction`  
**Created**: 2026-04-20  
**Status**: Draft  
**Input**: User description: "regex-based secret redactor with pluggable patterns"

## Clarifications

### Session 2026-04-20

- Q: What redaction marker format should built-in patterns use? → A: Use audit-visible markers in the format `[REDACTED:<pattern-name>]`.
- Q: How should sensitive environment-variable names be matched? → A: Match sensitive environment-variable names and assignment keys case-insensitively.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Redact Known Secrets Before Persistence (Priority: P1)

As Atelier's persistence layer, I can pass transcript, packet, evidence, or audit-log text through one redaction function before it is stored, so persisted artifacts do not retain reusable credentials.

**Why this priority**: Stored secrets are the immediate liability. The MVP must remove common credential formats before anything else.

**Independent Test**: Call the redaction function with representative secret-bearing strings and confirm the returned text replaces each secret-bearing fragment while leaving surrounding context readable.

**Acceptance Scenarios**:

1. **Given** a line such as `OPENAI_API_KEY=sk-abc123xyz`, **When** the line is redacted, **Then** the variable name remains visible and the secret value is replaced with an audit-visible marker in the format `[REDACTED:<pattern-name>]`.
2. **Given** a header such as `Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.xxx`, **When** the line is redacted, **Then** the `Bearer ` prefix remains visible and the token portion is replaced with an audit-visible marker in the format `[REDACTED:<pattern-name>]`.
3. **Given** text containing one or more known credential prefixes such as OpenAI, GitHub, Slack, AWS, or GCP credential shapes, **When** the text is redacted, **Then** every matched secret is replaced in a single pass.

---

### User Story 2 - Preserve Useful Context While Avoiding False Positives (Priority: P2)

As an investigator reading stored artifacts, I can still see non-secret context and structural hints after redaction, so logs remain useful for debugging without exposing credentials.

**Why this priority**: Blindly deleting text would make evidence less useful. Redaction must preserve enough shape to explain what was stored without leaking the secret itself.

**Independent Test**: Redact safe prose and structured credential-bearing strings, then verify that safe text stays unchanged and URL/header/log shapes remain recognizable after redaction.

**Acceptance Scenarios**:

1. **Given** the input `hello world`, **When** it is redacted, **Then** the output remains `hello world`.
2. **Given** `DATABASE_URL=postgres://user:pass@host/db`, **When** it is redacted, **Then** the scheme, host, and database path remain visible while credential components are replaced with redaction markers.
3. **Given** ordinary text that contains pattern-adjacent characters but not a real secret, **When** it is redacted, **Then** the text passes through unchanged.

---

### User Story 3 - Extend Coverage With Extra Patterns (Priority: P3)

As an integrator, I can provide extra regex patterns for organization-specific secrets, so the same redaction entrypoint can cover local credential formats without forking the built-in catalog.

**Why this priority**: Regex-based coverage is intentionally incomplete in Phase 0. Extra patterns let deployments close obvious gaps without waiting for a core release.

**Independent Test**: Call the redaction function with a caller-provided extra pattern and confirm that the custom secret is redacted while built-in behavior remains unchanged.

**Acceptance Scenarios**:

1. **Given** a caller-provided extra regex that matches an organization-specific token, **When** the text is redacted, **Then** the custom token is replaced with a redaction marker.
2. **Given** text that contains both built-in secret formats and a caller-provided custom secret, **When** the text is redacted, **Then** all matches are redacted in one output string.

### Edge Cases

- Multiple different secrets appear in the same line or paragraph.
- Environment assignments are quoted, spaced, or use mixed-case variable names.
- A credential-like prefix appears inside a normal English word and must not be redacted.
- URL-shaped text contains credentials and query/path context that should remain readable after redaction.
- Input already contains redaction markers and should not be re-redacted into unreadable nested markers.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose one pure redaction entrypoint that accepts a string and returns a redacted string without mutating external state.
- **FR-002**: The system MUST provide a built-in regex catalog for common secret-bearing formats, including environment-variable assignments, known credential prefixes, bearer tokens, AWS access keys, GCP service-account material, and sensitive environment-variable names.
- **FR-003**: The system MUST replace matched secret-bearing substrings with audit-visible markers in the format `[REDACTED:<pattern-name>]` instead of silently removing them.
- **FR-004**: The system MUST preserve surrounding non-secret context, including header names, variable names, URL schemes, hosts, paths, and safe prose.
- **FR-005**: The system MUST redact credentials embedded in database-style URLs while preserving the overall URL shape for debugging.
- **FR-006**: The system MUST treat sensitive environment-variable names case-insensitively.
- **FR-007**: The system MUST accept additional caller-provided regex patterns and apply them together with the built-in patterns.
- **FR-008**: The system MUST assign stable audit-visible labels to redactions produced by caller-provided extra patterns.
- **FR-009**: The system MUST avoid false positives on common English words, ordinary identifiers, and punctuation-adjacent safe strings that do not satisfy a full secret pattern.
- **FR-010**: The system MUST leave already redacted markers readable rather than repeatedly redacting them.
- **FR-011**: The system MUST be covered by focused positive and negative tests using representative real-looking secret strings and safe passthrough strings.

### Key Entities *(include if feature involves data)*

- **BuiltInPattern**: A named regex rule describing one supported secret family and the marker family it maps to.
- **RedactionMarker**: The visible placeholder inserted into stored text to show that a secret was removed and what family of pattern triggered the removal.
- **ExtraPattern**: A caller-supplied regex added at runtime to redact an organization-specific secret format.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Positive tests cover at least 30 representative secret-bearing inputs and all of them redact the intended secret substring.
- **SC-002**: Negative tests cover at least 10 safe inputs and all of them pass through unchanged.
- **SC-003**: The accepted examples `OPENAI_API_KEY=sk-abc123xyz`, `hello world`, `Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.xxx`, and `DATABASE_URL=postgres://user:pass@host/db` behave as specified under automated tests.
- **SC-004**: Redacted output preserves enough structural context that a reviewer can still identify the original field type or URL shape without seeing the secret value.
- **SC-005**: Caller-provided extra patterns can redact at least one custom secret format without breaking built-in redaction behavior.

## Assumptions

- Phase 0 uses regex-based matching only; entropy detection and pluggable redactor classes are deferred to later phases.
- This feature delivers the pure redaction function and pattern catalog; call sites at persistence boundaries will adopt that helper as follow-on integration work unless already in scope elsewhere.
- Inputs arrive as Python strings that may contain log lines, markdown, JSON fragments, headers, or URL-like values in a single text blob.
