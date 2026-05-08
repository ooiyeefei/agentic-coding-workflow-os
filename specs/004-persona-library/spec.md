# Feature Specification: Persona Library

**Feature Branch**: `004-persona-library`  
**Created**: 2026-04-20  
**Status**: Draft  
**Input**: User description: "Coder + Reviewer personas with LLMAdapter binding and devil_advocate_mode flag (default off)"

## Clarifications

### Session 2026-04-20

- Q: Which capability requirements drive default persona routing? → A: Coder routes on `tool_use=True` and `long_context>=128000`; Reviewer routes on `tool_use=True`, `code_execution=True`, and `structured_outputs=True`, and shipped defaults must include at least one compatible manifest for each persona.
- Q: How should default model mapping work in Phase 0? → A: Each persona loads available manifests and selects the first compatible manifest in caller-provided or shipped order via W02's matcher; callers may still inject a specific adapter for tests or integration wiring.
- Q: How should Coder behave before W05 lands its skills catalog? → A: Coder loads `.spanweave/defaults/skills/*.md` when present and otherwise falls back to the fixed Phase 0 `/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement` sequence.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Route Personas To Compatible Models (Priority: P1)

As a workflow orchestrator, I can instantiate Coder and Reviewer personas that declare their capability needs and bind themselves to the first compatible model, so persona behavior stays LLM-agnostic instead of hardcoded to one provider.

**Why this priority**: Capability-gated routing is the architectural proof behind the product's LLM-agnostic claim. If the default personas cannot route through W02, the abstraction is not real.

**Independent Test**: Instantiate each persona against shipped manifests and confirm Coder and Reviewer both resolve a compatible manifest, while Reviewer fails fast when only incompatible manifests are available.

**Acceptance Scenarios**:

1. **Given** the shipped manifests include at least one model with `tool_use=True` and `long_context>=128000`, **When** `Coder()` initializes, **Then** it selects the first compatible manifest via W02 routing and records the selected adapter name.
2. **Given** the shipped manifests include at least one model with `tool_use=True`, `code_execution=True`, and `structured_outputs=True`, **When** `Reviewer()` initializes, **Then** it selects the first compatible manifest via W02 routing and records the selected adapter name.
3. **Given** Reviewer only receives manifests that lack one or more required capabilities, **When** `Reviewer()` initializes, **Then** it raises `UnsupportedCapabilityError` instead of silently downgrading requirements.

---

### User Story 2 - Produce Structured Persona Responses (Priority: P2)

As a workflow engine, I can call `persona.respond(context_packet)` on any persona and receive one normalized response object that preserves the selected provider/model identity and generated content.

**Why this priority**: The workflow engine needs one persona-facing contract. If persona output shape varies by provider or role, downstream stages will splinter immediately.

**Independent Test**: Inject a mock adapter into each persona, call `respond(...)`, and verify both return the same `AgentResponse` shape with persona metadata and normalized LLM output fields.

**Acceptance Scenarios**:

1. **Given** a persona has a compatible adapter and a context packet, **When** `respond(...)` runs, **Then** it sends a system message plus user packet through the adapter and returns a structured `AgentResponse`.
2. **Given** the adapter returns normalized content, tool calls, usage, and cost, **When** the persona returns its result, **Then** those fields are preserved in the `AgentResponse` without provider-specific response objects leaking out.
3. **Given** Coder receives a packet describing the current workflow state, **When** it responds, **Then** it includes guidance for the next `/speckit.*` command based on the available skill catalog or the Phase 0 fallback sequence.

---

### User Story 3 - Enforce Execution-Mandatory Review Discipline (Priority: P3)

As a reviewer persona consumer, I can rely on the Reviewer's system prompt to demand real execution evidence, and I can optionally enable devil's-advocate mode to surface rejection arguments even on approvals.

**Why this priority**: Execution-mandatory review is the project's moat. If the Reviewer prompt becomes soft or vague, the review loop collapses into ungrounded opinions.

**Independent Test**: Load the default Reviewer prompt, confirm the required imperative phrases are present, then compare default vs `devil_advocate_mode=True` prompts and verify the latter adds explicit "reasons to reject" scaffolding.

**Acceptance Scenarios**:

1. **Given** the default Reviewer prompt, **When** it is loaded, **Then** it explicitly says the reviewer must execute checks, paste actual output, and treat approval as incomplete without execution evidence.
2. **Given** `Reviewer(devil_advocate_mode=False)`, **When** the persona is initialized, **Then** the base execution-mandatory prompt is used without any extra rejection scaffold.
3. **Given** `Reviewer(devil_advocate_mode=True)`, **When** the persona is initialized, **Then** the prompt includes an explicit "reasons to reject" section requirement even if the verdict is APPROVE.

### Edge Cases

- What happens when a persona prompt file is missing, malformed, or lacks capability frontmatter?
- What happens when `.spanweave/defaults/skills/` has not landed yet or contains no `/speckit.*` skills?
- How does the system handle a compatible manifest selection when multiple providers qualify and the shipped order changes?
- How does Reviewer fail when no manifest offers `code_execution` or `structured_outputs`?
- How does `respond(...)` serialize non-string context packets without leaking Python reprs into the LLM prompt?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define a shared `Persona` base in `spanweave/personas/base.py` with `name`, `system_prompt`, `required_capabilities`, `llm_adapter_name`, and async `respond(context_packet) -> AgentResponse`.
- **FR-002**: The system MUST define a structured `AgentResponse` model for persona output that includes persona identity plus normalized LLM response data.
- **FR-003**: The system MUST load persona system prompts from markdown files in `.spanweave/defaults/personas/` and parse YAML frontmatter for persona metadata.
- **FR-004**: The system MUST represent persona capability requirements with W02's `CapabilityRequirements` model and route personas through W02's `route_persona_to_model(...)` helper.
- **FR-005**: The system MUST allow personas to use a caller-injected `LLMAdapter` for tests and integration, while still validating that the selected manifest satisfies the persona's declared requirements.
- **FR-006**: The system MUST provide a `Coder` persona in `spanweave/personas/coder.py` that declares at least `tool_use=True` and `long_context>=128000` as routing requirements.
- **FR-007**: The system MUST let `Coder` discover `/speckit.*` skills from `.spanweave/defaults/skills/*.md` when available and fall back to the fixed Phase 0 Speckit command sequence when the skill catalog is absent.
- **FR-008**: The system MUST provide a `Reviewer` persona in `spanweave/personas/reviewer.py` that declares `tool_use=True`, `code_execution=True`, and `structured_outputs=True` as routing requirements.
- **FR-009**: The system MUST load the Reviewer prompt from `.spanweave/defaults/personas/reviewer.md` and keep the execution-mandatory protocol in imperative language.
- **FR-010**: The Reviewer prompt MUST explicitly mention the concepts "execute", "paste actual output", and "incomplete without execution evidence".
- **FR-011**: `Reviewer` MUST support a `devil_advocate_mode: bool = False` constructor flag that only appends explicit "reasons to reject" scaffolding when the flag is enabled.
- **FR-012**: The default shipped manifests and routing metadata MUST allow both `Coder()` and `Reviewer()` to resolve at least one compatible model on Phase 0 defaults.
- **FR-013**: When no compatible manifest exists for a persona, initialization MUST raise `UnsupportedCapabilityError` rather than silently dropping requirements.
- **FR-014**: `tests/test_personas.py` MUST cover default routing, structured `respond(...)` output, execution-mandatory prompt text, devil's-advocate prompt differences, and Reviewer failure on incompatible capabilities.

### Key Entities *(include if feature involves data)*

- **PersonaPromptDefinition**: Frontmatter metadata plus markdown body loaded from a shipped persona prompt file.
- **Persona**: A capability-gated role that owns a prompt, selected manifest, and `respond(...)` entrypoint.
- **AgentResponse**: The normalized persona response returned to the workflow engine, including persona metadata and LLM output details.
- **SkillReference**: A discovered or fallback `/speckit.*` command that helps Coder identify the next workflow transition.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `tests/test_personas.py` passes locally with mocked adapters.
- **SC-002**: `Coder()` initializes successfully against shipped defaults and records the first compatible model for `tool_use=True` and `long_context>=128000`.
- **SC-003**: `Reviewer()` initializes successfully against shipped defaults and records the first compatible model for `tool_use=True`, `code_execution=True`, and `structured_outputs=True`.
- **SC-004**: `Reviewer(devil_advocate_mode=True).system_prompt` differs from the default prompt by adding explicit "reasons to reject" scaffolding while leaving the default flag value off.
- **SC-005**: The shipped Reviewer prompt contains the phrases "execute", "paste actual output", and "incomplete without execution evidence" in the execution protocol text.
- **SC-006**: Instantiating Reviewer against only incompatible manifests raises `UnsupportedCapabilityError`.

## Assumptions

- W02 remains the source of truth for routing and adapter contracts; W04 may extend shipped manifest metadata if Phase 0 defaults do not yet satisfy Reviewer's declared requirements.
- W05 may not be merged yet, so Coder needs a built-in fallback Speckit progression rather than a hard dependency on the skills catalog.
- Persona instances are long-lived Python objects that can defer actual network calls until `respond(...)` is invoked.
- Real Evidence Pack generation remains out of scope for W04; Reviewer only needs to return a structured persona response that later worktrees can transform into evidence artifacts.
