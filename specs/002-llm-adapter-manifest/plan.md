# Implementation Plan: LLM Adapter Manifest

**Branch**: `acw-w02` | **Date**: 2026-04-20 | **Spec**: [/home/fei/fei/code/hackathon/acw-w02/specs/002-llm-adapter-manifest/spec.md](/home/fei/fei/code/hackathon/acw-w02/specs/002-llm-adapter-manifest/spec.md)
**Input**: Feature specification from `/specs/002-llm-adapter-manifest/spec.md`

## Summary

Build a provider-neutral LLM adapter layer under `atelier/llm/` with Anthropic and OpenAI implementations, YAML-backed capability manifests, deterministic capability routing, and mocked tests that verify normalized response handling and per-call cost accounting.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: anthropic, openai, pydantic, pyyaml, pytest, pytest-asyncio  
**Storage**: Versioned YAML files under `.atelier/defaults/models/`  
**Testing**: pytest with `AsyncMock`-backed SDK clients  
**Target Platform**: Local developer machine and CI on Linux or macOS  
**Project Type**: Python library package  
**Performance Goals**: Unit tests complete quickly without live API calls; capability routing and response normalization remain O(n) over available manifests  
**Constraints**: No hardcoded default model ids outside manifest YAMLs; adapters must return the same response shape across providers; capability mismatch raises before network use  
**Scale/Scope**: Two provider adapters, five default manifests, one routing function, one focused test module

## Constitution Check

The repository constitution is still template text, so there are no enforceable gates to fail. The plan still aligns with the roadmap's agent-agnostic and files-first principles by keeping model selection declarative and provider-specific behavior behind a normalized contract.

## Project Structure

### Documentation (this feature)

```text
specs/002-llm-adapter-manifest/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── llm-adapter.md
└── tasks.md
```

### Source Code (repository root)

```text
.atelier/
└── defaults/
    └── models/
        ├── claude-haiku-4-5.yaml
        ├── claude-opus-4-7.yaml
        ├── claude-sonnet-4-6.yaml
        ├── gpt-4o-mini.yaml
        └── gpt-5.yaml

atelier/
└── llm/
    ├── __init__.py
    ├── adapter.py
    ├── anthropic.py
    ├── capabilities.py
    └── openai.py

tests/
└── test_llm_adapter.py
```

**Structure Decision**: Keep the slice focused inside `atelier/llm/` with one shared contract module, one manifest module, and one adapter module per provider. Put shipped model manifests in `.atelier/defaults/models/` so routing data remains declarative and version-controlled.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
