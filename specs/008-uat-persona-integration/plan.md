# Implementation Plan: UAT Persona Integration

**Branch**: `008-uat-persona-integration` | **Date**: 2026-04-20 | **Spec**: [/home/fei/fei/code/hackathon/acw-w18/specs/008-uat-persona-integration/spec.md](/home/fei/fei/code/hackathon/acw-w18/specs/008-uat-persona-integration/spec.md)
**Input**: Feature specification from `/specs/008-uat-persona-integration/spec.md`

## Summary

Add an Spanweave `UAT` persona that still routes through the shared LLM capability layer for test-planning, then shells out to the user's existing `ccc/skills/uat-testing` asset through a timeout-bounded subprocess wrapper. The wrapper resolves credentials from packet/env/`.env.local`, captures stdout and stderr separately, parses JSON or line-oriented reports into the repository's current Evidence Pack shape, and redacts any credential values before evidence is surfaced.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: pydantic v2, python-frontmatter, pathlib, pytest, pytest-asyncio, Python standard library `subprocess`, `json`, `re`, `os`  
**Storage**: In-memory Pydantic models plus repo-local markdown/YAML files; subprocess evidence kept in memory for this slice  
**Testing**: pytest with mocked `LLMAdapter` instances and mocked subprocess execution  
**Target Platform**: Local developer machines and CI running the Spanweave Python package  
**Project Type**: Shared internal library module  
**Performance Goals**: Persona initialization remains synchronous and lightweight; `respond(...)` performs one adapter round-trip plus one bounded subprocess call; hung UAT is cut off by timeout  
**Constraints**: External UAT skill lives outside this repo; missing skill path must fail clearly; credentials must not be exposed in evidence; implementation should preserve the richer Evidence Pack and redaction contracts already on `main`  
**Scale/Scope**: One new persona, one subprocess runner, one prompt file, one focused test module, and minimal supporting evidence/redaction modules

## Constitution Check

The constitution file is still template text, so there are no enforceable gates to fail. The design still aligns with the repository direction: persona capability routing, execution-backed validation, and credential-safe artifacts.

## Project Structure

### Documentation (this feature)

```text
specs/008-uat-persona-integration/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── uat-persona.md
└── tasks.md
```

### Source Code (repository root)

```text
.spanweave/
└── defaults/
    └── personas/
        └── uat.md

spanweave/
├── evidence/
│   ├── __init__.py
│   └── schema.py
├── personas/
│   ├── __init__.py
│   ├── uat.py
│   └── uat_runner.py
└── security/
    ├── __init__.py
    └── redaction.py

tests/
└── test_uat.py
```

**Structure Decision**: Keep the feature inside the existing persona package, add the minimum adjacent support modules needed to represent evidence and redaction, and avoid broader workflow-engine changes until later issues land.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
