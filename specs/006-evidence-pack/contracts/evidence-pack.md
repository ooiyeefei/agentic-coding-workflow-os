# Evidence Pack Contract

## Public Python API

- `EvidencePack`
- `Finding`
- `CommandOutput`
- `generate(run_id: str, stage_id: str, pack: EvidencePack) -> tuple[pathlib.Path, pathlib.Path]`

## JSON Contract

Every generated `evidence.json` document contains:

- `schema_version`: `"1.0"`
- `verdict`: `APPROVED | NEEDS_REVISION | REJECTED`
- `confidence`: float in `[0.0, 1.0]`
- `findings`: array of objects with `finding_id`, `severity`, `description`, `file`, `line`, `verification`
- `execution`: array of objects with `command`, `stdout`, `stderr`, `exit_code`, `finding_ids`
- `audit_chain`: array of ULID strings
- `timestamp`: timezone-aware ISO 8601 datetime string
- `reviewer_persona_id`: string

## Filesystem Contract

- Destination directory: `.atelier/runs/<run_id>/stages/<stage_id>/`
- JSON sidecar: `evidence.json`
- Markdown sidecar: `evidence.md`

## Markdown Rendering Contract

- Top-level header identifying the Evidence Pack
- Visible verdict banner with confidence, reviewer persona, schema version, and timestamp
- Findings grouped under `RED`, `ORANGE`, and `YELLOW` headings
- Execution section with command, linked `finding_id` references, exit code, and fenced stdout/stderr blocks
- Audit chain rendered as markdown links pointing to the run-scoped `audit.jsonl`
