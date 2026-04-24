# Feature Specification: Persona Tool Callers

**Feature Branch**: `016-persona-tool-callers`  
**Created**: 2026-04-24  
**Status**: Draft  
**Input**: User description: "Persona rework: AgentToolCaller (generates prompts for agent tools) + DirectAPICaller (existing API path for auxiliary use). Wire into workflow engine."

## Clarifications

### Session 2026-04-24

- Q: How does AgentToolCaller return results for Phase 0? -> A: Generate the formatted prompt, print it to stdout for the human to paste into the target agent tool, and return the same prompt string; automated tool APIs are deferred.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate Agent Tool Prompts (Priority: P1)

As a workflow operator, I want persona stages to produce paste-ready prompts for the selected agent tool so Claude Code, Codex, or another tool performs the work instead of Atelier calling model APIs directly.

**Why this priority**: This corrects the core architecture for main workflow stages.

**Independent Test**: Can be tested by invoking a persona caller with a tool adapter and verifying that the returned content is a tool-specific prompt, not an LLM API response.

**Acceptance Scenarios**:

1. **Given** a persona name, stage context, skill, run ID, and Codex adapter, **When** the caller is invoked, **Then** it returns a prompt containing Codex-specific context conventions plus the persona prompt and stage request.
2. **Given** a persona name, stage context, skill, run ID, and Claude Code adapter, **When** the caller is invoked, **Then** it returns a prompt containing Claude Code-specific context conventions plus the persona prompt and stage request.

---

### User Story 2 - Preserve Direct API Compatibility (Priority: P2)

As a maintainer of auxiliary automation, I want the existing persona API path to remain available so council tiebreakers, ADR prose synthesis, and current tests keep working while main workflow stages move to agent tools.

**Why this priority**: The project still needs direct model calls for auxiliary tasks and backward compatibility.

**Independent Test**: Can be tested by calling existing `Persona.respond()` paths with fake adapters and verifying the same structured response semantics as before.

**Acceptance Scenarios**:

1. **Given** an existing persona test that supplies a fake adapter, **When** `respond()` is called without a caller override, **Then** the persona uses the direct API path and returns an `AgentResponse`.
2. **Given** a direct persona caller, **When** it is invoked for a known persona, **Then** it wraps the existing response behavior and returns the generated content.

---

### User Story 3 - Use Correct Callers In Workflow Execution (Priority: P3)

As a workflow maintainer, I want main stages to use agent-tool prompting while auxiliary stages remain on direct API execution so stage routing matches the intended system architecture.

**Why this priority**: Correct default wiring prevents regressions when workflow execution dependencies are not explicitly provided.

**Independent Test**: Can be tested by constructing workflow engine dependencies and verifying stage callers are selected according to main versus auxiliary use.

**Acceptance Scenarios**:

1. **Given** a main workflow stage such as specify, clarify, plan, tasks, implement, or review, **When** default workflow dependencies are built, **Then** the stage uses `AgentToolCaller`.
2. **Given** auxiliary work such as council tiebreaker or ADR synthesis, **When** direct model execution is requested, **Then** `DirectAPICaller` remains available and does not require an agent tool.

### Edge Cases

- Unknown persona names fail with a clear error rather than silently selecting the wrong prompt.
- Unknown agent tool names fail with a clear error listing the supported shipped adapters.
- Empty or whitespace tool prompts are rejected before printing.
- Existing tests that inject their own `StageExecutorDeps` continue to use those injected callers unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an `AgentToolCaller` implementation of the existing `PersonaCaller` contract.
- **FR-002**: `AgentToolCaller.call()` MUST return the formatted prompt string intended for the target agent tool, not an LLM API response.
- **FR-003**: `AgentToolCaller.call()` MUST print the formatted prompt to stdout in Phase 0 so a human can paste it into the agent tool.
- **FR-004**: The agent-tool prompt MUST include the persona system prompt, rendered stage context, requested skill, run ID, and tool-specific context packet formatting.
- **FR-005**: The system MUST provide a `DirectAPICaller` implementation that preserves the existing direct persona response behavior.
- **FR-006**: `Persona.respond()` MUST keep backward compatibility by defaulting to direct API behavior when no caller is supplied.
- **FR-007**: Personas MUST offer `respond_via_tool(agent_tool, context)` for generating an agent-tool prompt without calling an LLM API.
- **FR-008**: The workflow engine MUST be able to build or use dependencies that route main stages through `AgentToolCaller`.
- **FR-009**: Direct API calling MUST remain available for auxiliary tasks such as council tiebreaking and ADR prose synthesis.
- **FR-010**: New tests MUST verify tool-specific prompt generation and existing persona/workflow tests MUST continue to pass.

### Key Entities

- **AgentToolCaller**: Persona caller that composes and returns a paste-ready tool prompt.
- **DirectAPICaller**: Persona caller that delegates to existing persona direct API response behavior.
- **Tool Adapter**: Existing W27 adapter that contributes tool-specific context packet formatting.
- **Persona**: Existing prompt-bearing role object that can render system and user messages.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Agent-tool caller tests prove returned content includes tool-specific markers for at least Codex and Claude Code.
- **SC-002**: Direct caller and existing persona tests continue to return `AgentResponse` content through fake LLM adapters.
- **SC-003**: Workflow tests continue to pass with injected callers, showing backward-compatible dependency injection.
- **SC-004**: Targeted test run for persona callers, personas, and workflow completes without regressions.

## Assumptions

- Phase 0 does not automate Claude Code or Codex APIs; it generates a prompt and waits for human-mediated execution outside this slice.
- Main workflow stage names are the Spec Kit loop stages: specify, clarify, plan, tasks, implement, and review.
- Existing direct LLM adapter selection and policy handling remain owned by `Persona.respond()`.
- Existing council and ADR modules are not rewritten in this slice; direct persona caller availability is sufficient for the requested compatibility boundary.
