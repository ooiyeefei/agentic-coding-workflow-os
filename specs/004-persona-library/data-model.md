# Data Model: Persona Library

## PersonaPromptDefinition

- **Purpose**: Represents the contents of a shipped persona markdown file.
- **Fields**:
  - `name`: Canonical persona name such as `coder` or `reviewer`
  - `llm_adapter_name`: Selection policy or resolved adapter identifier
  - `required_capabilities`: W02 `CapabilityRequirements` payload used for routing
  - `body`: Markdown system prompt text
- **Validation rules**:
  - Frontmatter must exist and be a mapping.
  - `required_capabilities` must validate against W02's capability schema.
  - Prompt body must not be empty after trimming whitespace.

## SkillCatalogEntry

- **Purpose**: Represents one Speckit command available to Coder.
- **Fields**:
  - `command`: Canonical command name such as `/speckit.plan`
  - `source`: Either `catalog` or `fallback`
  - `description`: Short guidance shown to the model in the prompt context
- **Validation rules**:
  - `command` must begin with `/speckit.` for this slice.
  - Fallback entries must preserve the fixed Phase 0 order.

## PersonaBinding

- **Purpose**: Captures the routed manifest and adapter identity for a persona instance.
- **Fields**:
  - `persona_name`: Role name
  - `manifest_provider`: Provider selected by W02 routing
  - `manifest_model`: Model selected by W02 routing
  - `required_capabilities`: The requirements used for matching
  - `adapter_ready`: Whether a concrete adapter instance has been injected or constructed
- **Validation rules**:
  - The selected manifest must satisfy all declared required capabilities.
  - Binding creation fails fast when no compatible manifest exists.

## AgentResponse

- **Purpose**: Represents the normalized result of a persona turn.
- **Fields**:
  - `persona`: Persona name
  - `adapter_name`: Selected model or adapter identifier
  - `provider`: Selected provider
  - `model`: Selected model name
  - `content`: Normalized text output
  - `tool_calls`: Normalized tool call list
  - `stop_reason`: Provider stop reason when available
  - `usage`: Normalized usage counters
  - `cost`: Normalized cost fields
  - `metadata`: Persona-specific extras such as Coder's recommended next command
- **Validation rules**:
  - Persona metadata must match the bound manifest.
  - Tool calls, usage, and cost values follow W02's normalized types.
  - Metadata remains JSON-serializable.
