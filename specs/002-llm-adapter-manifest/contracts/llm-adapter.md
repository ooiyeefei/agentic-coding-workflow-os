# Contract: LLM Adapter Layer

## Adapter Interface

`LLMAdapter.generate(messages, tools, required_capabilities) -> Response`

### Inputs

- `messages`: ordered list of normalized `LLMMessage` records
- `tools`: ordered list of provider-neutral `ToolDefinition` records
- `required_capabilities`: optional `CapabilityRequirements` guard applied before provider execution

### Output

- `Response.id`: provider response identifier when available
- `Response.provider`: provider name from the manifest
- `Response.model`: model id from the manifest
- `Response.content`: normalized text output
- `Response.tool_calls`: zero or more normalized tool calls
- `Response.stop_reason`: provider stop reason when exposed
- `Response.usage`: normalized input, output, and total tokens
- `Response.cost`: normalized input, output, and total USD cost

## Routing Interface

`route_persona_to_model(persona_requires, available_models) -> CapabilityManifest`

### Behavior

- Evaluates manifests in caller-provided order
- Returns the first manifest whose offered capabilities satisfy all requested requirements
- Treats `long_context` as a minimum numeric threshold
- Raises `UnsupportedCapabilityError` when no manifest satisfies the request

## Failure Contract

- Capability mismatch fails before any provider call
- Invalid manifest data fails validation during load
- Tool-call argument JSON parsing preserves the raw string if decoding fails
