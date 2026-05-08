# Implementation Plan: Persona Tool Callers

**Branch**: `016-persona-tool-callers` | **Date**: 2026-04-24 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/016-persona-tool-callers/spec.md`

## Summary

Add two `PersonaCaller` implementations: `AgentToolCaller` for main workflow stages that generates paste-ready prompts for agent tools, and `DirectAPICaller` for compatibility paths that keep existing direct LLM persona behavior. Refactor `Persona.respond()` to delegate to direct caller behavior by default and add `respond_via_tool()` for prompt generation. Wire default workflow dependencies to use agent-tool calling while preserving explicit dependency injection in tests and callers.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: pydantic v2, python-frontmatter, pathlib, existing Spanweave persona/workflow/adapter modules  
**Storage**: Filesystem prompts/persona definitions and in-memory caller results; no new persistence  
**Testing**: pytest, pytest-asyncio  
**Target Platform**: Local developer CLI/library execution  
**Project Type**: Python library/CLI workflow tool  
**Performance Goals**: Prompt generation should be synchronous and avoid network calls for agent-tool stages  
**Constraints**: Preserve `PersonaCaller` protocol, preserve direct API test compatibility, avoid rewriting council or ADR internals  
**Scale/Scope**: One caller module, small persona base refactor, workflow default dependency wiring, focused tests

## Constitution Check

The constitution template still contains placeholders and imposes no concrete gates for this feature.

## Project Structure

### Documentation (this feature)

```text
specs/016-persona-tool-callers/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md
```

### Source Code (repository root)

```text
spanweave/
├── personas/
│   ├── base.py
│   └── callers.py
└── workflow/
    └── engine.py

tests/
├── test_persona_callers.py
├── test_personas.py
└── test_workflow.py
```

**Structure Decision**: Use the existing single-package Python layout under `spanweave/` and focused pytest files under `tests/`.

## Complexity Tracking

No constitution violations or added complexity exceptions.
