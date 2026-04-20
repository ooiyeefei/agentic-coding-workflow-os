# Implementation Plan: Evidence Pack

**Branch**: `006-evidence-pack` | **Date**: 2026-04-20 | **Spec**: [/home/fei/fei/code/hackathon/acw-w08/specs/006-evidence-pack/spec.md](/home/fei/fei/code/hackathon/acw-w08/specs/006-evidence-pack/spec.md)
**Input**: Feature specification from `/specs/006-evidence-pack/spec.md`

## Summary

Add a first-class `atelier.evidence` module that validates Evidence Pack payloads with Pydantic, renders a stable human-readable Markdown report through Jinja2, redacts captured command output before persistence, and writes JSON plus Markdown together into the canonical `.atelier/runs/<run_id>/stages/<stage_id>/` tree.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: pydantic v2, jinja2, pathlib, python-ulid  
**Storage**: Local filesystem under `.atelier/runs/<run_id>/stages/<stage_id>/`  
**Testing**: pytest with deterministic fixtures and golden-file comparison  
**Target Platform**: Cross-platform local development environments  
**Project Type**: Shared internal library module  
**Performance Goals**: Synchronous generation with negligible overhead for individual review artifacts; deterministic output for fixed inputs  
**Constraints**: Preserve canonical run-tree paths; reject unsafe stage identifiers; keep Markdown readable in plain terminals; avoid mismatched JSON and Markdown writes  
**Scale/Scope**: One schema module, one generator, one template, and one focused pytest module covering round-trip, rendering, and write behavior

## Constitution Check

The repository constitution remains template text, so there are no enforceable gates to fail. This plan still follows the intended project direction: filesystem-first persistence, explicit contracts, and strong automated verification.

## Project Structure

### Documentation (this feature)

```text
specs/006-evidence-pack/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── evidence-pack.md
└── tasks.md
```

### Source Code (repository root)

```text
atelier/
├── evidence/
│   ├── __init__.py
│   ├── generator.py
│   ├── schema.py
│   └── templates/
│       └── evidence.md.j2
└── util/
    ├── fs.py
    ├── paths.py
    └── ulid.py

tests/
├── golden/
│   └── evidence.md
└── test_evidence.py
```

**Structure Decision**: Keep all production code within `atelier/evidence/`, reuse existing utility helpers for run-root validation and atomic file operations where possible, and isolate evidence verification in one dedicated pytest module with a checked-in Markdown golden file.

## Complexity Tracking

No constitution violations or exceptional complexity expected. The only non-trivial area is transactional replacement of two output files, which is necessary to avoid mismatched artifacts.
