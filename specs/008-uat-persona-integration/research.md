# Research: UAT Persona Integration

## Decision 1: Resolve the external UAT skill path as either an executable file or a directory with a small entrypoint search

- **Decision**: Support `SPANWEAVE_UAT_SKILL_PATH` pointing at either an executable file or a directory. If it is a directory, resolve a small set of conventional entrypoints in priority order and otherwise raise a clear error instructing the caller to point the env var at an invokable path.
- **Rationale**: The requested default is a directory path, but this workspace does not contain the external `ccc` tree. Supporting both directory and file inputs keeps the integration usable without over-committing to one unknown external layout.
- **Alternatives considered**:
  - Require an exact executable file path only: rejected because the requested default points at a directory, which would force every caller to override the default immediately.
  - Attempt to interpret arbitrary skill metadata files: rejected because the external skill contract is not present in this repo and speculative parsing would be brittle.

## Decision 2: Resolve credentials from packet first, then environment, then repo-relative `.env.local`, and pass them to the subprocess via environment variables

- **Decision**: Resolve `TEST_USER` and `TEST_PASSWORD` from explicit packet data first, then from the process environment, then from `../../.env.local` relative to the repo root. Pass resolved credentials to the subprocess via environment variables instead of command-line arguments.
- **Rationale**: This matches the user's requested credential source while keeping tests easy to isolate and avoiding accidental secret exposure in command strings or process listings.
- **Alternatives considered**:
  - Read only `.env.local`: rejected because tests and CI need a simpler injection path and the file may not exist in every workspace.
  - Pass credentials as CLI arguments: rejected because it increases the chance of leaking secrets into command strings and execution logs.

## Decision 3: Parse either JSON output or tolerant line-oriented text into a minimal Evidence Pack

- **Decision**: Try JSON parsing first; if the report is not JSON, fall back to parsing a line-oriented text format that recognizes summary lines like `UAT: 2/3 passed` and status-prefixed checks such as `PASS:`, `WARN:`, `FAIL:`, or `ERROR:`.
- **Rationale**: The external skill format is not available in this repository, so the parser should be intentionally tolerant while still producing deterministic findings in tests.
- **Alternatives considered**:
  - Require JSON only: rejected because a human-oriented skill may emit markdown or plain text and the requested integration should not fail solely due to presentation format.
  - Treat raw stdout as an opaque blob with no parsing: rejected because the acceptance criteria explicitly require structured Evidence Pack findings.

## Decision 4: Add a minimal local Evidence Pack and redaction contract now instead of blocking on future work

- **Decision**: Introduce a small `spanweave.evidence.schema` module and a focused `spanweave.security.redaction` function sufficient for W18's needs.
- **Rationale**: The package stubs already exist in this repo, and W18 cannot satisfy its acceptance criteria without a structured evidence object and secret scrubbing.
- **Alternatives considered**:
  - Return ad hoc dictionaries from the runner: rejected because the feature is explicitly about producing structured Evidence Pack findings and should use a stable model shape.
  - Wait for W08/W10 to land first: rejected because the user asked to complete W18 in this workspace now.
