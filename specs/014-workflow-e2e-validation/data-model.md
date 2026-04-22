# Data Model: Workflow E2E Validation

## Integration Persona Mode

- **Purpose**: Selects how the integration harness resolves persona calls.
- **Values**:
  - `mock`: deterministic, repository-local responses for CI and default local runs.
  - `real`: opt-in provider-backed persona execution enabled only when `ATELIER_INTEGRATION_REAL_LLM=1`.
- **Rules**:
  - `mock` is the default when the environment variable is absent or falsey.
  - `real` requires the provider credentials needed by the selected persona adapters.

## Workflow Artifact Set

- **Purpose**: Captures the filesystem outputs that prove a workflow run completed correctly.
- **Run-level fields**:
  - `run_id`
  - `run_dir`
  - `run_md_path`
  - `workflow_state_path`
  - `adr_paths`
- **Stage-level fields**:
  - `stage_id`
  - `stage_dir`
  - `packet_path`
  - `transcript_path`
  - `evidence_md_path`
  - `evidence_json_path`
  - `completion_marker_path`
- **Rules**:
  - Stage IDs must follow the sequence and slug defined by `atelier.rungraph`.
  - The artifact set is considered complete only when every workflow stage has its expected files and completed stages carry `.complete`.

## Integration Harness

- **Purpose**: Shared fixture-owned coordinator that wires compiler, persona, workflow, evidence, memory, ADR, and git helpers together for tests.
- **Inputs**:
  - Demo issue text and metadata
  - Demo app path
  - Workflow definition
  - Persona mode (`mock` or `real`)
- **Outputs**:
  - A completed `Workflow Artifact Set`
  - Stored memory records under `.atelier/memory/`
  - Synthesized ADR files under `docs/adr/`
- **Rules**:
  - Every harness run executes inside an isolated temporary repository root.
  - The harness may resume approval-gated stages explicitly, but it must not bypass them silently.

## CI Validation Gate

- **Purpose**: Represents the repository automation that enforces the validation suite on every PR.
- **Fields**:
  - `trigger_events`
  - `python_version`
  - `job_name`
  - `command`
  - `mode`
- **Rules**:
  - Integration jobs must run in default mock mode.
  - Local and CI entrypoints must execute equivalent integration commands.
