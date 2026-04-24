# Research: Persona Tool Callers

## Decision: Keep `PersonaCaller` Protocol Unchanged

**Rationale**: The protocol already abstracts persona execution as `call(persona_name, context, *, skill, run_id)` and supports returning either a string or `PersonaCallResult`. The architectural bug is in implementation, not the contract.

**Alternatives considered**: Adding protocol methods for agent tools was rejected because it would ripple through stage execution without adding needed behavior.

## Decision: Compose Agent Tool Prompts From Existing Persona Rendering

**Rationale**: Personas already own system prompt rendering and user message construction. Reusing those methods keeps generated tool prompts consistent with direct API prompts while swapping execution from API calls to human-mediated agent tool use.

**Alternatives considered**: Duplicating prompt templates in the caller was rejected because it would drift from persona definitions and existing tests.

## Decision: Use W27 Tool Adapters As Context Packet Formatters

**Rationale**: Existing adapters already know how to render Codex and Claude Code context conventions. `AgentToolCaller` can prepend that packet to persona instructions and stage context.

**Alternatives considered**: Adding a new adapter API was deferred because the current `format_context_packet()` method is sufficient for Phase 0 prompt generation.

## Decision: Keep Direct API Behavior Behind `DirectAPICaller`

**Rationale**: Existing tests and auxiliary workflows rely on direct model calls. Encapsulating that behavior as a caller clarifies that it is exceptional and not the main workflow execution path.

**Alternatives considered**: Removing direct calls entirely was rejected because council tiebreaker and ADR synthesis compatibility remains in scope.

## Decision: Default Workflow Dependencies Can Be Built, Explicit Dependencies Still Win

**Rationale**: Current workflow tests inject mock dependencies. Default dependency construction should use `AgentToolCaller` without breaking injected test doubles.

**Alternatives considered**: Forcing every `WorkflowEngine` caller to pass dependencies was rejected because it preserves the old hidden architecture bug for production defaults.
