# Data Model: Tool Adapter Layer

## ToolManifest

- **Fields**:
  - `capabilities: list[str]`
  - `session_format: str`
  - `config_paths: list[str]`
  - `context_injection: str`
- **Rules**:
  - Must validate from YAML mapping data.
  - `capabilities` should be non-empty and use a constrained vocabulary for shipped manifests.

## TranscriptEntry

- **Fields**:
  - `role: str`
  - `text: str`
  - `timestamp: str | None`
  - `metadata: dict[str, str]`
- **Rules**:
  - Represents one normalized conversational chunk regardless of source transcript shape.
  - Empty text entries are discarded before heuristic extraction.

## ExtractedMemoryRecord

- **Fields**:
  - Existing typed memory record fields from `Decision`, `ReviewFinding`, or `RejectedAlternative`
  - Source-specific tags such as `claude-code`, `codex`, or `generic`
- **Rules**:
  - Must validate through existing memory schemas.
  - Run and stage ids are synthesized as valid prefixed ULID identifiers when the source transcript lacks Atelier-native ids.

## ToolContextPacket

- **Fields**:
  - `tool_name`
  - `role`
  - `body`
  - `referenced_config_paths`
  - `run_summary`
- **Rules**:
  - Rendered as plain markdown text.
  - Must contain prior decisions, relevant ADRs, and current run state.

## RunStateSummary

- **Fields**:
  - `run_id`
  - `workflow`
  - `status`
  - `current_stage`
  - `waiting_reason`
  - `stages`
- **Rules**:
  - Derived from `.atelier/runs/<run_id>/workflow_state.yaml` and stage directories when available.
  - Formatting must degrade gracefully when the run directory does not exist.
