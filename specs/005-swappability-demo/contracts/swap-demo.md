# Contract: `demo/swap-demo.py`

## Invocation

- `python demo/swap-demo.py`
- `python demo/swap-demo.py --mode {auto|live|mock}`
- `python demo/swap-demo.py --claude-model <model> --codex-model <model>`

## Inputs

- Optional CLI flags for run mode and model overrides.
- Optional environment variables for model overrides and provider credentials.
- Shipped capability manifests under `.atelier/defaults/models/`.
- Shipped Reviewer prompt body under `.atelier/defaults/personas/reviewer.md`.

## Outputs

- `demo/swap-demo-output/claude/evidence.md`
- `demo/swap-demo-output/codex/evidence.md`
- Console summary that includes:
  - the effective backend pair,
  - whether each run was live or mock,
  - whether the planted bug was found,
  - the expected incompatible-manifest failure message.

## Successful Run Contract

- The script prepares one shared buggy fixture for both backends.
- The script runs the same tool-driven review loop for the Claude and Codex backends.
- Each successful backend writes a markdown Evidence Pack that includes:
  - backend label and model identity,
  - run mode,
  - executed check output,
  - tool transcript,
  - final reviewer response,
  - explicit statement that the planted off-by-one bug was or was not found.

## Guardrail Contract

- The script validates required capabilities with `CapabilityRequirements(tool_use=True)`.
- The script performs one incompatible-manifest check using a model definition that lacks `tool_use`.
- The incompatible path must surface `UnsupportedCapabilityError` and must not write a successful Evidence Pack for that failed backend.
