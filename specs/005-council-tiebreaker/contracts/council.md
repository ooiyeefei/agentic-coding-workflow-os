# Contract: spanweave.council Public API

## Council Schema

- `Verdict`
- `CouncilVote`
- `CouncilReport`

**Contract**:

- `Verdict` defines the only legal vote values for the council protocol.
- `CouncilVote` represents one model's normalized vote and metadata.
- `CouncilReport` represents one completed council run and is safe to persist as a memory record.

## Tiebreaker Runtime

- `await tiebreak(coder_position, reviewer_position, context, models=None) -> Verdict`
- `DEFAULT_COUNCIL_MODELS -> tuple[str, str, str]`

**Contract**:

- When `models` is omitted, the council uses the Phase 0 default trio of `claude-opus-4-7`, `gpt-5`, and `claude-sonnet-4-6`.
- When `models` is supplied, it must contain exactly three distinct model ids.
- The council resolves each model through W02 manifests and raises `UnsupportedCapabilityError` if any voter lacks required capabilities.
- The council requires provider-neutral tool use for verdict submission and never parses freeform vote text.
- The council dispatches all three votes concurrently.
- The council returns the majority verdict on a 2-1 split and `HUMAN_REQUIRED` on a 1-1-1 split.
- The council writes one `CouncilReport` memory record for every completed run and does not silently ignore write failures.
