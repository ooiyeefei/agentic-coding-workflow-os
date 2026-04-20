# Contract: Context Compiler API

## Public entrypoint

- **Function**: `compile_packet(objective, sources, budget_tokens) -> Packet`
- **Inputs**:
  - `objective`: Either a plain objective string or an `Objective` source model
  - `sources`: Ordered sequence of typed compiler sources
  - `budget_tokens`: Positive integer token budget
- **Output**:
  - `Packet.body`: Markdown packet containing the objective block, included source blocks, and a provenance footer
  - `Packet.provenance`: Ordered provenance entries for included blocks
  - `Packet.estimated_tokens`: Final packet estimate

## Source types

- Supported source models:
  - `IssueText`
  - `RepoRule`
  - `ADR`
  - `SampleDoc`
  - `WorktreeRef`
  - `Objective`
  - `ExactCommands`
  - `AcceptanceGate`
- Every source provides `source_id`, `priority`, `title`, `content`, and optional `path`.

## Ordering and deduplication

- Sources are compiled in `must`, `should`, `nice` order.
- Caller order is preserved within each priority tier.
- Duplicate `source_id` values are deduplicated by exact match.
- The first deterministic occurrence wins.

## Budget behavior

- Token estimate uses `ceil(len(text) * 4 / 3)`.
- `nice` blocks are dropped before `should` blocks.
- `must` blocks are never dropped.
- If must-tier content alone exceeds budget, `BudgetExceededError` is raised.

## Provenance footer

- Footer heading: `## Provenance`
- Footer body: Markdown table with columns `source_type`, `source_id`, and `path`
- Footer order matches the order of blocks included in the packet
- Missing paths render as `-`
