# Feature Specification: Tool Adapter Layer

**Feature Branch**: `015-tool-adapter-layer`  
**Created**: 2026-04-23  
**Status**: Implemented  
**Input**: User description: "Tool Adapter Layer: ABC + Claude Code adapter + Codex adapter + generic fallback, with ingest/format/detect operations and YAML manifests"

## Clarifications

### Session 2026-04-23

- Q: What Claude Code transcript format should Phase 0 support? -> A: Repo-local or home-directory Claude Code JSONL session logs under `.claude/projects/.../*.jsonl`, where each line is an event record and assistant/user turns live inside `message.role` content blocks.
- Q: What Codex transcript format should Phase 0 support? -> A: Codex rollout logs under `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`; `~/.codex/history.jsonl` is only user input history and is not sufficient for full session ingestion.
- Q: How should decision extraction work in unit-tested Phase 0? -> A: Use deterministic heuristic extraction from normalized transcript text with explicit support for `Decision:`, `Finding:`, and `Rejected:` markers; auxiliary LLM extraction stays optional for a later slice.
- Q: How should tool-specific context packets differ? -> A: Claude Code packets must reference `CLAUDE.md` and `.claude/rules/`; Codex packets must reference `AGENTS.md`; the generic adapter emits one self-contained markdown prompt with no external repo-convention dependency.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingest Agent Session State Into Typed Memory (Priority: P1)

As a user switching between coding agents, I can ingest a Claude Code, Codex, or pasted transcript into typed memory records so durable decisions survive the session boundary.

**Why this priority**: Durable transcript ingestion is the core bridge. If Atelier cannot capture decisions from the source tool, context transfer never begins.

**Independent Test**: Feed fixture transcripts for Claude Code, Codex, and the generic adapter into `ingest_transcript(...)`, write the returned records with `write_record(...)`, and confirm `.atelier/memory/` contains the expected typed markdown files.

**Acceptance Scenarios**:

1. **Given** a Claude Code JSONL session fixture with explicit decision statements, **When** the Claude Code adapter ingests it, **Then** it returns at least three `Decision` records with valid run and stage identifiers.
2. **Given** a Codex rollout JSONL fixture with explicit decision statements, **When** the Codex adapter ingests it, **Then** it returns typed records without depending on `history.jsonl`.
3. **Given** a plain markdown transcript fixture, **When** the generic adapter ingests it, **Then** it returns typed records from deterministic transcript markers.

---

### User Story 2 - Format Context Packets For The Target Tool (Priority: P2)

As a user moving from one coding agent to another, I can format the same stored memory into a paste-ready packet that matches the conventions of the target tool.

**Why this priority**: Ingestion alone does not solve tool switching. The output must feel native enough that the target agent uses the transferred context correctly.

**Independent Test**: Build a small set of memory records plus a fixture run state, format packets for Claude Code and Codex, and verify the output references the correct repo conventions and includes decisions, ADRs, and current run state.

**Acceptance Scenarios**:

1. **Given** prior decisions and a run id, **When** the Claude Code adapter formats a packet, **Then** the packet references `CLAUDE.md`, `.claude/rules/`, prior decisions, relevant ADRs, and current run state.
2. **Given** the same inputs, **When** the Codex adapter formats a packet, **Then** the packet references `AGENTS.md`, prior decisions, relevant ADRs, and current run state in Codex-oriented instruction style.
3. **Given** no repo-specific tool conventions are available, **When** the generic adapter formats a packet, **Then** it emits a self-contained markdown prompt that includes the same core context without external file assumptions.

---

### User Story 3 - Detect The Active Tool And Validate Adapter Manifests (Priority: P3)

As Atelier runtime code, I can detect whether Claude Code, Codex, or neither is active and load validated adapter manifests so the adapter layer can be selected safely.

**Why this priority**: Detection and manifest validation make the adapter layer operational instead of manual-only glue code.

**Independent Test**: Create temporary repositories and environment variable combinations, then confirm tool detection matches expectations and manifest YAML files validate with Pydantic.

**Acceptance Scenarios**:

1. **Given** a repository containing `.claude/`, **When** Claude Code detection runs, **Then** it reports `True`.
2. **Given** a repository containing `AGENTS.md` and Codex environment markers, **When** Codex detection runs, **Then** it reports `True`.
3. **Given** the shipped adapter manifests, **When** the manifest loader reads them, **Then** both files validate into typed manifest models.

### Edge Cases

- Claude Code JSONL files include non-message event lines such as permission-mode and progress updates; ingestion must ignore unsupported line types instead of failing the whole session.
- Codex rollout logs include developer and system messages as well as tool call records; ingestion must focus on user/assistant-visible content and relevant event payloads.
- Generic transcript files may contain blank sections or headings without decisions; ingestion should return an empty list instead of fabricated records.
- Context packet formatting must behave sensibly when a referenced ADR id or run state directory does not exist.
- Codex detection should not return `True` solely because `AGENTS.md` exists; it also requires Codex environment markers to avoid false positives in non-Codex tooling.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define a shared `ToolAdapter` abstract base class in `atelier/adapters/base.py`.
- **FR-002**: `ToolAdapter` MUST expose `tool_name` and `session_format` metadata plus abstract `ingest_transcript(session_path)`, `format_context_packet(run_id, role, memory_records)`, and `detect()` methods.
- **FR-003**: The system MUST define a typed manifest model and loader for adapter YAML manifests.
- **FR-004**: The system MUST ship validated manifests for Claude Code and Codex under `atelier/adapters/manifests/`.
- **FR-005**: The Claude Code adapter MUST ingest Claude Code JSONL session logs from `.claude/projects/.../*.jsonl`.
- **FR-006**: The Codex adapter MUST ingest Codex rollout JSONL session logs from `~/.codex/sessions/.../rollout-*.jsonl`.
- **FR-007**: The generic adapter MUST ingest a plain markdown transcript file for manual fallback usage.
- **FR-008**: Phase 0 ingestion MUST extract decisions and findings through deterministic heuristics without requiring live model calls in unit tests.
- **FR-009**: Extracted records MUST be compatible with existing `Decision`, `ReviewFinding`, and `RejectedAlternative` schemas in `atelier/memory/records.py`.
- **FR-010**: Claude Code context packets MUST reference `CLAUDE.md` and `.claude/rules/` when formatting instructions.
- **FR-011**: Codex context packets MUST reference `AGENTS.md` when formatting instructions.
- **FR-012**: Context packets MUST include prior decision summaries, relevant ADR summaries, and current run state.
- **FR-013**: Claude Code detection MUST require `.claude/`.
- **FR-014**: Codex detection MUST require `AGENTS.md` plus Codex environment markers.
- **FR-015**: The generic adapter detection surface MUST always return `False`.
- **FR-016**: `tests/test_adapters.py` MUST cover manifest validation, ingest behavior, context packet formatting, detection, and persistence with fixture data only.

### Key Entities *(include if feature involves data)*

- **ToolAdapter**: Shared adapter contract for ingesting transcripts, formatting packets, and detecting active tooling.
- **ToolManifest**: Typed YAML-backed description of one tool's capabilities, config paths, and session format.
- **TranscriptEntry**: Normalized conversational text extracted from a Claude Code, Codex, or generic transcript source.
- **ExtractedMemoryRecord**: A `Decision`, `ReviewFinding`, or `RejectedAlternative` built from transcript evidence and ready for persistence.
- **ToolContextPacket**: A paste-ready markdown prompt tailored to Claude Code, Codex, or generic instructions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `pytest tests/test_adapters.py -q` passes locally with no live network or model calls.
- **SC-002**: The Claude Code fixture produces at least three `Decision` records and can be written to `.atelier/memory/` via the existing memory writer.
- **SC-003**: The Codex fixture produces typed records from a rollout JSONL file rather than the lossy input-history file.
- **SC-004**: Claude Code and Codex packet outputs both include prior decisions, relevant ADRs, and current run state while referencing the correct tool convention files.
- **SC-005**: Detection correctly distinguishes Claude Code, Codex, and fallback cases in temporary repositories.
- **SC-006**: Both shipped adapter manifests validate through the typed manifest loader.

## Assumptions

- Phase 0 decision extraction prioritizes deterministic, offline-safe behavior over semantic completeness.
- The adapter layer formats packets from already persisted memory records rather than querying live tool APIs.
- Claude Code sessions can be provided either from repo-local `.claude/` state or from copied fixture logs.
- Codex environment detection will rely on environment variables visible inside the active Codex process, such as `CODEX_THREAD_ID`, alongside repo config files.
- Cursor and other tools are out of scope for this slice, but the base adapter contract should leave room for future adapters.
