# Feature Specification: Context Compiler

**Feature Branch**: `006-context-compiler`  
**Created**: 2026-04-20  
**Status**: Draft  
**Input**: User description: "Context Compiler: priority-tier packet assembly with token budgets and provenance"

## Clarifications

### Session 2026-04-20

- Q: What deduplication strategy should Phase 0 use when multiple sources describe the same block? → A: Deduplicate by exact `source_id` match only; the first occurrence in deterministic compilation order wins.
- Q: What happens when the must-have tier alone exceeds the requested token budget? → A: Raise `BudgetExceededError`; the compiler must not drop must-tier content automatically.
- Q: How should provenance appear in the rendered packet? → A: Append a deterministic provenance footer block to the packet markdown and mirror the same entries in a structured provenance sidecar.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Compile A Priority-Aware Packet (Priority: P1)

As a workflow engine, I can compile an objective plus prioritized context sources into one deterministic packet so an agent receives the most important context first without manual copy-paste.

**Why this priority**: This is the core value of the Context Compiler. If it cannot produce a deterministic packet that honors priority tiers, the product does not replace manual packet assembly.

**Independent Test**: Call `compile_packet(...)` with fixture sources under a roomy budget and confirm the output packet markdown is deterministic, includes all eligible blocks in stable order, and renders the provenance footer.

**Acceptance Scenarios**:

1. **Given** an objective and a set of must, should, and nice sources whose combined estimate fits within budget, **When** `compile_packet(...)` runs, **Then** it returns one deterministic packet containing every included block and a provenance footer.
2. **Given** the same inputs are compiled multiple times, **When** no source content or budget changes, **Then** the packet body and provenance sidecar are byte-for-byte identical.
3. **Given** sources from multiple supported source types, **When** the packet is compiled, **Then** each included block is labeled with its source metadata and grouped in deterministic priority-preserving order.

---

### User Story 2 - Enforce Budget By Dropping Lower Tiers First (Priority: P2)

As an operator, I can trust the compiler to respect a token budget by dropping lower-priority context before higher-priority context so expensive packets degrade predictably instead of arbitrarily.

**Why this priority**: Budget enforcement is the mechanism that turns packet composition into a usable production feature. Without predictable trimming, the compiler is not safe to automate.

**Independent Test**: Compile the same fixture sources under progressively tighter budgets and verify nice-tier blocks are dropped first, then should-tier blocks, while must-tier blocks are preserved.

**Acceptance Scenarios**:

1. **Given** a packet is over budget only because of nice-tier sources, **When** `compile_packet(...)` runs, **Then** all nice-tier blocks are dropped before any should-tier blocks are considered.
2. **Given** a packet still exceeds budget after all nice-tier blocks are removed, **When** `compile_packet(...)` runs, **Then** should-tier blocks are dropped in deterministic reverse-priority order until the packet fits.
3. **Given** must-tier content alone exceeds the requested budget, **When** `compile_packet(...)` runs, **Then** it raises `BudgetExceededError` instead of dropping must-tier content.

---

### User Story 3 - Preserve Provenance And Deduplicate Sources (Priority: P3)

As a reviewer, I can inspect which inputs made it into the packet and avoid duplicate blocks so I can audit packet assembly without reading repeated content.

**Why this priority**: Provenance and deduplication make packet assembly trustworthy. Without them, teams cannot explain why a packet contains certain context or verify that the compiler is not wasting budget on duplicates.

**Independent Test**: Compile fixture sources containing duplicate `source_id` values and verify only the first deterministic occurrence is included while the provenance footer and sidecar list exactly the included blocks.

**Acceptance Scenarios**:

1. **Given** two source entries share the same `source_id`, **When** `compile_packet(...)` runs, **Then** only the first deterministic occurrence is included in the packet.
2. **Given** a packet includes blocks from several source types, **When** compilation completes, **Then** the provenance sidecar contains one `(source_type, source_id, path)` tuple per included block in packet order.
3. **Given** a rendered packet body, **When** a reviewer reads its footer block, **Then** they can identify every included source type, source id, and path without consulting source code.

### Edge Cases

- What happens when the requested budget exactly equals the estimated size of all must-tier and should-tier content?
- What happens when a source has no filesystem path, such as issue text or the explicit objective?
- What happens when duplicate `source_id` values appear across different source types or tiers?
- What happens when the objective is empty but sources are present?
- What happens when a single oversized must-tier block causes the entire packet to exceed budget?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide `compile_packet(objective, sources, budget_tokens) -> Packet` in `atelier/compiler/compiler.py`.
- **FR-002**: The system MUST define a `Packet` model that stores the compiled markdown body plus a structured provenance sidecar for every included block.
- **FR-003**: The system MUST define source models in `atelier/compiler/sources.py` for `IssueText`, `RepoRule`, `ADR`, `SampleDoc`, `WorktreeRef`, `Objective`, `ExactCommands`, and `AcceptanceGate`.
- **FR-004**: Every source model MUST declare one priority tier from `must`, `should`, or `nice`.
- **FR-005**: The compiler MUST compile sources in deterministic order, preserving tier priority before lower-tier content and preserving stable ordering within the same tier.
- **FR-006**: Phase 0 deduplication MUST use exact `source_id` matching only and MUST retain the first deterministic occurrence of any duplicate block.
- **FR-007**: The compiler MUST estimate token usage with the Phase 0 approximation `len(text) * 4 / 3`, rounded up to an integer token count.
- **FR-008**: Budget enforcement MUST drop `nice` tier blocks before `should` tier blocks and MUST never drop `must` tier blocks.
- **FR-009**: When all must-tier content alone exceeds the requested budget, the compiler MUST raise `BudgetExceededError`.
- **FR-010**: Each included block MUST record provenance as a `(source_type, source_id, path)` tuple in `atelier/compiler/provenance.py`.
- **FR-011**: The rendered packet markdown MUST end with a provenance footer block that lists every included source in deterministic packet order.
- **FR-012**: `tests/test_compiler.py` MUST cover compilation within budget, compilation under a tight budget that drops lower tiers, deduplication by `source_id`, and the impossible-budget error path.

### Key Entities *(include if feature involves data)*

- **ContextSource**: A typed input block with a source type, source id, optional path, priority tier, title, and markdown content.
- **Packet**: The compiled output containing packet markdown plus the provenance sidecar for included blocks.
- **ProvenanceEntry**: A structured tuple recording `(source_type, source_id, path)` for an included block.
- **BudgetDecision**: The deterministic decision about whether a candidate block is included, dropped for budget, or rejected because must-tier content exceeds budget.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Compiling the fixture sources under an `8000` token budget produces deterministic packet markdown that remains byte-for-byte stable across repeated runs.
- **SC-002**: Under a tight budget, fixture compilation drops all necessary nice-tier blocks before dropping any should-tier blocks.
- **SC-003**: Under a tighter budget, fixture compilation drops should-tier blocks only after all nice-tier blocks have already been removed.
- **SC-004**: When must-tier content alone exceeds budget, `compile_packet(...)` raises `BudgetExceededError`.
- **SC-005**: Duplicate fixture sources that share a `source_id` appear only once in the packet body and only once in the provenance footer.
- **SC-006**: Unit tests covering within-budget, tight-budget, dedupe, and impossible-budget scenarios pass locally.

## Assumptions

- Phase 0 only needs a deterministic in-memory compiler; persistence, caching, and fuzzy deduplication remain out of scope.
- Source content is already available as markdown-ready text when passed into the compiler; this feature does not fetch or read source files itself.
- The packet body may include lightweight source headings or labels, but the provenance footer is the authoritative human-readable source listing.
- Budget estimation accuracy only needs to be directionally conservative for Phase 0; replacing the approximation with a model-specific tokenizer can happen later.
