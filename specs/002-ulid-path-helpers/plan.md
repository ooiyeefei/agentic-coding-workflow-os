# Implementation Plan: ULID Path Helpers

**Branch**: `002-ulid-path-helpers` | **Date**: 2026-04-20 | **Spec**: [/home/fei/fei/code/hackathon/acw-w03/specs/002-ulid-path-helpers/spec.md](/home/fei/fei/code/hackathon/acw-w03/specs/002-ulid-path-helpers/spec.md)
**Input**: Feature specification from `/specs/002-ulid-path-helpers/spec.md`

## Summary

Implement the foundational `atelier.util` package so later worktrees can generate prefixed ULID identifiers, derive canonical `.atelier/runs/...` paths through validated `Path` objects, and perform same-directory atomic replacement without risking partial overwrite corruption of existing artifacts.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: pydantic v2, python-ulid, pathlib, pytest  
**Storage**: Local filesystem under `.atelier/`  
**Testing**: pytest, unittest.mock, coverage via `pytest --cov=atelier.util`  
**Target Platform**: Cross-platform local development environments using Python filesystem APIs  
**Project Type**: Shared internal library module  
**Performance Goals**: ID and path helper calls complete synchronously with negligible overhead; generated IDs lex-sort by creation order; failed final replacement steps never mutate the destination content  
**Constraints**: Keep the public API small; use `Path` throughout path helpers; avoid manual path string concatenation; create temporary files in the destination directory; reach 100% coverage for `atelier/util/`  
**Scale/Scope**: Six entity ID generators, seven canonical path helpers, and two filesystem helpers used by many downstream modules

## Constitution Check

The repository constitution is still template text, so there are no enforceable gates to fail. This plan still follows the intended direction: a small shared library, deterministic behavior, and strong automated verification.

## Project Structure

### Documentation (this feature)

```text
specs/002-ulid-path-helpers/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── util-api.md
└── tasks.md
```

### Source Code (repository root)

```text
atelier/
└── util/
    ├── __init__.py
    ├── fs.py
    ├── paths.py
    └── ulid.py

tests/
├── conftest.py
├── test_fs.py
├── test_paths.py
└── test_ulid.py
```

**Structure Decision**: Keep all new production code inside `atelier/util/` and all verification in dedicated top-level pytest modules. This matches the current repository layout and isolates the foundational utility surface cleanly.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
