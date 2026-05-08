# Feature Specification: UAT Persona Integration

**Feature Branch**: `008-uat-persona-integration`  
**Created**: 2026-04-20  
**Status**: Draft  
**Input**: User description: "UAT persona that invokes ccc/skills/uat-testing as subprocess and produces Evidence Pack findings"

## Clarifications

### Session 2026-04-20

- Q: How is the external UAT skill located? → A: The runner resolves `SPANWEAVE_UAT_SKILL_PATH`, defaulting to `/home/fei/fei/code/hackathon/ccc/skills/uat-testing`, and callers may override it for local worktrees or tests.
- Q: How should the system behave when the configured UAT skill path is missing or unusable? → A: Raise a clear execution error immediately; do not silently skip UAT, fabricate a passing result, or downgrade the stage.
- Q: How are test credentials sourced? → A: Prefer explicit credentials supplied in the packet, then `TEST_USER` and `TEST_PASSWORD` from the environment, then repo-relative `../../.env.local`; if no usable credentials are available, fail with a clear error.
- Q: How is subprocess execution bounded? → A: The runner enforces a real timeout so a hung UAT subprocess cannot block the workflow indefinitely.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run Real UAT Against The Target App (Priority: P1)

As a workflow stage, I can invoke the user's existing UAT skill against a concrete app path with test credentials so Spanweave verifies a real user-facing flow instead of only unit or integration tests.

**Why this priority**: The subprocess execution path is the core proof that UAT is real. Without it, the persona would only simulate acceptance testing and the stage would not deliver user value.

**Independent Test**: Instantiate the UAT persona with a mocked adapter and mocked subprocess runner, call `respond(...)` with an app path and credentials, and confirm the subprocess is invoked with the resolved skill path plus the target app context.

**Acceptance Scenarios**:

1. **Given** a valid UAT skill path and target app path, **When** the UAT persona responds to a packet, **Then** it invokes the external UAT subprocess instead of claiming a result without execution.
2. **Given** test credentials are provided through the packet, environment, or repo-local `.env.local`, **When** the subprocess is launched, **Then** the credentials are made available to the subprocess without requiring hardcoded values in source files.
3. **Given** the subprocess exceeds the allowed runtime, **When** the runner waits for completion, **Then** it fails the UAT execution with a clear timeout error instead of hanging indefinitely.

---

### User Story 2 - Convert UAT Output Into Structured Evidence (Priority: P2)

As a workflow engine, I can turn the UAT report and captured execution output into structured Evidence Pack findings so downstream stages can persist, display, and reason over user-facing validation results.

**Why this priority**: Execution alone is not enough. The output has to become a reusable artifact with normalized findings and captured stdout/stderr, otherwise the workflow cannot consume it.

**Independent Test**: Feed the runner a mocked subprocess result containing a representative UAT report, then assert the resulting Evidence Pack summary, findings, and execution record match the report content.

**Acceptance Scenarios**:

1. **Given** the UAT subprocess returns a structured or semi-structured report, **When** the runner parses it, **Then** it produces an Evidence Pack with findings populated from the reported failures or warnings.
2. **Given** the subprocess emits stdout and stderr, **When** the Evidence Pack is created, **Then** both streams are preserved in execution evidence with secret values redacted.
3. **Given** the UAT report indicates full success, **When** the Evidence Pack is created, **Then** it includes a human-readable success summary and no false-negative findings are introduced.

---

### User Story 3 - Keep UAT Persona Capability-Gated And Transparent (Priority: P3)

As an orchestrator, I can instantiate the UAT persona through the same capability-routing contract as other personas and receive a normalized response that includes both the LLM-planned UAT intent and the subprocess-backed evidence outcome.

**Why this priority**: UAT still has to behave like an Spanweave persona, not a one-off script. Capability routing and normalized responses keep the workflow architecture coherent.

**Independent Test**: Instantiate `UAT()` against shipped manifests and a fake adapter, confirm it selects a compatible model, delegates prompt generation to the adapter, and returns a normalized `AgentResponse` enriched with parsed UAT evidence metadata.

**Acceptance Scenarios**:

1. **Given** shipped manifests include at least one model with the UAT persona's required capabilities, **When** `UAT()` initializes, **Then** it selects the first compatible manifest via the persona routing layer.
2. **Given** the adapter returns a UAT plan or checklist draft, **When** `respond(...)` completes, **Then** the final persona response preserves the adapter identity while attaching subprocess-backed Evidence Pack data.
3. **Given** the configured UAT skill path is invalid, **When** `respond(...)` is called, **Then** the persona surfaces a clear error instead of emitting a fabricated success response.

### Edge Cases

- What happens when `SPANWEAVE_UAT_SKILL_PATH` points to a missing path, a non-executable file, or a directory without a resolvable entrypoint?
- What happens when `TEST_USER` or `TEST_PASSWORD` are missing from both the packet and the local environment sources?
- How does the runner behave when the subprocess exits successfully but produces a report that is empty or partially unparseable?
- How does the runner preserve stderr separately from stdout when the UAT skill reports failures?
- How does the stage ensure credential values never appear verbatim in Evidence Pack output?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a `UAT` persona in `spanweave/personas/uat.py` that extends the shared `Persona` base.
- **FR-002**: The UAT persona MUST load its system prompt from `.spanweave/defaults/personas/uat.md`.
- **FR-003**: The UAT persona MUST declare capability requirements that allow it to route through the shared persona model-selection contract before any subprocess execution begins.
- **FR-004**: `UAT.respond(context_packet)` MUST delegate to the selected LLM adapter to generate UAT intent or test guidance before launching the subprocess-backed UAT execution.
- **FR-005**: The system MUST provide a subprocess wrapper in `spanweave/personas/uat_runner.py` that resolves the external UAT skill path from `SPANWEAVE_UAT_SKILL_PATH`, defaulting to `/home/fei/fei/code/hackathon/ccc/skills/uat-testing`.
- **FR-006**: The UAT runner MUST accept a target `app_path` and test account credentials and pass them into the subprocess execution context.
- **FR-007**: If the configured UAT skill path is missing, invalid, or not invokable, the runner MUST raise a clear error and MUST NOT silently skip UAT or claim success.
- **FR-008**: The runner MUST capture stdout, stderr, exit code, and command metadata from the subprocess execution.
- **FR-009**: The runner MUST enforce a subprocess timeout and surface timeout failures distinctly from normal non-zero exits.
- **FR-010**: The runner MUST parse the returned UAT report into structured Evidence Pack findings and a human-readable summary.
- **FR-011**: The system MUST provide an Evidence Pack data shape that can carry UAT findings plus execution output for this stage.
- **FR-012**: The runner MUST redact test credentials from any execution output and findings content before constructing the Evidence Pack.
- **FR-013**: Credential resolution MUST prefer explicit packet values, then process environment variables, then repo-relative `../../.env.local`.
- **FR-014**: The UAT persona MUST return a normalized `AgentResponse` that preserves the selected adapter identity and includes the parsed Evidence Pack in response metadata.
- **FR-015**: `tests/test_uat.py` MUST cover capability-routed persona initialization, subprocess invocation, UAT report to Evidence Pack mapping, invalid skill-path failure, and credential redaction.

### Key Entities *(include if feature involves data)*

- **UATRequest**: The context packet consumed by the persona, including the target app path and optional explicit credentials or execution overrides.
- **TestAccountCredentials**: The user/password pair resolved for UAT execution, sourced from the packet, environment, or `.env.local`.
- **UATExecutionResult**: The captured subprocess command, exit status, stdout, stderr, and parsed report summary.
- **Finding**: One structured UAT observation, including severity and verification context that can populate an Evidence Pack.
- **EvidencePack**: The normalized evidence artifact containing summary, findings, and execution output for the UAT stage.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `tests/test_uat.py` passes locally with mocked adapters and mocked subprocess execution.
- **SC-002**: `UAT()` initializes successfully against shipped manifests and records a compatible model through the shared routing layer.
- **SC-003**: A mocked subprocess report containing failing UAT cases is converted into Evidence Pack findings with the expected severities and descriptions.
- **SC-004**: Invoking the runner with an invalid `SPANWEAVE_UAT_SKILL_PATH` raises a clear error instead of producing a silent pass.
- **SC-005**: A subprocess output containing test credentials does not expose those credential values in the resulting Evidence Pack execution output.
- **SC-006**: UAT subprocess execution is bounded by a timeout rather than waiting indefinitely.

## Assumptions

- The external `ccc/skills/uat-testing` asset remains outside this repository, so this feature integrates with it through a configurable path instead of vendoring it.
- The external UAT skill can consume target-app context and credentials from subprocess inputs without requiring Spanweave to reimplement the browser automation itself.
- The UAT slice should integrate with the current Evidence Pack and redaction contracts on `main` rather than forking them again.
- The demo app under `demo/app/` remains the default local target when no alternate app path is supplied by the workflow packet.
