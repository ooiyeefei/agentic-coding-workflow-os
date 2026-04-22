# Implementation Plan: Atelier CLI

**Branch**: `013-atelier-cli` | **Date**: 2026-04-22 | **Spec**: [/home/fei/fei/code/hackathon/acw-w15/specs/013-atelier-cli/spec.md](/home/fei/fei/code/hackathon/acw-w15/specs/013-atelier-cli/spec.md)
**Input**: Feature specification from `/specs/013-atelier-cli/spec.md`

## Summary

Replace the current placeholder CLI scaffold with a real Click-based Atelier command surface that wraps the existing workflow engine, rungraph filesystem state, git cleanup helpers, and truthful placeholder daemon state. Keep human-readable output as the default, add `--json` on structured commands, and enforce explicit confirmation for destructive cleanup.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: click, pathlib, pytest, existing `atelier.workflow`, `atelier.rungraph`, `atelier.audit`, and `atelier.git` modules  
**Storage**: Filesystem-only repo-local state under `.atelier/` plus shipped defaults under the package's `.atelier/defaults/` tree  
**Testing**: pytest with `click.testing.CliRunner`, temporary repositories, and repository-scoped placeholder daemon state checks  
**Target Platform**: Local developer machines and CI invoking the installed `atelier` console script  
**Project Type**: CLI surface over internal library modules  
**Performance Goals**: `atelier --help`, `run list`, and `run show` should feel instantaneous on small Phase 0 repos and should not pull in heavy runtime dependencies just to print help or inspect state  
**Constraints**: Prefer Click over Typer; default to human output with opt-in `--json`; destructive cleanup requires confirmation; repo selection must stay explicit via `--repo`; W15 must not depend on W16 being implemented  
**Scale/Scope**: One root CLI entrypoint, one shared formatter module, seven command modules, and one focused CLI test module; no new persistence layer and no daemon server implementation changes outside the CLI wrapper

## Constitution Check

The repository constitution is still template text, so there are no enforceable gates to fail. This plan still aligns with the repo's real Phase 0 constraints from `phase0_launch.md`: the CLI is the primary product surface, all persistent state stays filesystem-first under `.atelier/`, and destructive actions remain human-gated and confirmation-safe.

## Project Structure

### Documentation (this feature)

```text
specs/013-atelier-cli/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── cli.md
└── tasks.md
```

### Source Code (repository root)

```text
atelier/
├── cli/
│   ├── __init__.py
│   ├── main.py
│   ├── formatters.py
│   └── commands/
│       ├── __init__.py
│       ├── cleanup.py
│       ├── daemon.py
│       ├── grep.py
│       ├── init.py
│       ├── list.py
│       ├── run.py
│       └── show.py
├── git/
│   └── cleanup.py
├── rungraph/
│   └── tree.py
└── workflow/
    ├── engine.py
    └── loader.py

tests/
└── test_cli.py
```

**Structure Decision**: Keep W15 implementation inside `atelier/cli/`, with one module per command surface and a shared formatter layer for human vs JSON output. Reuse existing workflow, rungraph, audit, and git helpers instead of adding a separate service or persistence abstraction.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
