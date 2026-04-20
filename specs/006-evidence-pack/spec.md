# Feature Specification: Evidence Pack

**Feature Branch**: `006-evidence-pack`  
**Created**: 2026-04-20  
**Status**: Draft  
**Input**: User description: "Evidence Pack with JSON + Markdown dual output"

## Clarifications

### Session 2026-04-20

- Q: Does the JSON schema need an explicit version field for stability? → A: Yes, every Evidence Pack carries `schema_version: "1.0"`.
- Q: How is execution evidence linked back to findings? → A: Findings have a stable `finding_id`, and execution entries reference related findings by `finding_id`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Write Replayable Evidence Files (Priority: P1)

As a workflow stage, I can persist one Evidence Pack as both JSON and Markdown inside the run tree, so downstream automation and human reviewers both receive the same proof-of-execution artifact.

**Why this priority**: Dual-format persistence is the core deliverable. If a review cannot emit both files together, Atelier has no durable receipt for approval or rejection.

**Independent Test**: Construct an `EvidencePack`, call `generate(run_id, stage_id, pack)`, and verify that both `evidence.json` and `evidence.md` exist under the expected stage directory and can be opened immediately.

**Acceptance Scenarios**:

1. **Given** a valid `run_id`, `stage_id`, and `EvidencePack`, **When** `generate(...)` is called, **Then** the generator writes `evidence.json` and `evidence.md` under `.atelier/runs/<run_id>/stages/<stage_id>/`.
2. **Given** an existing stage directory, **When** `generate(...)` replaces a prior Evidence Pack, **Then** the new JSON and Markdown contents replace the old contents without leaving partial temp files behind.
3. **Given** an invalid `run_id` or unsafe `stage_id`, **When** `generate(...)` is called, **Then** it fails fast instead of writing outside the run tree.

---

### User Story 2 - Preserve a Stable Machine Schema (Priority: P2)

As a plugin or CI consumer, I can parse Evidence Pack JSON into a validated schema with stable field names and explicit linkage between findings and command output, so automation can replay and inspect reviews without scraping prose.

**Why this priority**: The JSON schema is the long-term integration contract. If it is vague or unstable, future replay, CI, and plugin consumers cannot depend on it.

**Independent Test**: Serialize a populated `EvidencePack` to JSON, parse it back through the Pydantic schema, and confirm the loaded model is equivalent to the original pack.

**Acceptance Scenarios**:

1. **Given** a pack with verdict, confidence, findings, execution output, audit references, timestamp, and reviewer persona ID, **When** it is serialized, **Then** the JSON contains all required fields plus `schema_version: "1.0"`.
2. **Given** findings and execution entries that share `finding_id` references, **When** the JSON is parsed, **Then** those identifiers remain intact for downstream correlation.
3. **Given** an invalid confidence score, missing verdict, or malformed audit ULID, **When** the schema validates input, **Then** validation fails before any file write occurs.

---

### User Story 3 - Render Dense Human Markdown (Priority: P3)

As a human reviewer or demo judge, I can read the Markdown Evidence Pack and immediately understand the verdict, grouped findings, executed commands, and audit-chain tracebacks without opening the JSON sidecar.

**Why this priority**: The Markdown is the human-facing receipt. It needs to be clear in terminals, pull requests, and screenshots while still carrying enough detail to defend the verdict.

**Independent Test**: Render a deterministic fixture pack and compare `evidence.md` against a checked-in golden file.

**Acceptance Scenarios**:

1. **Given** a rejected review with mixed severities, **When** the Markdown renders, **Then** it includes a header, a verdict banner, and findings grouped by `RED`, `ORANGE`, and `YELLOW`.
2. **Given** execution entries with stdout and stderr, **When** the Markdown renders, **Then** each command shows exit code and fenced code blocks for captured output.
3. **Given** audit-chain ULIDs, **When** the Markdown renders, **Then** each reference is emitted as a visible markdown link for traceback navigation.

### Edge Cases

- What happens when a pack has no findings for one or more severity groups?
- What happens when a command only has stdout, only stderr, or no captured output at all?
- What happens when execution output contains secrets such as API keys, bearer tokens, or passwords?
- What happens when a finding omits a line number because the issue applies to an entire file?
- What happens when an Evidence Pack replaces an earlier pack and one destination file already exists?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define an `EvidencePack` schema in `atelier/evidence/schema.py` with required fields `schema_version`, `verdict`, `confidence`, `findings`, `execution`, `audit_chain`, `timestamp`, and `reviewer_persona_id`.
- **FR-002**: `schema_version` MUST default to the fixed string `"1.0"` and reject other values.
- **FR-003**: `verdict` MUST accept only `APPROVED`, `NEEDS_REVISION`, or `REJECTED`.
- **FR-004**: `confidence` MUST accept only numeric values in the inclusive range `0.0` through `1.0`.
- **FR-005**: The schema MUST define a `Finding` model with `finding_id`, `severity`, `description`, `file`, optional `line`, and `verification`.
- **FR-006**: `Finding.severity` MUST accept only `RED`, `ORANGE`, or `YELLOW`.
- **FR-007**: The schema MUST define a `CommandOutput` model with `command`, `stdout`, `stderr`, `exit_code`, and `finding_ids`.
- **FR-008**: `CommandOutput.finding_ids` MUST reference `Finding.finding_id` values so execution evidence can be correlated back to findings.
- **FR-009**: `audit_chain` MUST contain one or more ULID references stored as strings.
- **FR-010**: `timestamp` MUST be timezone-aware and serialized in a stable machine-readable format.
- **FR-011**: `generate(run_id, stage_id, pack)` in `atelier/evidence/generator.py` MUST write `evidence.json` and `evidence.md` to `.atelier/runs/<run_id>/stages/<stage_id>/`.
- **FR-012**: The generator MUST validate `run_id` and reject unsafe `stage_id` values containing traversal or path separators.
- **FR-013**: The generator MUST render Markdown using a Jinja2 template stored at `atelier/evidence/templates/evidence.md.j2`.
- **FR-014**: The Markdown output MUST include a header, verdict banner, grouped findings, execution output sections with fenced code blocks, and audit-chain links.
- **FR-015**: The generator MUST apply redaction to execution stdout and stderr before writing JSON or Markdown output.
- **FR-016**: The generator MUST replace both evidence files as one logical operation so a failed write does not leave mismatched JSON and Markdown artifacts behind.
- **FR-017**: `tests/test_evidence.py` MUST cover JSON round-trip equivalence, deterministic Markdown rendering via a golden file, and write-time output generation.

### Key Entities *(include if feature involves data)*

- **EvidencePack**: The review receipt containing verdict metadata, findings, execution evidence, audit references, and reviewer identity.
- **Finding**: A structured review issue with a stable `finding_id`, severity, affected file location, and verification text.
- **CommandOutput**: A captured command invocation with stdout, stderr, exit code, and references to the findings it supports.
- **Audit Reference**: A ULID string that links the pack back to append-only audit records.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `EvidencePack(verdict="REJECTED", findings=[...])` generates both `evidence.json` and `evidence.md` under the requested stage path.
- **SC-002**: Parsing the generated JSON back through `EvidencePack.model_validate_json(...)` yields a model equivalent to the original non-secret fixture pack.
- **SC-003**: The generated Markdown contains a visible verdict banner, findings grouped by severity, an execution section with fenced command output, and markdown links for every audit reference.
- **SC-004**: `tests/test_evidence.py` passes locally with a checked-in golden Markdown file and deterministic fixture inputs.
- **SC-005**: Execution outputs containing secrets are written in redacted form rather than leaking the original secret values into either artifact.

## Assumptions

- `run_id` uses the existing prefixed ULID format already validated by `atelier.util`.
- `stage_id` is the run-graph directory label such as `001-review`, not a prefixed ULID.
- Findings may omit `line` for file-wide issues, but `file` remains required in this first schema version.
- W10 may later centralize redaction logic, but W08 still needs redacted evidence output now.
