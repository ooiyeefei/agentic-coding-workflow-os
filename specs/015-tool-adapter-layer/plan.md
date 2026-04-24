# Implementation Plan: Tool Adapter Layer

**Branch**: `015-tool-adapter-layer` | **Date**: 2026-04-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/015-tool-adapter-layer/spec.md`

## Summary

Build a shared adapter layer under `atelier/adapters/` that can ingest Claude Code and Codex session transcripts into typed memory records, format tool-specific context packets from stored memory, detect the active tool environment, and validate tool manifests with deterministic tests and fixture data.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: pydantic v2, pathlib, pyyaml, python-frontmatter, pytest  
**Storage**: Filesystem JSONL transcripts, repo-local markdown memory records, YAML manifests  
**Testing**: pytest with fixture transcript files and temporary repositories  
**Target Platform**: Local developer machines and CI running the Atelier Python package  
**Project Type**: Shared internal library module  
**Performance Goals**: Transcript normalization and heuristic extraction stay fast for local session logs and do not require live model calls  
**Constraints**: Phase 0 must stay offline-safe in tests; adapter outputs must reuse existing memory schemas and run-state files; tool detection should avoid false positives  
**Scale/Scope**: One base adapter contract, three concrete adapters, two YAML manifests, one test module, and fixture transcripts for Claude Code, Codex, and generic markdown

## Constitution Check

The repository constitution remains template text, so there are no enforceable gates to fail. The plan still aligns with the roadmap direction: transcripts feed typed filesystem memory, and packets target tool conventions without turning Atelier into a direct agent runtime.

## Project Structure

### Documentation (this feature)

```text
specs/015-tool-adapter-layer/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── tool-adapters.md
└── tasks.md
```

### Source Code (repository root)

```text
atelier/
├── adapters/
│   ├── __init__.py
│   ├── base.py
│   ├── claude_code.py
│   ├── codex.py
│   ├── generic.py
│   └── manifests/
│       ├── claude-code.yaml
│       └── codex.yaml
├── cli/
│   └── commands/
│       └── run.py
├── memory/
│   ├── reader.py
│   ├── records.py
│   └── writer.py
└── util/
    └── ulid.py

tests/
├── fixtures/
│   └── adapters/
│       ├── claude/
│       ├── codex/
│       └── generic/
└── test_adapters.py
```

**Structure Decision**: Keep the implementation isolated in `atelier/adapters/` and reuse existing memory, run-state, and filesystem helpers rather than adding a second packet or persistence stack.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
