# Research: Workflow E2E Validation

## Decision 1: Default The Integration Harness To Deterministic Mock Mode

- **Decision**: Use deterministic mock persona behavior and deterministic UAT subprocess output by default for integration tests and CI.
- **Rationale**: The acceptance criteria require repeatability, PR safety, and low cost. A mock-first harness keeps failures attributable to repository changes instead of provider latency, quota, or prompt drift.
- **Alternatives considered**:
  - Real LLM calls on every run: rejected because CI would become nondeterministic, slower, and credential-dependent.
  - Pure unit-style fakes with no real module composition: rejected because the feature specifically needs integration evidence across the real filesystem and workflow modules.

## Decision 2: Keep Real LLM Coverage As An Explicit Opt-In

- **Decision**: Gate real persona calls behind `SPANWEAVE_INTEGRATION_REAL_LLM=1` and skip cleanly when required provider credentials are absent.
- **Rationale**: Maintainers still need a way to smoke-test real model routing, but that path must not alter CI defaults or break contributor workflows.
- **Alternatives considered**:
  - No real-LLM mode at all: rejected because the issue explicitly asks for an opt-in path.
  - Provider-specific separate test files: rejected because the same fixture layer can switch modes without duplicating the integration scenarios.

## Decision 3: Compose Real Modules In The Test Harness Instead Of Adding New Production Plumbing

- **Decision**: Build the integration harness inside `tests/integration/conftest.py`, where helper classes drive the workflow engine while writing packets, transcripts, evidence artifacts, memory records, ADRs, and git-hygiene outputs through existing repository modules.
- **Rationale**: The current production engine owns stage transitions and rungraph state but intentionally does not know how to render packets, transcripts, or ADRs. The test harness can prove those modules compose correctly without expanding production scope just to satisfy test setup.
- **Alternatives considered**:
  - Adding production-only orchestration glue before W24: rejected because it changes the product surface late in Phase 0.
  - Asserting only on placeholder files created by rungraph: rejected because it would not validate evidence generation, memory persistence, or ADR synthesis.

## Decision 4: Split CI Into Distinct Validation Jobs

- **Decision**: Run `ruff`, `pyright`, unit tests, and integration tests as separate GitHub Actions jobs within one workflow.
- **Rationale**: Separate jobs make failures legible, keep the PR gate aligned with the acceptance criteria, and let faster checks finish independently of the slower integration path.
- **Alternatives considered**:
  - One monolithic CI step: rejected because it obscures which gate failed and makes reruns more expensive.
  - Multiple workflows: rejected because one workflow is simpler to maintain while still surfacing separate statuses.
