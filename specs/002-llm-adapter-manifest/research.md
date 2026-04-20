# Research: LLM Adapter Manifest

## Decision: Normalize adapter I/O with shared Pydantic models

- **Rationale**: Shared input and output models make Anthropic and OpenAI adapters interchangeable for personas and keep audit-log consumers insulated from provider response shapes.
- **Alternatives considered**: Passing raw SDK objects through the persona layer would leak provider-specific conditionals and undermine swappability.

## Decision: Use Anthropic Messages API and OpenAI Responses API

- **Rationale**: Both APIs support text generation, tool use, and structured response handling while exposing token usage that can be normalized into a shared response contract.
- **Alternatives considered**: OpenAI Chat Completions would simplify message serialization but is less aligned with current built-in tool capabilities than the Responses API.

## Decision: Treat `long_context` as a minimum numeric requirement

- **Rationale**: A numeric threshold makes routing composable and lets a 200k or 1M token model satisfy a smaller 128k requirement without special-case logic.
- **Alternatives considered**: Representing long context as a boolean would lose routing precision and force personas to encode token thresholds elsewhere.

## Decision: Raise on capability mismatch instead of downgrading

- **Rationale**: Explicit failure prevents silent provider swaps that violate persona expectations and aligns with the roadmap rule that capabilities must be real rather than claimed.
- **Alternatives considered**: Best-effort downgrade would hide routing mistakes and produce hard-to-audit behavior changes.

## Decision: Keep model selection data in YAML manifests and preserve caller order

- **Rationale**: YAML manifests satisfy the no-hardcoded-model-strings rule, and preserving caller order keeps routing deterministic without inventing an implicit cost-optimization policy in this slice.
- **Alternatives considered**: Hardcoded provider defaults would violate the issue constraints; cheapest-match routing would add policy that was not requested.

## Decision: Record cost per call on the normalized response

- **Rationale**: Per-call cost is the right granularity for downstream audit aggregation and can be computed immediately from manifest pricing plus provider token usage.
- **Alternatives considered**: Run-level aggregation inside the adapter layer would couple unrelated workflow concerns into a low-level transport boundary.
