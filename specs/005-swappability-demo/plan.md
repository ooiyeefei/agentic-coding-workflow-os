# Implementation Plan: Swappability Demo

**Branch**: `005-swappability-demo` | **Date**: 2026-04-20 | **Spec**: [spec.md](/home/fei/fei/code/hackathon/acw-w19/specs/005-swappability-demo/spec.md)
**Input**: Feature specification from `/specs/005-swappability-demo/spec.md`

## Summary

Build a demo-focused review runner under `demo/` that reuses Spanweave's shipped Reviewer prompt body, executes the same tool-driven review loop against a Claude manifest and a Codex/OpenAI manifest, writes one Markdown Evidence Pack per backend, surfaces an `UnsupportedCapabilityError` path for a tool-less manifest, and ships a narration script that fits inside the live demo slot.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: anthropic SDK, openai SDK, pydantic v2, python-frontmatter, pathlib, pytest  
**Storage**: Filesystem outputs under `demo/swap-demo-output/` and generated fixture files inside the demo workspace  
**Testing**: `pytest` for focused helper coverage plus direct script execution in mock mode and, when credentials exist, live mode  
**Target Platform**: Local developer machines and Phase 0 demo environments running the Spanweave repo  
**Project Type**: Demo script plus checked-in markdown artifacts  
**Performance Goals**: Default run completes quickly enough for live demo use; mock mode should finish in a few seconds and live mode should stay comfortably inside a normal demo beat  
**Constraints**: Keep the same reviewer prompt body and tool contract across both backends; do not change W04's default Reviewer routing contract; require `tool_use=True`; keep model swapping configurable; preserve a no-credentials path so the repo asset still runs in review environments  
**Scale/Scope**: One Python demo script, one narration markdown file, two generated Evidence Packs, one runtime fixture workspace, and one focused test module

## Constitution Check

The constitution file is still template text, so there are no enforceable gates to fail. The plan still follows the repo's stated direction: filesystem-first artifacts, capability-gated swappability, and execution-backed review evidence.

## Project Structure

### Documentation (this feature)

```text
specs/005-swappability-demo/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── swap-demo.md
└── tasks.md
```

### Source Code (repository root)

```text
demo/
├── swap-demo.md
├── swap-demo.py
└── swap-demo-output/
    ├── claude/
    │   └── evidence.md
    ├── codex/
    │   └── evidence.md
    └── workspace/
        ├── fixture.py
        └── test_fixture.py

tests/
└── test_swap_demo.py
```

**Structure Decision**: Keep W19 self-contained under `demo/` so the asset stays easy to run and easy to present, and add one focused test module in `tests/` for the review-loop helpers, manifest guardrail, and evidence rendering behavior.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
