# Implementation Plan: Persona Library

**Branch**: `004-persona-library` | **Date**: 2026-04-20 | **Spec**: [/home/fei/fei/code/hackathon/agentic-coding-workflow-os/specs/004-persona-library/spec.md](/home/fei/fei/code/hackathon/agentic-coding-workflow-os/specs/004-persona-library/spec.md)
**Input**: Feature specification from `/specs/004-persona-library/spec.md`

## Summary

Implement a persona library under `spanweave/personas/` that loads prompt definitions from markdown frontmatter, routes Coder and Reviewer through W02's capability matcher, returns one structured `AgentResponse` shape from `respond(...)`, and preserves the Reviewer's execution-mandatory protocol with an opt-in devil's-advocate prompt extension.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: pydantic v2, python-frontmatter, pathlib, pyyaml, pytest, pytest-asyncio  
**Storage**: Versioned markdown and YAML files under `.spanweave/defaults/` plus local Python modules under `spanweave/`  
**Testing**: pytest with mocked `LLMAdapter` implementations and focused prompt assertions  
**Target Platform**: Local developer machines and CI running the Spanweave Python package  
**Project Type**: Shared internal library module  
**Performance Goals**: Persona initialization remains synchronous and lightweight; no network call during default routing; `respond(...)` only performs one adapter round-trip per invocation  
**Constraints**: Route through W02 instead of hardcoding models; keep adapter construction injectable for tests; Reviewer prompt must use imperative execution language; Coder must operate before W05 lands by using a fallback Speckit sequence  
**Scale/Scope**: Two personas, one shared base contract, two prompt files, one focused test module, and minimal manifest metadata updates needed to satisfy Reviewer's declared requirements

## Constitution Check

The repository constitution is still template text, so there are no enforceable gates to fail. The plan still aligns with the repository's stated direction: LLM-agnostic routing, execution-backed review discipline, and filesystem-first defaults.

## Project Structure

### Documentation (this feature)

```text
specs/004-persona-library/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── personas.md
└── tasks.md
```

### Source Code (repository root)

```text
.spanweave/
└── defaults/
    ├── models/
    │   ├── claude-haiku-4-5.yaml
    │   ├── claude-opus-4-7.yaml
    │   ├── claude-sonnet-4-6.yaml
    │   ├── gpt-4o-mini.yaml
    │   └── gpt-5.yaml
    └── personas/
        ├── coder.md
        └── reviewer.md

spanweave/
├── llm/
│   ├── adapter.py
│   └── capabilities.py
└── personas/
    ├── __init__.py
    ├── base.py
    ├── coder.py
    └── reviewer.py

tests/
├── test_llm_adapter.py
└── test_personas.py
```

**Structure Decision**: Keep persona logic isolated inside `spanweave/personas/`, store shipped prompt definitions in `.spanweave/defaults/personas/`, and make only the minimal adjacent updates in `spanweave/llm/` and `.spanweave/defaults/models/` that are necessary for genuine capability-gated routing on default manifests.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
