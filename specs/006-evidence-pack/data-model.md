# Data Model: Evidence Pack

## EvidencePack

- **Purpose**: Canonical proof-of-execution artifact for one review stage.
- **Fields**:
  - `schema_version`: literal `"1.0"`
  - `verdict`: enum `APPROVED | NEEDS_REVISION | REJECTED`
  - `confidence`: float `0.0..1.0`
  - `findings`: non-empty-or-empty list of `Finding`
  - `execution`: non-empty-or-empty list of `CommandOutput`
  - `audit_chain`: list of ULID strings
  - `timestamp`: timezone-aware datetime
  - `reviewer_persona_id`: non-empty string
- **Rules**:
  - `confidence` must stay within inclusive bounds.
  - `timestamp` must include timezone information.
  - Every `CommandOutput.finding_ids` entry must reference an existing `Finding.finding_id`.

## Finding

- **Purpose**: Structured issue or risk supporting the final verdict.
- **Fields**:
  - `finding_id`: stable non-empty string identifier used for linkage
  - `severity`: enum `RED | ORANGE | YELLOW`
  - `description`: non-empty string
  - `file`: repository-relative path string
  - `line`: optional integer greater than or equal to 1
  - `verification`: non-empty string describing how the finding was validated
- **Rules**:
  - `line` is optional to support file-wide findings.
  - `description` and `verification` are required because findings must be defensible from the artifact alone.

## CommandOutput

- **Purpose**: Captured execution evidence supporting zero or more findings.
- **Fields**:
  - `command`: non-empty string
  - `stdout`: string, possibly empty after redaction
  - `stderr`: string, possibly empty after redaction
  - `exit_code`: integer
  - `finding_ids`: list of zero or more `Finding.finding_id` references
- **Rules**:
  - Output text is persisted only after redaction.
  - `finding_ids` may be empty for commands that establish context without proving a specific finding.

## Audit Reference

- **Purpose**: Link from the Evidence Pack to append-only audit records.
- **Fields**:
  - ULID string
- **Rules**:
  - Must parse as a valid ULID.
