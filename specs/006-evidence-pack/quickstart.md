# Quickstart: Evidence Pack

1. Construct a deterministic `EvidencePack` with a fixed timestamp, at least one finding, one execution record, and one audit ULID.
2. Call `generate(run_id, "001-review", pack)`.
3. Open `.spanweave/runs/<run_id>/stages/001-review/evidence.json` and confirm:
   - `schema_version` equals `"1.0"`
   - the JSON parses back through `EvidencePack.model_validate_json(...)`
   - execution output is redacted before persistence
4. Open the matching `evidence.md` and confirm:
   - the verdict banner is visible near the top
   - findings are grouped by severity
   - execution output appears inside fenced code blocks
   - audit references render as markdown links to `../../audit.jsonl#<ulid>`
5. Run `pytest tests/test_evidence.py -v`.
