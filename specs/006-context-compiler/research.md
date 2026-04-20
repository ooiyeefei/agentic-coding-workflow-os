# Research: Context Compiler

## Decision 1: Use typed Pydantic models for sources, packets, and provenance

- **Decision**: Model compiler inputs and outputs with small Pydantic types rather than raw dictionaries or tuples-only APIs.
- **Rationale**: The repo already uses Pydantic pervasively, and typed models make the source catalog, packet output, and test fixtures explicit without adding infrastructure.
- **Alternatives considered**:
  - Plain dictionaries everywhere: rejected because the source surface is large enough to benefit from validation and field defaults.
  - Dataclasses: rejected because the rest of the repo already standardizes on Pydantic validation and serialization behavior.

## Decision 2: Treat the objective as an `Objective` source internally

- **Decision**: `compile_packet(...)` accepts either a plain objective string or an `Objective` model and normalizes it into a must-tier `Objective` block before budgeting.
- **Rationale**: The public function signature keeps objective handling simple while still letting the compiler use one internal source pipeline and one provenance mechanism.
- **Alternatives considered**:
  - Require callers to always construct an `Objective` model: rejected because it adds friction to the primary API.
  - Keep the objective outside the source pipeline entirely: rejected because it would create special-case logic for ordering, budgeting, and provenance.

## Decision 3: Preserve deterministic order by tier first, then input order

- **Decision**: Compile blocks in `must`, then `should`, then `nice` order, while preserving the caller's original order within each tier.
- **Rationale**: This matches the product brief's priority semantics while keeping repeated compilation byte-stable and easy to reason about in tests.
- **Alternatives considered**:
  - Global sorting by source type or title: rejected because it would surprise callers and weaken the meaning of source order.
  - Fuzzy relevance ranking: rejected because Phase 0 explicitly prefers predictable exact behavior over heuristic ranking.

## Decision 4: Deduplicate by exact `source_id` and keep the first deterministic occurrence

- **Decision**: When two candidate blocks share the same `source_id`, only the first block encountered in deterministic compilation order is kept.
- **Rationale**: This directly implements the Phase 0 clarification, removes duplicated content cheaply, and makes precedence visible in tests.
- **Alternatives considered**:
  - Deduplicate by content hash: rejected because the clarified requirement says exact `source_id` matching for Phase 0.
  - Merge duplicate content across tiers: rejected because it complicates provenance and can obscure which source actually won.

## Decision 5: Budget against rendered block markdown and drop from the tail of each lower tier

- **Decision**: Estimate the token cost of each rendered block plus the provenance footer, then trim `nice` blocks from the end of the nice-tier list first and `should` blocks from the end of the should-tier list next.
- **Rationale**: Trimming from the tail preserves earlier, presumably more intentional caller ordering within a tier while satisfying the requirement to degrade predictably.
- **Alternatives considered**:
  - Drop largest blocks first: rejected because it changes packet shape in a less predictable way and can scramble caller intent.
  - Recompute a relevance score per block: rejected because it adds heuristics the feature brief intentionally avoids in Phase 0.

## Decision 6: Render provenance as both a sidecar list and a markdown table footer

- **Decision**: Store provenance as a structured list of `(source_type, source_id, path)` entries in the `Packet` model and append a `## Provenance` markdown table to the packet body.
- **Rationale**: The sidecar gives code a structured representation, while the footer gives humans an audit trail in the packet markdown itself.
- **Alternatives considered**:
  - Footer only: rejected because tests and downstream code benefit from structured provenance.
  - Sidecar only: rejected because the acceptance criteria require provenance to be visible in the rendered packet.
