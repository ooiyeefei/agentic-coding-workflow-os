# Feature Specification: Swappability Demo

**Feature Branch**: `005-swappability-demo`  
**Created**: 2026-04-20  
**Status**: Draft  
**Input**: User description: "swappability demo script + captured Evidence Packs from Claude vs Codex review of same input"

## Clarifications

### Session 2026-04-20

- Q: What code should the demo reviewer analyze? → A: Generate a tiny standalone Python fixture around a `rolling_window_average(...)` helper with a planted off-by-one bug plus one failing pytest that proves the defect.
- Q: Which models should the demo use by default? → A: Default the Claude side to `claude-sonnet-4-6` and the Codex/OpenAI side to `gpt-5`, while allowing command-line or environment overrides without code edits.
- Q: How literal must "the same Reviewer persona" be for this demo? → A: Reuse the shipped Reviewer system-prompt body and the same tool contract on both runs, but keep the demo's routing requirement at `tool_use=True` so Claude can participate without changing W04's default Reviewer routing rules.
- Q: How should the demo behave when live API credentials are unavailable during local review? → A: Auto-fallback to deterministic mock responders that preserve the same review loop shape, still write both Evidence Packs, and clearly mark the run mode in the output.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run The Same Review Twice (Priority: P1)

As a demo operator, I can run one script that sends the same reviewer protocol and the same buggy input to a Claude backend and a Codex/OpenAI backend, so the audience sees vendor swappability instead of vendor lock-in.

**Why this priority**: The core product claim is that the interface stays fixed while the model backend changes. If the demo does not show the same review flow across two providers, W19 fails.

**Independent Test**: Run the demo script once, inspect both generated Evidence Packs, and confirm each one records a review against the same fixture, the same failing check, and the same planted bug.

**Acceptance Scenarios**:

1. **Given** the demo script has access to a Claude-capable manifest and a Codex/OpenAI-capable manifest, **When** the operator runs the script, **Then** it executes the same review loop against both backends and writes one Evidence Pack per backend.
2. **Given** both backends review the planted off-by-one fixture, **When** each run completes, **Then** both Evidence Packs identify the boundary bug and include the execution evidence that exposed it.
3. **Given** the operator wants to swap models, **When** they change configuration inputs instead of editing source code, **Then** the script routes to the requested manifests and keeps the rest of the review flow unchanged.

---

### User Story 2 - Prove Capability Gating Works (Priority: P2)

As a reviewer of the demo asset, I can see the negative case where a model without required tool support is rejected, so the swappability claim looks engineered rather than staged.

**Why this priority**: Swappability without capability checks is just a marketing line. The demo needs a visible failure path that proves the manifest gate is real.

**Independent Test**: Run the demo's incompatible-model check and confirm it raises `UnsupportedCapabilityError` before the review loop starts.

**Acceptance Scenarios**:

1. **Given** the demo requests a model manifest that does not offer `tool_use`, **When** the script validates the backend, **Then** it raises `UnsupportedCapabilityError` instead of attempting the review.
2. **Given** the operator runs the normal demo path, **When** the script completes, **Then** the output summarizes the expected incompatible-model failure alongside the successful Claude and Codex runs.

---

### User Story 3 - Narrate The Demo In Under One Minute (Priority: P3)

As a presenter, I can read a concise narration script that frames the swap, the bug, and the manifest guardrail in under 60 seconds, so W19 fits inside the Phase 0 live-demo slot.

**Why this priority**: A correct script that takes too long to explain still misses the demo window.

**Independent Test**: Read the narration aloud at a normal speaking pace and confirm it fits within 60 seconds while still naming the two backends, the planted bug, and the unsupported-capability check.

**Acceptance Scenarios**:

1. **Given** the presenter reads `demo/swap-demo.md` aloud, **When** the narration finishes, **Then** it fits within 60 seconds and clearly states that the same reviewer protocol ran against two different backends.
2. **Given** the audience sees the Evidence Packs, **When** the narration reaches the guardrail beat, **Then** it explains that an incompatible model is rejected because the manifest does not satisfy the required tool capability.

### Edge Cases

- What happens when one provider credential is missing but the other is present?
- What happens when a live model returns narrative output without using the supplied tools?
- What happens when both live provider credentials are missing during local review or CI?
- What happens when the two Evidence Packs reach different wording or verdict structure while still finding the same bug?
- What happens when a user requests a model name that is not present in the shipped manifests?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a demo runner at `demo/swap-demo.py` that executes the same reviewer prompt body, the same tool contract, and the same buggy review input against a Claude backend and a Codex/OpenAI backend.
- **FR-002**: The demo runner MUST generate or prepare one standalone review fixture with a known off-by-one bug plus one executable check that exposes the bug.
- **FR-003**: The demo runner MUST write Markdown Evidence Packs to `demo/swap-demo-output/claude/evidence.md` and `demo/swap-demo-output/codex/evidence.md` on every successful run.
- **FR-004**: Each Evidence Pack MUST record the backend label, provider/model identity, run mode, the executed check output, and the reviewer’s final write-up.
- **FR-005**: The successful Claude and Codex runs MUST operate through the same review-loop shape, including the same tool definitions and the same review instructions.
- **FR-006**: The demo MUST prove the planted bug by recording evidence from an executed check, not only from static code commentary.
- **FR-007**: The demo MUST default to `claude-sonnet-4-6` for the Claude side and `gpt-5` for the Codex/OpenAI side, and MUST let the operator override those choices without editing source code.
- **FR-008**: The demo MUST validate required backend capabilities before starting a review and MUST require `tool_use=True` for the review loop.
- **FR-009**: When a selected or synthetic model lacks `tool_use`, the demo MUST raise or surface `UnsupportedCapabilityError` as an expected failure case.
- **FR-010**: The narration script at `demo/swap-demo.md` MUST describe the two successful runs, the planted bug, and the incompatible-model guardrail in language that fits within 60 seconds when read aloud.
- **FR-011**: When live provider credentials are absent, the demo runner MUST fall back to deterministic mock responders that still write both Evidence Packs and visibly mark the run as non-live.
- **FR-012**: The demo runner MUST preserve different backend outputs when both runs succeed; the two packs may differ in wording, but they MUST not collapse into one reused artifact.

### Key Entities *(include if feature involves data)*

- **SwapDemoFixture**: The generated review target containing the planted off-by-one bug and the check that exposes it.
- **SwapDemoBackend**: One configured review target, including label, manifest identity, provider, and run mode.
- **SwapDemoRun**: A single backend execution of the review loop, including tool transcript, reviewer response, and output path.
- **Evidence Pack**: The human-readable artifact proving what the backend reviewed, what evidence it gathered, and what bug it reported.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single execution of the demo runner writes both Markdown Evidence Packs to the expected output paths.
- **SC-002**: Both generated Evidence Packs explicitly identify the planted off-by-one bug and include executed-check evidence showing the failure.
- **SC-003**: The demo runner prints or records the expected `UnsupportedCapabilityError` path for a model that lacks `tool_use`.
- **SC-004**: The default demo path does not require source edits to swap between the configured Claude and Codex/OpenAI models.
- **SC-005**: Reading `demo/swap-demo.md` aloud at a normal speaking pace completes within 60 seconds.

## Assumptions

- W19 is allowed to ship as a demo-focused asset under `demo/` without changing W04's default `Reviewer` routing requirements.
- Reusing the shipped Reviewer prompt body is sufficient to count as "the same Reviewer persona" for the live-demo beat, even though the W19 runner binds capabilities directly for this narrower scenario.
- The demo fixture can be generated by the script itself instead of living as a separately owned source file.
- Mock mode is acceptable for repository review and CI as long as the output clearly says it was not a live provider run.
