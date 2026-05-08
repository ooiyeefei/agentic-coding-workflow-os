# Research: Council Tiebreaker

## Decision 1: Use a strict tool-submitted verdict schema instead of freeform vote parsing

- **Decision**: Require each voter to submit its verdict through one provider-neutral tool call whose single enum argument is validated before tallying.
- **Rationale**: The reviewer guidance explicitly rejects freeform vote parsing. A tool-submitted schema works across the existing W02 adapters, including the default Anthropic models that do not advertise native structured outputs.
- **Alternatives considered**:
  - Parse natural-language responses with keyword matching: rejected because it invites hallucinated or partially formatted votes.
  - Require native `structured_outputs=True`: rejected because the default Phase 0 voter trio includes Anthropic manifests that do not advertise that capability in W02 today.

## Decision 2: Fan out the three votes concurrently with `asyncio.gather`

- **Decision**: Dispatch the three voter calls concurrently and wait for the full panel before tallying.
- **Rationale**: The reviewer explicitly calls out sequential calls as wasteful. The council only has three voters, so `asyncio.gather` is the simplest correct concurrency primitive.
- **Alternatives considered**:
  - Call voters sequentially: rejected because it adds latency without improving correctness.
  - Short-circuit after the first two matching votes: rejected because the full vote breakdown still needs to be persisted for auditability.

## Decision 3: Resolve voters by explicit model id against shipped manifests

- **Decision**: Accept a caller-supplied list of model ids, fall back to the default trio when none is supplied, and resolve each id against the shipped W02 manifests before constructing adapters.
- **Rationale**: The feature brief wants a default panel but allows override. Explicit model-id resolution keeps the panel predictable and makes capability failures attributable to a named manifest.
- **Alternatives considered**:
  - Route to the first three compatible manifests automatically: rejected because it makes the panel unstable as manifest ordering changes.
  - Hardcode provider SDK clients in the council module: rejected because it would bypass W02 entirely.

## Decision 4: Persist council reports as markdown memory records now, not later

- **Decision**: Add a narrow council memory writer that serializes `CouncilReport` to markdown with YAML frontmatter under `.spanweave/memory/council_reports/`.
- **Rationale**: The acceptance criteria require an auditable report, but W06 is not present on this branch. A council-specific writer satisfies the audit need while staying filesystem-first and forward-compatible with broader memory work.
- **Alternatives considered**:
  - Keep council reports in process memory only: rejected because the roadmap treats council auditability as persistent state, not session-local cache.
  - Block W21 on full W06 implementation: rejected because the issue is explicitly scoped as a narrow Phase 1 peek.

## Decision 5: Fail fast on persistence or capability errors

- **Decision**: Treat capability mismatch and report-write failure as hard errors rather than returning a verdict without auditability.
- **Rationale**: Silent degradation would violate two of the feature’s core guarantees: capability honesty and reproducible audit records.
- **Alternatives considered**:
  - Downgrade to best-effort voting when a model lacks tool-use support: rejected because it breaks W02’s contract.
  - Return the verdict even if report writing fails: rejected because that would create an invisible audit gap.
