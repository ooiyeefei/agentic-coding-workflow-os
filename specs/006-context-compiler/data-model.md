# Data Model: Context Compiler

## PriorityTier

- **Purpose**: Represents the priority class that controls budget trimming.
- **Values**:
  - `must`
  - `should`
  - `nice`
- **Validation rules**:
  - Only the three canonical tier names are allowed.
  - Budget trimming may remove `nice` and `should`, but never `must`.

## ContextSource

- **Purpose**: Represents one candidate block of packet content.
- **Fields**:
  - `source_type`: Canonical source kind such as `issue_text`, `repo_rule`, or `adr`
  - `source_id`: Stable identifier used for exact deduplication
  - `priority`: One of the `PriorityTier` values
  - `title`: Human-readable heading for the rendered block
  - `content`: Markdown-ready body content
  - `path`: Optional filesystem or logical path for provenance
- **Validation rules**:
  - `source_id`, `title`, and `content` must be non-empty after trimming.
  - `path` may be absent for logical sources such as objectives or issue text.
  - Each specialized source type fixes `source_type` to a canonical literal.

## Objective

- **Purpose**: Represents the packet objective as a first-class source.
- **Fields**:
  - Inherits `source_id`, `title`, `content`, `path`, and `priority`
- **Validation rules**:
  - Defaults to `source_id="objective"` and `priority="must"`.
  - Content must describe the task being executed by the packet consumer.

## ProvenanceEntry

- **Purpose**: Records where an included block came from.
- **Fields**:
  - `source_type`
  - `source_id`
  - `path`
- **Validation rules**:
  - One provenance entry exists for every included block.
  - Entries remain in the same order as blocks appear in the packet body.

## Packet

- **Purpose**: Represents the compiler output returned to callers.
- **Fields**:
  - `body`: Full packet markdown including the provenance footer
  - `provenance`: Ordered list of `ProvenanceEntry` values
  - `estimated_tokens`: Final packet estimate after trimming
- **Validation rules**:
  - `body` must include the provenance footer block.
  - `estimated_tokens` must be less than or equal to the requested budget when compilation succeeds.
  - The provenance list and footer must describe the same included sources.

## BudgetDecision

- **Purpose**: Captures whether a rendered source block is included or trimmed during compilation.
- **Fields**:
  - `source_id`
  - `priority`
  - `estimated_tokens`
  - `included`
  - `reason`
- **Validation rules**:
  - Must-tier blocks cannot be marked excluded for budget reasons.
  - Duplicate `source_id` exclusions use the reason `deduped`.
  - Lower-tier budget removals use the reason `dropped_for_budget`.
