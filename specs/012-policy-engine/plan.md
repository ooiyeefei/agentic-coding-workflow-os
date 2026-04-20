# Implementation Plan: Policy Engine

**Branch**: `012-policy-engine` | **Date**: 2026-04-20 | **Spec**: [/home/fei/fei/code/hackathon/acw-w12/specs/012-policy-engine/spec.md](/home/fei/fei/code/hackathon/acw-w12/specs/012-policy-engine/spec.md)
**Input**: Feature specification from `/specs/012-policy-engine/spec.md`

## Summary

Implement a hardcoded Phase 0 policy layer under `atelier/policy/` that isolates approval-gate decisions, conservative dry-run defaults for git mutations, and filesystem-only cost cap checks backed by W13-style audit JSONL aggregation.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: pydantic v2, pathlib, pytest  
**Storage**: Filesystem JSONL audit logs under `.atelier/runs/` and `.atelier/audit/`  
**Testing**: pytest with temporary audit log fixtures and focused boundary assertions  
**Target Platform**: Local developer machines and CI running the Atelier Python package  
**Project Type**: Shared internal library module  
**Performance Goals**: Policy checks remain synchronous and complete in milliseconds on small Phase 0 audit logs  
**Constraints**: No network calls, no database, hardcoded defaults only, and exact cap boundary behavior must be deterministic  
**Scale/Scope**: One policy engine, one cost tracker, one defaults module, one test module, and minimal package exports

## Constitution Check

The repository constitution is still template text, so there are no enforceable gates to fail. This plan still matches the repo's stated constraints: filesystem-first state, conservative destructive-operation controls, and explicit cost governance.

## Project Structure

### Documentation (this feature)

```text
specs/012-policy-engine/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── policy.md
└── tasks.md
```

### Source Code (repository root)

```text
atelier/
├── policy/
│   ├── __init__.py
│   ├── cost_tracker.py
│   ├── defaults.py
│   └── engine.py
└── util/
    └── paths.py

tests/
└── test_policy.py
```

**Structure Decision**: Keep all policy logic inside `atelier/policy/`, reuse `atelier.util.paths.audit_log_path` for run-scoped audit log lookup, and verify the slice through a single focused test module.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
