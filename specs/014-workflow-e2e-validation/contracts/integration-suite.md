# Contract: Integration Validation Surface

## Inputs

- Demo issue source: `demo/issue.md`
- Demo issue metadata: `demo/issue.meta.yaml`
- Demo app root: `demo/app`
- Workflow definition: `.atelier/defaults/workflows/speckit-loop.yaml`

## Environment Variables

- `ATELIER_INTEGRATION_REAL_LLM`
  - `0` or unset: deterministic mock mode
  - `1`: opt into real persona execution where supported
- `OPENAI_API_KEY`
  - Required only for real mode when OpenAI-backed personas are selected
- `ANTHROPIC_API_KEY`
  - Required only for real mode when Anthropic-backed personas are selected

## Local Runner Contract

`scripts/run-e2e.sh` must:

1. Fail fast when `uv` is unavailable.
2. Assume dependencies were installed with `uv sync`.
3. Default to mock mode unless `ATELIER_INTEGRATION_REAL_LLM=1` is already exported.
4. Execute the integration validation from repository root without requiring pre-existing `.atelier/` contents.

## CI Contract

`.github/workflows/ci.yaml` must:

1. Trigger on every push and pull request.
2. Run separate jobs for:
   - `ruff`
   - `pyright`
   - unit tests
   - integration tests
3. Use Python 3.11.
4. Run integration tests in default mock mode.

## Artifact Contract

The E2E test must verify that a completed run contains:

- `run.md`
- `workflow_state.yaml`
- for every stage:
  - `packet.md`
  - `transcript.jsonl`
  - `evidence.md`
  - `evidence.json`
  - `.complete`
- memory records under `.atelier/memory/decisions/` and `.atelier/memory/rejected_alternatives/` when ADR synthesis input is required
- synthesized ADR files under `docs/adr/`
