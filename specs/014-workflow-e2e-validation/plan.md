# Implementation Plan: Workflow E2E Validation

**Branch**: `014-workflow-e2e-validation` | **Date**: 2026-04-22 | **Spec**: [/home/fei/fei/code/hackathon/acw-w24/specs/014-workflow-e2e-validation/spec.md](/home/fei/fei/code/hackathon/acw-w24/specs/014-workflow-e2e-validation/spec.md)
**Input**: Feature specification from `/specs/014-workflow-e2e-validation/spec.md`

## Summary

Add a deterministic integration harness that composes the real Atelier compiler, persona, workflow, evidence, memory, ADR, and git modules into repeatable end-to-end validation against the demo issue and demo app. Back that harness with focused component integration tests, a one-command local E2E script, and a GitHub Actions workflow that runs lint, type-checking, unit tests, and integration tests on every PR.

## Technical Context

**Language/Version**: Python 3.11 plus Bash for the local runner  
**Primary Dependencies**: pytest, pytest-asyncio, pathlib, subprocess, existing `atelier.compiler`, `atelier.personas`, `atelier.workflow`, `atelier.evidence`, `atelier.memory`, `atelier.adr`, and `atelier.git` modules  
**Storage**: Temporary filesystem state under `.atelier/runs/`, `.atelier/memory/`, and `docs/adr/` inside isolated test repositories  
**Testing**: pytest integration modules, temporary git repositories, and one GitHub Actions workflow that mirrors local validation  
**Target Platform**: Local developer machines and GitHub Actions Ubuntu runners  
**Project Type**: Filesystem-first Python library with CLI-adjacent integration validation  
**Performance Goals**: Default mock-mode integration validation should finish in a few minutes in CI and should not require external model providers  
**Constraints**: Mock by default for determinism and cost; real LLM mode only when `ATELIER_INTEGRATION_REAL_LLM=1`; no shared state across tests; approval-gated stages remain explicit; the local script must work from a clean checkout after `uv sync`  
**Scale/Scope**: Three integration-owned test files, one CI workflow, one local runner script, and a feature-local documentation set; no new production persistence layer or new workflow stage types

## Constitution Check

The repository constitution is still template text, so there are no enforceable gates to fail. This plan still matches the real Phase 0 goals from `phase0_plan.md`: prove the shipped workflow works against a real example issue, keep state filesystem-first, require human approval at destructive gates, and make the validation replayable in both local development and CI.

## Project Structure

### Documentation (this feature)

```text
specs/014-workflow-e2e-validation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── integration-suite.md
└── tasks.md
```

### Source Code (repository root)

```text
.github/
└── workflows/
    └── ci.yaml

scripts/
└── run-e2e.sh

tests/
├── conftest.py
├── integration/
│   ├── conftest.py
│   ├── test_component_integration.py
│   └── test_e2e_workflow.py
├── test_adr.py
├── test_compiler.py
├── test_git.py
├── test_personas.py
├── test_uat.py
└── test_workflow.py

atelier/
├── adr/
├── compiler/
├── evidence/
├── git/
├── memory/
├── personas/
└── workflow/
```

**Structure Decision**: Keep all new implementation under `tests/integration/`, `.github/workflows/`, and `scripts/`. The feature is a validation layer, so the production modules stay the system under test while the integration harness composes them through their public APIs.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
