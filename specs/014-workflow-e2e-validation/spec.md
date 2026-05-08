# Feature Specification: Workflow E2E Validation

**Feature Branch**: `014-workflow-e2e-validation`  
**Created**: 2026-04-22  
**Status**: Implemented  
**Input**: User description: "integration tests validating full Spanweave workflow end-to-end + CI pipeline"

## Clarifications

### Session 2026-04-22

- Q: Which LLM mode should CI use for workflow validation? → A: CI uses deterministic mock LLM behavior by default, with real LLM calls enabled only when `SPANWEAVE_INTEGRATION_REAL_LLM=1`.
- Q: What counts as the "full workflow" for Phase 0 validation? → A: Every stage from `speckit-loop.yaml` must execute through the workflow engine and leave the expected filesystem artifacts behind.
- Q: How should repeatability be enforced? → A: Every integration test must create isolated repo-local state and must not depend on cached runs, prior `.spanweave/` contents, or previously generated artifacts.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validate The Full Workflow Run (Priority: P1)

As a maintainer, I can run one deterministic end-to-end integration test against the demo app and demo issue, so Phase 0 has a single proof point that the default Spanweave workflow still works from start to finish.

**Why this priority**: The release gate is whether the shipped workflow actually composes across compiler, personas, workflow state, evidence, ADRs, and git-hygiene stages. Without that proof, the rest of the repo can be green while the real product path is broken.

**Independent Test**: Run the end-to-end integration test in a clean temporary repository and verify it drives `speckit-loop` from `specify` through `cleanup`, producing stage directories, packets, transcripts, evidence files, memory decisions, ADR output, and stage completion markers.

**Acceptance Scenarios**:

1. **Given** the demo issue and demo app fixtures, **When** the mock-driven E2E workflow test runs, **Then** each stage in `speckit-loop.yaml` is created and advanced in order.
2. **Given** that workflow run, **When** the run completes, **Then** every stage directory contains `packet.md`, `transcript.jsonl`, `evidence.md`, and `evidence.json`, and completed stages include `.complete`.
3. **Given** the same completed run, **When** ADR synthesis executes from the recorded memory records, **Then** at least one ADR file is written and references the decisions produced during the run.
4. **Given** the destructive git-hygiene stages, **When** the workflow reaches them, **Then** explicit approvals are still required and the run resumes correctly after approval.

---

### User Story 2 - Verify Component Boundaries In Pairs (Priority: P2)

As a maintainer, I can run focused integration tests across the highest-risk boundaries, so failures show which subsystem contract broke instead of only saying that the whole workflow failed.

**Why this priority**: A single E2E test is necessary but not sufficient. The riskiest integration points still need smaller tests that localize regressions in compiler output, persona handoff, evidence generation, rungraph persistence, and ADR synthesis.

**Independent Test**: Run the component integration test module and verify separate tests cover compiler-to-persona packet handling, persona-to-evidence generation, workflow-to-rungraph progression, and ADR synthesis from memory records.

**Acceptance Scenarios**:

1. **Given** compiled context sources, **When** they are handed to a coder persona harness, **Then** the persona layer receives deterministic packet content and records a transcript entry.
2. **Given** persona output for a stage, **When** the evidence writer runs, **Then** it writes `evidence.md` and `evidence.json` under the current stage and the returned pack matches the stored files.
3. **Given** a workflow engine run, **When** stages advance, **Then** rungraph directories and completion markers reflect the actual transition history.
4. **Given** decision and rejected-alternative memory records from a run, **When** ADR synthesis runs, **Then** it writes a MADR file that uses those records as its source material.

---

### User Story 3 - Keep Validation Running On Every PR (Priority: P3)

As a maintainer, I can run the same validation locally and in GitHub Actions, so every pull request gets the same repeatable Phase 0 gate that I can reproduce from a clean checkout.

**Why this priority**: The tests only protect the branch if they run automatically, and contributors need a single local entrypoint that mirrors CI.

**Independent Test**: From a clean checkout, run `scripts/run-e2e.sh` after `uv sync`, and verify the same integration suite that CI runs completes without relying on pre-existing state.

**Acceptance Scenarios**:

1. **Given** a pull request branch, **When** GitHub Actions starts, **Then** it runs lint, type-checking, unit tests, and integration tests as separate CI checks.
2. **Given** a local developer checkout with dependencies installed, **When** `scripts/run-e2e.sh` runs, **Then** it executes the integration validation with the same default mock mode as CI.
3. **Given** a maintainer with real model credentials, **When** `SPANWEAVE_INTEGRATION_REAL_LLM=1` is set, **Then** the integration fixtures can opt into real persona calls without changing test code or CI defaults.

### Edge Cases

- The integration suite must not reuse `.spanweave/runs/` data from earlier tests or earlier local runs.
- The workflow should still complete when approval-gated stages pause execution and require an explicit resume.
- The component tests must keep passing even if the E2E harness writes richer packet or transcript content later.
- Real-LLM opt-in must skip cleanly when required API keys are absent instead of failing deterministic CI.
- The local E2E script must fail fast with a clear message when `uv` is missing or dependencies have not been installed yet.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `tests/integration/test_e2e_workflow.py` MUST run the shipped `speckit-loop` workflow against the demo issue and demo app using deterministic mock LLM behavior by default.
- **FR-002**: The E2E workflow test MUST verify creation of `run.md`, `workflow_state.yaml`, stage `packet.md`, `transcript.jsonl`, `evidence.md`, `evidence.json`, stage `.complete` markers, and ADR output derived from run memory.
- **FR-003**: The E2E workflow test MUST assert that all stage IDs from `speckit-loop.yaml` appear in the run tree in order.
- **FR-004**: `tests/integration/test_component_integration.py` MUST cover compiler-to-persona, persona-to-evidence, workflow-to-rungraph, and ADR-synthesis integration boundaries.
- **FR-005**: `tests/integration/conftest.py` MUST provide shared isolated fixtures for repo-root setup, deterministic mock LLM behavior, and opt-in real LLM execution controlled by `SPANWEAVE_INTEGRATION_REAL_LLM`.
- **FR-006**: The integration fixtures MUST default to mock mode in CI and MUST not require `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` unless real mode is explicitly enabled.
- **FR-007**: The integration harness MUST be repeatable: every test run starts from a clean temporary workspace and does not depend on pre-existing `.spanweave/` state.
- **FR-008**: The harness MUST use real repository modules for context compilation, workflow advancement, evidence generation, memory persistence, ADR synthesis, and git-hygiene analysis or approval flow instead of asserting against fabricated placeholder paths alone.
- **FR-009**: `.github/workflows/ci.yaml` MUST run on every push and pull request and MUST include separate checks for `ruff`, `pyright`, unit tests, and integration tests.
- **FR-010**: `scripts/run-e2e.sh` MUST provide a one-command local entrypoint that runs the integration validation against a clean checkout after dependencies and environment variables are prepared.
- **FR-011**: The local E2E script and the CI workflow MUST use the same default mock mode so local reproduction matches pull request behavior.
- **FR-012**: Real-LLM integration coverage MUST be opt-in and MUST skip with a clear reason when the required credentials are unavailable.

### Key Entities *(include if feature involves data)*

- **Integration Persona Mode**: The selected execution mode for persona calls, either deterministic mock mode or opt-in real LLM mode.
- **Workflow Artifact Set**: The run-level and stage-level filesystem outputs that prove the workflow executed correctly, including run metadata, packets, transcripts, evidence, completion markers, memory records, and ADRs.
- **Integration Harness**: The shared test fixture layer that composes compiler, persona, workflow, evidence, ADR, and git-hygiene modules into repeatable integration scenarios.
- **CI Validation Gate**: The pull-request automation that runs linting, type-checking, unit tests, and integration tests as the repository’s Phase 0 acceptance pipeline.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running `uv run pytest tests/integration/test_e2e_workflow.py -q` from a clean checkout completes successfully in mock mode and produces a completed run with the expected stage and artifact set.
- **SC-002**: Running `uv run pytest tests/integration/test_component_integration.py -q` passes and covers the four required integration boundaries.
- **SC-003**: Running `uv run pytest tests -q` passes without relying on leftover `.spanweave/` state from previous test runs.
- **SC-004**: GitHub Actions starts on every pull request and push and exposes distinct statuses for lint, type-check, unit tests, and integration tests.
- **SC-005**: Running `scripts/run-e2e.sh` after `uv sync` succeeds locally in default mock mode without requiring manual file cleanup.
- **SC-006**: Setting `SPANWEAVE_INTEGRATION_REAL_LLM=1` enables real-model integration coverage while leaving the default CI path unchanged.

## Assumptions

- The demo app and demo issue under `demo/` remain the canonical Phase 0 fixtures for integration validation.
- Deterministic CI is more important than exercising paid model providers on every pull request.
- Approval-gated workflow stages can be satisfied inside tests by explicit resume calls rather than interactive terminal prompts.
- The integration suite is allowed to write temporary run state, memory records, and ADR files inside isolated temporary repositories during test execution.
