# Data Model: UAT Persona Integration

## UATRequest

- **Purpose**: The context packet consumed by `UAT.respond(...)`.
- **Fields**:
  - `app_path`: target application directory or executable root for UAT
  - `test_user`: optional explicit username override
  - `test_password`: optional explicit password override
  - `timeout_seconds`: optional subprocess timeout override
  - `skill_path`: optional explicit UAT skill path override
  - `notes`: optional extra execution context rendered into the LLM prompt

## TestAccountCredentials

- **Purpose**: The credentials resolved for subprocess execution.
- **Fields**:
  - `username`
  - `password`
- **Rules**:
  - Must contain both fields before subprocess launch
  - Values are treated as secrets and must be redacted from any surfaced evidence

## UATExecutionResult

- **Purpose**: The raw subprocess outcome before it is attached to a persona response.
- **Fields**:
  - `command`: executed command string or argv list rendered for evidence
  - `exit_code`
  - `stdout`
  - `stderr`
  - `summary`
  - `findings`

## Finding

- **Purpose**: One normalized UAT observation suitable for an Evidence Pack.
- **Fields**:
  - `severity`: `RED`, `ORANGE`, or `YELLOW`
  - `description`
  - `verification`
  - `file` (optional)
  - `line` (optional)

## CommandOutput

- **Purpose**: Captured execution evidence for one subprocess command.
- **Fields**:
  - `command`
  - `stdout`
  - `stderr`
  - `exit_code`

## EvidencePack

- **Purpose**: The structured output attached to the UAT persona response.
- **Fields**:
  - `summary`
  - `findings`
  - `execution`
- **Rules**:
  - Execution output is always redacted before it is stored
  - Findings are derived from parsed report failures or warnings
  - A fully successful UAT run may contain zero findings but still records execution evidence
