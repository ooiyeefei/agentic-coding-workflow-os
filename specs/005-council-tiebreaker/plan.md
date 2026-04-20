# Implementation Plan: Council Tiebreaker

**Branch**: `005-council-tiebreaker` | **Date**: 2026-04-20 | **Spec**: [/home/fei/fei/code/hackathon/acw-w21/specs/005-council-tiebreaker/spec.md](/home/fei/fei/code/hackathon/acw-w21/specs/005-council-tiebreaker/spec.md)
**Input**: Feature specification from `/specs/005-council-tiebreaker/spec.md`

## Summary

Implement a minimal council module under `atelier/council/` that sends the Coder and Reviewer positions to three capability-checked W02 adapters in parallel, tallies the majority verdict or escalates to `HUMAN_REQUIRED`, and persists an auditable `CouncilReport` under `.atelier/memory/council_reports/`.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: pydantic v2, asyncio, pathlib, python-frontmatter, pyyaml, pytest, pytest-asyncio  
**Storage**: Filesystem-backed council report records under `.atelier/memory/council_reports/` plus in-process Pydantic models  
**Testing**: pytest with mocked adapters, mocked manifests, and async timing checks  
**Target Platform**: Local developer machines and CI running the Atelier Python package  
**Project Type**: Shared internal library module  
**Performance Goals**: All three voter requests dispatch concurrently; council overhead remains negligible beyond the three provider calls; tests stay fully offline  
**Constraints**: Exactly three distinct voters; no silent capability downgrade; strict tool-submitted verdict parsing; filesystem-first audit record; full MAD and anonymized debate remain out of scope  
**Scale/Scope**: One council schema module, one council runtime module, one minimal memory writer helper, and one focused council test module

## Constitution Check

The repository constitution is still template text, so there are no enforceable gates to fail. The plan still aligns with the documented project direction: filesystem-first persistence, LLM-agnostic routing, explicit human escalation on unresolved ties, and evidence-backed decision traces.

## Project Structure

### Documentation (this feature)

```text
specs/005-council-tiebreaker/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── council.md
└── tasks.md
```

### Source Code (repository root)

```text
.atelier/
└── defaults/
    └── models/
        ├── claude-opus-4-7.yaml
        ├── claude-sonnet-4-6.yaml
        └── gpt-5.yaml

atelier/
├── council/
│   ├── __init__.py
│   ├── schema.py
│   └── tiebreaker.py
├── llm/
│   ├── adapter.py
│   ├── capabilities.py
│   ├── anthropic.py
│   └── openai.py
└── memory/
    ├── __init__.py
    └── council.py

tests/
└── test_council.py
```

**Structure Decision**: Keep the voting protocol isolated inside `atelier/council/`, reuse W02 manifests and adapters directly, and add only a narrow council-specific persistence helper under `atelier/memory/` so the feature remains auditable without implementing the whole W06 record system.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
