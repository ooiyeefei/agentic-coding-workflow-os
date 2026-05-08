# Implementation Plan: Secret Redaction

**Branch**: `005-secret-redaction` | **Date**: 2026-04-20 | **Spec**: [/home/fei/fei/code/hackathon/acw-w10/specs/006-secret-redaction/spec.md](/home/fei/fei/code/hackathon/acw-w10/specs/006-secret-redaction/spec.md)
**Input**: Feature specification from `/specs/006-secret-redaction/spec.md`

## Summary

Implement a regex-based secret redactor under `spanweave/security/` that provides one pure `redact(...)` entrypoint, ships a named built-in pattern catalog for common secret formats, preserves useful surrounding context such as variable names and URL structure, and supports caller-provided extra regexes with stable audit-visible markers.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Python `re` and `typing` from the standard library, plus `pytest` for validation  
**Storage**: N/A for the redaction function itself; transforms in-memory strings before persistence  
**Testing**: `pytest` with focused positive and negative parameterized cases in `tests/test_redaction.py`  
**Target Platform**: Local developer machines and CI running the Spanweave Python package  
**Project Type**: Shared internal library module  
**Performance Goals**: Redact typical log, transcript, and packet-sized strings in bounded linear passes without network or filesystem work  
**Constraints**: Pure function only; regex-based MVP; keep safe surrounding text visible; no false positives on common English words; use `[REDACTED:<pattern-name>]` markers; treat sensitive environment-variable names case-insensitively  
**Scale/Scope**: One pattern catalog, one redaction module, one focused test file, and 40+ representative test cases across positive and negative paths

## Constitution Check

The repository constitution file is still template text, so there are no enforceable gates to fail. This plan still follows the project direction by keeping the feature filesystem-free, testable, and isolated to a small internal library surface.

## Project Structure

### Documentation (this feature)

```text
specs/006-secret-redaction/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── redaction.md
└── tasks.md
```

### Source Code (repository root)

```text
spanweave/
└── security/
    ├── __init__.py
    ├── patterns.py
    └── redaction.py

tests/
└── test_redaction.py
```

**Structure Decision**: Keep the feature fully contained in `spanweave/security/` with one pattern catalog and one pure redaction module, plus a single focused test module under `tests/`.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
