# Implementation Plan: Run Graph Tree Ops

**Branch**: `005-rungraph-tree-ops` | **Date**: 2026-04-20 | **Spec**: [/home/fei/fei/code/hackathon/acw-w09/specs/007-rungraph-tree-ops/spec.md](/home/fei/fei/code/hackathon/acw-w09/specs/007-rungraph-tree-ops/spec.md)
**Input**: Feature specification from `/specs/007-rungraph-tree-ops/spec.md`

## Summary

Implement the filesystem-backed run graph module under `atelier/rungraph/` so the workflow engine can create canonical `.atelier/runs/<run_id>/` trees, create ordered stage directories, mark stage completion, resume from the first incomplete stage, and serialize writers with reclaimable per-run file locks.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: pathlib, pydantic v2, python-ulid, pytest, pytest-asyncio, standard-library `fcntl`, existing `atelier.util.fs` helpers  
**Storage**: Filesystem-only state under `.atelier/runs/<run_id>/...` matching the roadmap's canonical storage layout  
**Testing**: pytest unit tests plus subprocess-based lock contention checks in `tests/test_rungraph.py`  
**Target Platform**: Local Linux or Unix-like developer machines and CI running the Atelier Python package  
**Project Type**: Shared internal library module for workflow persistence  
**Performance Goals**: Run and stage creation stay lightweight and synchronous; resume scanning is linear in stage count; lock acquisition blocks correctly without busy looping  
**Constraints**: Preserve the roadmap's `.atelier` storage layout; stage identifiers are sequence-prefixed slugs such as `001-specify`; stages without completion markers must be restartable; lock files live at `.atelier/runs/<run_id>/.lock`; no new third-party locking dependency is required  
**Scale/Scope**: One new `atelier/rungraph/` slice with three modules, one focused test file, and minimal supporting exports required to make file tree creation, resume scanning, and locking verifiable

## Constitution Check

The repository constitution is still template text, so there are no enforceable gates to fail. This plan still follows the repo's stated principles: filesystem-first storage, reproducible run lineage, and evidence-friendly explicit state on disk.

## Project Structure

### Documentation (this feature)

```text
specs/007-rungraph-tree-ops/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── rungraph.md
└── tasks.md
```

### Source Code (repository root)

```text
.atelier/
└── runs/
    └── <run_id>/
        ├── .lock
        ├── run.md
        ├── audit.jsonl
        └── stages/
            └── <nnn-stage-name>/
                ├── stage.md
                ├── packet.md
                ├── transcript.jsonl
                ├── evidence.md
                ├── evidence.json
                ├── .complete
                ├── decisions/
                └── findings/

atelier/
├── rungraph/
│   ├── __init__.py
│   ├── cursor.py
│   ├── lock.py
│   └── tree.py
└── util/
    ├── fs.py
    ├── paths.py
    └── ulid.py

tests/
├── conftest.py
└── test_rungraph.py
```

**Structure Decision**: Keep the new behavior isolated in `atelier/rungraph/`, reuse existing filesystem and ULID helpers from `atelier/util/`, and validate the public behavior through one focused end-to-end test module that inspects the real `.atelier/runs/` tree in a temporary working directory.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
