# Implementation Plan: Typed Memory Records

**Branch**: `005-typed-memory-records` | **Date**: 2026-04-20 | **Spec**: [/home/fei/fei/code/hackathon/acw-w06/specs/005-typed-memory-records/spec.md](/home/fei/fei/code/hackathon/acw-w06/specs/005-typed-memory-records/spec.md)
**Input**: Feature specification from `/specs/005-typed-memory-records/spec.md`

## Summary

Implement the knowledge-plane persistence layer in `spanweave/memory/` with strict Pydantic record schemas, a redact-before-write markdown writer using YAML frontmatter plus atomic replacement, and a reader/query surface that reconstructs typed records from `.spanweave/memory/**/*.md` without introducing a database.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: pydantic v2, python-frontmatter, pathlib, pyyaml, python-ulid, pytest  
**Storage**: Markdown files with YAML frontmatter under `.spanweave/memory/{decisions,findings,rejected_alternatives}/`  
**Testing**: pytest round-trip, filter, and redaction tests in `tests/test_memory.py`  
**Target Platform**: Local developer machines and CI running the Spanweave Python package  
**Project Type**: Shared internal library module  
**Performance Goals**: Recursive scans remain fast enough for Phase 0 local repositories; single-record reads and writes stay synchronous and lightweight  
**Constraints**: Filesystem-first only; preserve markdown body formatting; reject schema drift via `extra="forbid"`; apply redaction at write time; use atomic replacement for persistence  
**Scale/Scope**: Three record types, one shared memory package, one supporting redaction shim, and one focused pytest module

## Constitution Check

The repository constitution is still template text, so there are no enforceable gates to fail. The plan still aligns with the documented product direction: typed records first, transcripts second, files as the source of truth, and no database in the core workflow.

## Project Structure

### Documentation (this feature)

```text
specs/005-typed-memory-records/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── memory-records.md
└── tasks.md
```

### Source Code (repository root)

```text
spanweave/
├── memory/
│   ├── __init__.py
│   ├── records.py
│   ├── reader.py
│   └── writer.py
├── security/
│   ├── __init__.py
│   └── redaction.py
└── util/
    ├── fs.py
    └── ulid.py

tests/
└── test_memory.py
```

**Structure Decision**: Keep the feature centered in `spanweave/memory/` and add only one narrow supporting module in `spanweave/security/` because the memory writer cannot meet its acceptance criteria without a reusable redaction entrypoint.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
