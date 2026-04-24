# Research: Tool Adapter Layer

## Decision 1: Use deterministic transcript markers for Phase 0 extraction

- **Decision**: Normalize transcript text and extract typed memory records from explicit markers such as `Decision:`, `Finding:`, and `Rejected:`.
- **Rationale**: This keeps tests offline, deterministic, and fast while still exercising the adapter layer end to end.
- **Alternatives considered**:
  - Use the existing LLM adapter layer during ingestion. Rejected for this slice because unit tests must not depend on live model calls or credentials.
  - Extract every imperative sentence as a decision. Rejected because it would overproduce noisy records from verbose tool sessions.

## Decision 2: Treat Claude Code and Codex transcript formats as different normalizers over one shared extraction pipeline

- **Decision**: Each adapter will parse its native session format into normalized text entries, then reuse a shared heuristic extraction layer from the base module.
- **Rationale**: The file formats differ materially, but the record-construction rules should stay consistent across tools.
- **Alternatives considered**:
  - Build completely separate extraction logic in each adapter. Rejected because it duplicates record construction and makes future tool additions harder.
  - Force all adapters through one generic JSONL parser. Rejected because Claude Code and Codex payload shapes are too different for one brittle parser.

## Decision 3: Support Claude Code `.claude/projects/.../*.jsonl` event logs directly

- **Decision**: Claude Code ingestion will target the real event-per-line JSONL format observed under `.claude/projects/`, including top-level event records and `message.role` blocks.
- **Rationale**: This is the durable session artifact that contains both user and assistant content plus session metadata.
- **Alternatives considered**:
  - Parse only copied markdown summaries. Rejected because the acceptance criteria require JSONL ingestion.
  - Depend on one exact filename such as `session.jsonl`. Rejected because the observed format uses per-session UUID filenames.

## Decision 4: Support Codex rollout logs instead of `history.jsonl`

- **Decision**: Codex ingestion will target `~/.codex/sessions/.../rollout-*.jsonl`.
- **Rationale**: The rollout logs contain developer, user, assistant, reasoning, commentary, and tool-event records; `history.jsonl` only stores user input history and loses assistant decisions.
- **Alternatives considered**:
  - Parse `history.jsonl`. Rejected because it cannot recover the assistant-side decisions needed for cross-tool transfer.
  - Depend on local sqlite state. Rejected for Phase 0 because the rollout JSONL is already sufficient and easier to fixture.

## Decision 5: Format packets as tool-native wrappers over common context sections

- **Decision**: Packet formatting will share common sections for prior decisions, relevant ADRs, and current run state, then wrap them in tool-specific instruction framing.
- **Rationale**: The content should stay equivalent while the outer voice matches the destination tool's conventions.
- **Alternatives considered**:
  - Emit the compiler's generic packet format unchanged. Rejected because the acceptance criteria explicitly require CLAUDE.md-style and AGENTS.md-style differences.
  - Build totally different content selection rules per tool. Rejected because the problem is convention mismatch, not content mismatch.
