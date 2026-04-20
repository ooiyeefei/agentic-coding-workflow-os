# Feature Specification: Council Tiebreaker

**Feature Branch**: `005-council-tiebreaker`  
**Created**: 2026-04-20  
**Status**: Draft  
**Input**: User description: "3-agent tiebreaker triggered on Coder↔Reviewer deadlock, majority-wins voting, ties escalate to human"

## Clarifications

### Session 2026-04-20

- Q: Which voter models should Phase 0 use by default? → A: Use `claude-opus-4-7`, `gpt-5`, and `claude-sonnet-4-6` as the default three-voter panel, while allowing callers to override the list with three distinct model ids.
- Q: What output format should each voter produce? → A: Each voter must return exactly one structured verdict from `COMPATIBLE_WITH_CODER`, `COMPATIBLE_WITH_REVIEWER`, or `NEITHER`; freeform vote parsing is out of scope.
- Q: How should the council satisfy the memory requirement before full W06 lands? → A: Persist each `CouncilReport` as a filesystem-backed markdown record under `.atelier/memory/council_reports/` with YAML frontmatter plus a markdown body, so the demo stays audit-friendly without requiring the whole W06 knowledge plane.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Break A Deadlock By Majority Vote (Priority: P1)

As a workflow engine, I can send a Coder position and a Reviewer position to three council voters and receive one tiebreak verdict based on the majority vote, so deadlocked reviews can advance without inventing a fake consensus.

**Why this priority**: Majority voting is the entire value of the Phase 1 peek. If the council cannot turn a deadlock into a deterministic outcome or a human escalation, the feature is not demoable.

**Independent Test**: Mock three LLM adapters, return controlled vote combinations, and confirm the council returns the majority verdict or `HUMAN_REQUIRED` for a 1-1-1 split.

**Acceptance Scenarios**:

1. **Given** three voters where two return `COMPATIBLE_WITH_CODER` and one returns `COMPATIBLE_WITH_REVIEWER`, **When** `tiebreak(...)` runs, **Then** it returns `COMPATIBLE_WITH_CODER`.
2. **Given** three voters where two return `COMPATIBLE_WITH_REVIEWER` and one returns `NEITHER`, **When** `tiebreak(...)` runs, **Then** it returns `COMPATIBLE_WITH_REVIEWER`.
3. **Given** three voters that produce one `COMPATIBLE_WITH_CODER`, one `COMPATIBLE_WITH_REVIEWER`, and one `NEITHER`, **When** `tiebreak(...)` runs, **Then** it returns `HUMAN_REQUIRED`.

---

### User Story 2 - Enforce Capability-Gated Voting (Priority: P2)

As a council orchestrator, I can run each voter through W02 capability checks before any provider call happens, so the tiebreaker never silently downgrades the voting protocol when a requested model cannot honor structured voting.

**Why this priority**: The product’s LLM-agnostic claim depends on capability-checked routing. A council that quietly falls back to incompatible models would undercut the adapter layer’s contract.

**Independent Test**: Inject manifests and adapters so one model lacks required capabilities, then confirm the council raises a capability error before calling the provider; also verify the three valid voter calls are launched concurrently.

**Acceptance Scenarios**:

1. **Given** a requested model manifest that lacks the required tool-use support for structured verdict submission, **When** `tiebreak(...)` prepares the voter call, **Then** it raises `UnsupportedCapabilityError` instead of degrading the prompt or parser.
2. **Given** three compatible voter models, **When** `tiebreak(...)` runs, **Then** it launches the three model calls concurrently instead of serially.
3. **Given** a caller supplies an override list of three distinct model ids, **When** `tiebreak(...)` runs, **Then** it uses those models instead of the Phase 0 default trio.

---

### User Story 3 - Persist An Auditable Council Report (Priority: P3)

As a reviewer or demo operator, I can inspect a persisted council report showing the final verdict and every per-model vote, so the escalation step is audit-friendly rather than a black box.

**Why this priority**: The council is meant to be a visible demo beat and a future building block for MAD. Without an auditable report, the vote is not reproducible enough to trust.

**Independent Test**: Run `tiebreak(...)` with mocked voters and a temporary memory directory, then confirm it writes one report file containing the final verdict, the selected model ids, and the full vote breakdown.

**Acceptance Scenarios**:

1. **Given** a completed council vote, **When** `tiebreak(...)` finishes, **Then** it writes a `CouncilReport` memory record containing the coder position, reviewer position, context summary, per-model votes, and the final verdict.
2. **Given** the council reaches `HUMAN_REQUIRED`, **When** the report is written, **Then** the memory record still contains the full 1-1-1 breakdown instead of collapsing the disagreement into a generic failure.
3. **Given** memory persistence fails, **When** the council attempts to finalize the decision, **Then** the failure is surfaced to the caller instead of silently dropping the audit record.

### Edge Cases

- What happens when the caller supplies fewer than three models, more than three models, or duplicate model ids?
- What happens when a voter response is missing or does not validate to one of the three allowed verdicts?
- What happens when one provider call fails while the other two succeed?
- How does the council serialize non-string `context` payloads into a stable voter prompt and memory record?
- What happens when the default council panel is requested but a shipped manifest for one of those models is missing?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define a `Verdict` enum in `atelier/council/schema.py` with `COMPATIBLE_WITH_CODER`, `COMPATIBLE_WITH_REVIEWER`, `NEITHER`, and `HUMAN_REQUIRED`.
- **FR-002**: The system MUST define a structured `CouncilReport` model that records the coder position, reviewer position, rendered context, selected models, per-model votes, and final verdict.
- **FR-003**: The system MUST expose `tiebreak(coder_position, reviewer_position, context, models)` from `atelier/council/tiebreaker.py`.
- **FR-004**: `tiebreak(...)` MUST require exactly three distinct voter model ids, using the Phase 0 default trio when the caller does not supply an override list.
- **FR-005**: The council MUST build each voter through W02 adapters and manifests rather than hardcoding provider clients directly.
- **FR-006**: Each voter MUST require W02 capabilities that can guarantee structured verdict submission, using a provider-neutral tool call protocol instead of freeform text parsing.
- **FR-007**: The council MUST validate model capabilities before any provider call and MUST raise `UnsupportedCapabilityError` on mismatch instead of degrading the protocol.
- **FR-008**: The council MUST send the three voter requests concurrently.
- **FR-009**: Each voter prompt MUST present the two positions plus context and MUST instruct the model to return only one allowed verdict.
- **FR-010**: The council MUST treat a 2-1 split as the winning majority verdict.
- **FR-011**: The council MUST treat a 1-1-1 split as `HUMAN_REQUIRED`.
- **FR-012**: The council MUST persist a `CouncilReport` memory record with the full vote breakdown under `.atelier/memory/council_reports/`.
- **FR-013**: The council MUST not silently discard persistence failures when writing the `CouncilReport`.
- **FR-014**: `tests/test_council.py` MUST cover majority-for-coder, majority-for-reviewer, 1-1-1 tie, capability-check enforcement, and memory-record persistence.

### Key Entities *(include if feature involves data)*

- **Verdict**: The council’s allowed outcomes for each voter and the overall tiebreak result.
- **CouncilVote**: One model’s verdict plus its provider identity and any normalized response metadata needed for debugging.
- **CouncilReport**: The persisted audit record for one council escalation, including positions, context, selected models, all votes, and the final verdict.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `tests/test_council.py` passes locally with mocked adapters and no live API calls.
- **SC-002**: In the majority fixture, `tiebreak(...)` returns the verdict supported by two of the three voters.
- **SC-003**: In the 1-1-1 fixture, `tiebreak(...)` returns `HUMAN_REQUIRED`.
- **SC-004**: The council raises `UnsupportedCapabilityError` before any provider call when a requested voter model lacks the required tool-use capability for structured verdict submission.
- **SC-005**: A successful council run writes one `CouncilReport` memory record that includes all three votes and the final verdict.

## Assumptions

- Phase 0 only needs a minimal council protocol; anonymized debate rounds, chairman synthesis, and multi-round MAD stay out of scope.
- The council can reuse W02 manifests and adapter implementations directly without waiting for a broader workflow engine abstraction.
- A lightweight council-specific memory writer is acceptable until W06 lands, as long as the persisted record stays filesystem-first and parseable.
- The caller provides already-formed Coder and Reviewer positions; the council does not derive those positions itself.
