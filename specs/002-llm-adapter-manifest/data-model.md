# Data Model: LLM Adapter Manifest

## CapabilityRequirements

- **Purpose**: Represents the minimum capabilities a persona needs before routing to a model.
- **Fields**:
  - `tool_use`: whether tool calling is required
  - `parallel_tool_use`: whether multi-tool execution is required
  - `long_context`: minimum acceptable input context window in tokens
  - `code_execution`: whether built-in code execution is required
  - `structured_outputs`: whether structured output support is required

## CapabilityManifest

- **Purpose**: Declares one model's provider, model identifier, offered capabilities, and pricing.
- **Fields**:
  - `provider`: model vendor name such as Anthropic or OpenAI
  - `model`: provider model identifier loaded from YAML
  - `offers`: capability record for routing
  - `cost_per_mtok_in`: USD per one million input tokens
  - `cost_per_mtok_out`: USD per one million output tokens

## ToolDefinition

- **Purpose**: Describes a callable function tool in a provider-neutral format.
- **Fields**:
  - `name`: tool name exposed to the model
  - `description`: natural-language tool description
  - `input_schema`: JSON schema for tool arguments
  - `strict`: whether argument validation should be strict where supported

## LLMMessage

- **Purpose**: Represents one conversation turn passed into an adapter.
- **Fields**:
  - `role`: `system`, `user`, `assistant`, or `tool`
  - `content`: text payload for the message
  - `tool_call_id`: tool call identifier for tool-result messages
  - `tool_calls`: optional assistant-issued tool calls preserved for follow-up turns

## ToolCall

- **Purpose**: Represents one normalized tool request emitted by a provider.
- **Fields**:
  - `id`: provider-generated tool call identifier
  - `name`: tool name
  - `arguments`: parsed JSON arguments or raw argument text when parsing fails

## LLMResponse

- **Purpose**: Represents a provider response after normalization.
- **Fields**:
  - `id`: provider response identifier
  - `provider`: provider name
  - `model`: manifest model identifier
  - `content`: normalized text content
  - `tool_calls`: normalized tool call list
  - `stop_reason`: provider stop status when available
  - `usage`: input, output, and total token counts
  - `cost`: input, output, and total USD cost for the call

## Relationships

- One `CapabilityManifest` is evaluated against one `CapabilityRequirements` record during routing.
- One `LLMAdapter` instance is configured with exactly one `CapabilityManifest`.
- One `LLMResponse` may contain zero or more `ToolCall` items.
- `LLMResponse.cost` is derived from `CapabilityManifest` pricing and `LLMResponse.usage`.
