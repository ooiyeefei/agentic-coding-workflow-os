# Contract: atelier.personas Public API

## Persona Base

- `Persona(...).name -> str`
- `Persona(...).system_prompt -> str`
- `Persona(...).required_capabilities -> CapabilityRequirements`
- `Persona(...).llm_adapter_name -> str`
- `await Persona.respond(context_packet) -> AgentResponse`

**Contract**:

- Persona initialization loads prompt metadata from `.atelier/defaults/personas/<name>.md`.
- Persona initialization routes through W02's `route_persona_to_model(...)`.
- Persona initialization raises `UnsupportedCapabilityError` if no compatible manifest exists.
- `respond(...)` always sends one system message plus one user message built from the supplied context packet.
- `respond(...)` returns `AgentResponse` and never exposes provider SDK response objects.

## Coder Persona

- `Coder(...)`

**Contract**:

- Declares `tool_use=True` and `long_context>=128000` as required routing capabilities.
- Discovers `.atelier/defaults/skills/*.md` when available.
- Falls back to the Phase 0 Speckit command sequence when no skill catalog exists.
- Includes the recommended next `/speckit.*` command in `AgentResponse.metadata`.

## Reviewer Persona

- `Reviewer(..., devil_advocate_mode: bool = False)`

**Contract**:

- Declares `tool_use=True`, `code_execution=True`, and `structured_outputs=True` as required routing capabilities.
- Loads an execution-mandatory prompt that explicitly requires execution evidence.
- When `devil_advocate_mode=False`, uses the base prompt unchanged.
- When `devil_advocate_mode=True`, appends explicit "reasons to reject" scaffolding even for APPROVE verdicts.
