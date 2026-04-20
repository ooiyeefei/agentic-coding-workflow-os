# Implementation Plan: Context Compiler

**Branch**: `006-context-compiler` | **Date**: 2026-04-20 | **Spec**: [/home/fei/fei/code/hackathon/acw-w07/specs/006-context-compiler/spec.md](/home/fei/fei/code/hackathon/acw-w07/specs/006-context-compiler/spec.md)
**Input**: Feature specification from `/specs/006-context-compiler/spec.md`

## Summary

Implement `atelier/compiler/` as the packet assembly layer that converts an objective plus prioritized context sources into deterministic markdown packets with exact `source_id` deduplication, token-budget enforcement, and explicit provenance in both a sidecar model and a footer block.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: pydantic v2, pathlib, pytest  
**Storage**: In-memory source models and markdown strings; optional filesystem paths only as provenance metadata  
**Testing**: pytest unit tests with deterministic fixture sources  
**Target Platform**: Local developer machines and CI running the Atelier Python package  
**Project Type**: Shared internal library module  
**Performance Goals**: Compile Phase 0 packets synchronously and deterministically in one process; keep packet assembly lightweight enough for repeated local use; support at least the acceptance-case `8000` token budget without nonlinear work  
**Constraints**: Exact `source_id` dedupe only for Phase 0; token estimate uses `ceil(len(text) * 4 / 3)`; `must` content is never dropped; provenance footer must stay deterministic and human-readable; no source fetching or tokenizer integration in this slice  
**Scale/Scope**: One compiler package with four new modules, eight typed source variants, one focused test module, and a small public API surface centered on `compile_packet(...)`

## Constitution Check

The repository constitution is still template text, so there are no enforceable gates to fail. The plan still aligns with the project direction in this repo: small library modules, deterministic local behavior, and tests that prove the public contract directly.

## Project Structure

### Documentation (this feature)

```text
specs/006-context-compiler/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── compiler.md
└── tasks.md
```

### Source Code (repository root)

```text
atelier/
└── compiler/
    ├── __init__.py
    ├── budget.py
    ├── compiler.py
    ├── provenance.py
    └── sources.py

tests/
└── test_compiler.py
```

**Structure Decision**: Keep the packet engine isolated inside `atelier/compiler/` so source typing, budget logic, provenance formatting, and compilation orchestration remain cohesive and can be tested through one focused unit module without affecting unrelated packages.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
