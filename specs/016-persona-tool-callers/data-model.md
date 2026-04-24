# Data Model: Persona Tool Callers

## AgentToolCaller

**Purpose**: Implements workflow persona calls by generating a paste-ready prompt for an external agent tool.

**Fields / Configuration**

- `agent_tool`: Tool adapter instance, tool name, or omitted auto-detected tool.
- `repo_root`: Repository root used by tool adapters to render context.
- `persona_factory`: Callable that returns a persona object for a persona name.
- `memory_records`: Optional transferred memory records included in the tool context packet.
- `output`: Text stream used for Phase 0 prompt printing.

**Behavior**

- Resolves persona name to a persona instance.
- Renders a tool-specific context packet.
- Appends persona system prompt, stage context, skill, and run ID.
- Prints and returns the prompt string.

## DirectAPICaller

**Purpose**: Implements workflow persona calls by delegating to existing persona direct API response behavior.

**Fields / Configuration**

- `persona_factory`: Callable that returns a persona object for a persona name.

**Behavior**

- Resolves persona name to a persona instance.
- Calls the persona direct response path.
- Returns a `PersonaCallResult` carrying content and metadata.

## Persona

**Purpose**: Existing role prompt object that renders system and user messages.

**New Behavior**

- `respond()` delegates to direct caller behavior by default.
- `respond_via_tool()` delegates to `AgentToolCaller` prompt generation.

## Tool Adapter

**Purpose**: Existing adapter that renders tool-specific context packet conventions.

**Behavior Used**

- `format_context_packet(run_id, role, memory_records)` provides the tool-specific section prepended to generated prompts.
