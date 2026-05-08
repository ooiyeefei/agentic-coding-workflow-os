# Contract: Tool Adapters

## ToolAdapter

Every concrete adapter implements:

- `ingest_transcript(session_path) -> list[MemoryRecord]`
  - Reads one transcript source from disk.
  - Returns zero or more typed memory records.
  - Never writes records by itself.

- `format_context_packet(run_id, role, memory_records) -> str`
  - Builds a paste-ready markdown prompt for the target tool.
  - Includes prior decisions, relevant ADRs, and current run state.

- `detect() -> bool`
  - Detects whether the adapter's tool appears to be the active one in the current repository and process environment.

## Claude Code Adapter

- Supported transcript source: `.claude/projects/.../*.jsonl`
- Detect contract:
  - `True` when `.claude/` exists in the repo root
- Packet contract:
  - Must reference `CLAUDE.md`
  - Must mention `.claude/rules/`

## Codex Adapter

- Supported transcript source: `~/.codex/sessions/.../rollout-*.jsonl`
- Detect contract:
  - `True` only when `AGENTS.md` exists and Codex environment markers are present
- Packet contract:
  - Must reference `AGENTS.md`

## Generic Adapter

- Supported transcript source: plain markdown transcript
- Detect contract:
  - Always `False`
- Packet contract:
  - Self-contained markdown with no required repo-specific config files

## Manifest Loader

- Reads YAML files from `spanweave/adapters/manifests/`
- Rejects non-mapping YAML payloads
- Returns typed manifest models that can be asserted in tests
