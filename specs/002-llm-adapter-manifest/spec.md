# Feature Specification: LLM Adapter Manifest

**Feature Branch**: `acw-w02`  
**Created**: 2026-04-20  
**Status**: Draft  
**Input**: User description: "LLM adapter layer with Anthropic + OpenAI implementations and capability manifest matching"

## Clarifications

### Session 2026-04-20

- Q: What is the capability vocabulary for routing? → A: `tool_use`, `parallel_tool_use`, `long_context`, `code_execution`, and `structured_outputs`.
- Q: What should happen on capability mismatch? → A: Routing must raise `UnsupportedCapabilityError`; silent downgrade is out of scope.
- Q: At what level should cost be recorded? → A: Each adapter call records per-call cost on the normalized `Response`; run-level aggregation happens elsewhere.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Route Personas To Compatible Models (Priority: P1)

As a workflow orchestrator, I can match a persona's required capabilities against available model manifests so I only dispatch work to models that actually meet the persona contract.

**Why this priority**: Without capability-based routing, Atelier cannot honestly claim model swappability and will continue to depend on brittle hardcoded model choices.

**Independent Test**: Provide a requirements object with `tool_use=True` and `long_context=128000`, then confirm the matcher selects a manifest that offers both while rejecting one that lacks `tool_use`.

**Acceptance Scenarios**:

1. **Given** a persona requires `tool_use=True` and `long_context=128000`, **When** a manifest offers `tool_use=True` and `long_context=200000`, **Then** the matcher returns that manifest as compatible.
2. **Given** a persona requires `tool_use=True`, **When** the only available manifest offers `tool_use=False`, **Then** routing raises `UnsupportedCapabilityError`.
3. **Given** multiple manifests are available, **When** routing evaluates them, **Then** it returns the first compatible manifest in caller-provided order instead of relying on hardcoded provider or model names.

---

### User Story 2 - Generate Normalized Responses Across Providers (Priority: P2)

As a persona runner, I can call Anthropic or OpenAI through one adapter contract so provider swaps do not require persona-specific code changes.

**Why this priority**: The adapter layer is the actual abstraction boundary. If the response contract is not normalized, every persona will leak provider conditionals.

**Independent Test**: Mock each SDK client, call `generate(...)`, and verify both adapters return the same normalized response fields for content, tool calls, usage, and cost.

**Acceptance Scenarios**:

1. **Given** the Anthropic adapter receives chat messages and optional tools, **When** the mocked SDK returns text and usage data, **Then** the adapter returns a normalized `Response` with provider, model, content, usage, and cost fields populated.
2. **Given** the OpenAI adapter receives the same logical inputs, **When** the mocked SDK returns text and tool calls, **Then** the adapter returns the same normalized `Response` shape without exposing provider-specific response objects.
3. **Given** required capabilities are passed into `generate(...)`, **When** the backing manifest does not satisfy them, **Then** the adapter raises `UnsupportedCapabilityError` before making a provider call.

---

### User Story 3 - Ship Default Model Manifests For Phase 0 (Priority: P3)

As a repository maintainer, I can load default model manifests from versioned YAML files so model availability, capability claims, and pricing stay outside the code path.

**Why this priority**: Default manifests make the abstraction operational and enforce the rule that model identifiers live in declarative config rather than source code.

**Independent Test**: Load the shipped YAML files, confirm each validates into a `CapabilityManifest`, and verify the adapter code uses manifest-provided model ids instead of embedded literals.

**Acceptance Scenarios**:

1. **Given** the defaults directory contains Anthropic and OpenAI manifest YAML files, **When** the loader reads them, **Then** each file validates against the manifest schema.
2. **Given** an adapter is instantiated with a manifest, **When** it makes a provider request, **Then** it uses `manifest.model` rather than a hardcoded string.
3. **Given** response usage contains token counts, **When** the adapter normalizes the provider response, **Then** it computes per-call USD cost from the manifest pricing fields.

### Edge Cases

- Missing or malformed manifest fields must fail validation rather than silently defaulting to unsupported capabilities.
- Capability routing must ignore optional capability fields that were not requested instead of treating absent requirements as failures.
- Providers may return text-only responses, tool-call-only responses, or both; the normalized response must handle all three shapes.
- Invalid JSON in a provider tool-call payload must not crash response normalization; the raw argument string should still be preserved.
- Capability mismatch must raise before any network request is attempted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define an abstract `LLMAdapter` contract in `atelier/llm/adapter.py` with async `generate(messages, tools, required_capabilities) -> Response`.
- **FR-002**: The system MUST provide normalized Pydantic models for adapter inputs and outputs, including messages, tools, tool calls, usage, and per-call cost.
- **FR-003**: The system MUST implement an Anthropic adapter in `atelier/llm/anthropic.py` using the `anthropic` Python SDK.
- **FR-004**: The system MUST implement an OpenAI adapter in `atelier/llm/openai.py` using the `openai` Python SDK.
- **FR-005**: The system MUST validate required capabilities against the adapter's manifest before making a provider request.
- **FR-006**: The system MUST define a Pydantic `CapabilityManifest` model in `atelier/llm/capabilities.py` with declarative capability offers and input/output pricing.
- **FR-007**: The system MUST define a matcher function `route_persona_to_model(persona_requires, available_models)` that returns the first compatible manifest in input order.
- **FR-008**: The system MUST raise `UnsupportedCapabilityError` when no available manifest satisfies the requested capabilities.
- **FR-009**: The system MUST represent `long_context` as a numeric minimum-token capability and treat larger offered context windows as compatible with smaller requirements.
- **FR-010**: The system MUST load default manifests from `.atelier/defaults/models/*.yaml`.
- **FR-011**: The system MUST ship default manifests for `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5`, `gpt-5`, and `gpt-4o-mini`.
- **FR-012**: The system MUST keep provider model identifiers out of source code paths other than the manifest YAML files.
- **FR-013**: The system MUST compute per-call input, output, and total USD cost on the normalized `Response` using manifest pricing and provider token usage.
- **FR-014**: The system MUST include mocked unit tests for Anthropic and OpenAI adapter calls plus capability match success and failure cases.

### Key Entities *(include if feature involves data)*

- **CapabilityRequirements**: The minimum features a persona needs, including boolean capability flags and minimum context window size.
- **CapabilityManifest**: A validated description of one model's provider, capability offers, and token pricing sourced from YAML.
- **ToolDefinition**: A provider-neutral description of a callable function tool, including name, description, and JSON schema.
- **LLMMessage**: A normalized message record passed into adapters, including role, text content, and optional tool call metadata.
- **LLMResponse**: A normalized provider response that carries text, tool calls, usage totals, and per-call cost.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `tests/test_llm_adapter.py` passes locally and covers Anthropic, OpenAI, successful capability routing, and unsupported capability failure.
- **SC-002**: A persona requirement of `tool_use=True, long_context=128000` matches a manifest offering `tool_use=True, long_context=200000`.
- **SC-003**: A persona requirement of `tool_use=True` fails with `UnsupportedCapabilityError` when the only available manifest offers `tool_use=False`.
- **SC-004**: Repository source files outside `.atelier/defaults/models/` contain no hardcoded default provider model identifiers for this feature.
- **SC-005**: Every normalized adapter response includes per-call input, output, and total cost values suitable for later audit-log ingestion.

## Assumptions

- Multimodal request payloads are out of scope for this slice; the adapter contract only needs text messages and function-style tools.
- Provider SDK clients will read API keys from their standard environment variables unless a caller injects a client instance directly.
- Built-in provider tools can be added later; this slice only needs provider-neutral function tool definitions plus capability advertising for future routing.
- The first compatible manifest in caller-provided order is the desired routing policy for Phase 0.
