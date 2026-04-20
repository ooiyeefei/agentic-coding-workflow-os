# Implementation Plan: Minimal Demo App

**Branch**: `feat/W22-demo-app` | **Date**: 2026-04-19 | **Spec**: [/home/fei/fei/code/hackathon/agentic-coding-workflow-os/worktrees/W22-demo-app/specs/001-minimal-demo-app/spec.md](/home/fei/fei/code/hackathon/agentic-coding-workflow-os/worktrees/W22-demo-app/specs/001-minimal-demo-app/spec.md)
**Input**: Feature specification from `/specs/001-minimal-demo-app/spec.md`

## Summary

Build a small FastAPI demo app under `demo/app/` with a browser login form, an HTTP-only session cookie, a protected notes CRUD API, a minimal notes page for live walkthroughs, and a pytest suite that proves the auth and CRUD flow works locally.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: FastAPI, Jinja2, Uvicorn, pytest, httpx  
**Storage**: In-memory dictionaries for sessions and notes  
**Testing**: pytest with FastAPI `TestClient`  
**Target Platform**: Local developer machine on Linux or macOS  
**Project Type**: Single-service web app with minimal server-rendered HTML  
**Performance Goals**: Login and note CRUD complete interactively on localhost with sub-second responses  
**Constraints**: Keep the codebase small enough to explain end-to-end in 90 seconds; no database; no JWT; no external services  
**Scale/Scope**: One demo account, one process, ephemeral data, one protected resource

## Constitution Check

The repository constitution is still template text, so there are no enforceable gates to fail. The plan still follows the intended direction: small surface area, explicit tests, and minimal moving parts.

## Project Structure

### Documentation (this feature)

```text
specs/001-minimal-demo-app/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── demo-app.openapi.yaml
└── tasks.md
```

### Source Code (repository root)

```text
demo/app/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   ├── store.py
│   └── templates/
│       ├── login.html
│       └── notes.html
├── tests/
│   └── test_app.py
├── .env.example
├── README.md
└── pyproject.toml
```

**Structure Decision**: Use one small Python web app with a tiny package, two templates, and one integration-style test module. This keeps the feature easy to understand while preserving enough separation for auth, storage, UI, and tests.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
