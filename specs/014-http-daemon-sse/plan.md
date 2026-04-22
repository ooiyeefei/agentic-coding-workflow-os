# Implementation Plan: HTTP Daemon + SSE

**Branch**: `014-http-daemon-sse` | **Date**: 2026-04-22 | **Spec**: [/home/fei/fei/code/hackathon/acw-w16/specs/014-http-daemon-sse/spec.md](/home/fei/fei/code/hackathon/acw-w16/specs/014-http-daemon-sse/spec.md)
**Input**: Feature specification from `/specs/014-http-daemon-sse/spec.md`

## Summary

Add a localhost-only FastAPI daemon under `atelier/daemon/` that exposes repo-local run start, run inspection, per-run SSE audit streaming, and gate approval over HTTP. Reuse the existing workflow and run snapshot logic, auto-drive daemon-started runs with a deterministic Phase 0 execution backend, ship a real `python -m atelier.daemon` entrypoint, authenticate all routes with a shared secret header, and keep the entire surface testable in-process with `httpx.AsyncClient`.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: FastAPI, sse-starlette, httpx, pydantic v2, pathlib, existing `atelier.audit`, `atelier.workflow`, and `atelier.cli.commands.run` helpers  
**Storage**: Filesystem-only state under `.atelier/runs/` plus a repo-local daemon secret fallback under `.atelier/daemon/` when `LOCAL_DAEMON_SECRET` is unset  
**Testing**: pytest, pytest-asyncio, and `httpx.AsyncClient` with in-process ASGI transport  
**Target Platform**: Local developer machines and CI executing the daemon app without a real bound port  
**Project Type**: Local HTTP control-plane service over existing filesystem-backed workflow state  
**Performance Goals**: Metadata routes should complete within local filesystem latency, and SSE should surface appended audit events within one short polling interval in tests  
**Constraints**: SSE only, not WebSockets; loopback-only client access; shared-secret auth required; no external network in tests; no new persistence layer; daemon-started runs must emit audit events without depending on an external agent runtime  
**Scale/Scope**: One FastAPI app factory, one router module, one audit-tail/SSE helper module, and one focused AsyncClient test module

## Constitution Check

The repository constitution is still template text, so there are no enforceable gates to fail. This plan still respects the repo's actual Phase 0 constraints: filesystem-first state under `.atelier/`, CLI and daemon surfaces sharing the same source of truth, and safe local-only control-plane boundaries.

## Project Structure

### Documentation (this feature)

```text
specs/014-http-daemon-sse/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── daemon-http.md
└── tasks.md
```

### Source Code (repository root)

```text
atelier/
├── audit/
│   ├── events.py
│   └── writer.py
├── cli/
│   └── commands/
│       └── run.py
├── daemon/
│   ├── server.py
│   ├── routes.py
│   └── events.py
└── workflow/
    └── engine.py

tests/
└── test_daemon.py
```

**Structure Decision**: Keep the W16 implementation isolated to `atelier/daemon/` and the focused test module, while reusing existing audit, workflow, and run snapshot helpers rather than adding a new service abstraction.

## Complexity Tracking

No constitution violations or exceptional complexity expected.
