# Quickstart: Swappability Demo

## Verify the feature

1. Run `python3 -m pytest tests/test_swap_demo.py -v`.
2. Run `python3 demo/swap-demo.py --mode mock`.
3. If `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` are available, run `python3 demo/swap-demo.py --mode live`.
4. Read `demo/swap-demo-output/claude/evidence.md` and `demo/swap-demo-output/codex/evidence.md`.
5. Read `demo/swap-demo.md` aloud and confirm it fits inside 60 seconds.

## Manual spot checks

1. Confirm the two successful runs target different backend labels but the same fixture bug and the same review instructions.
2. Confirm both Evidence Packs include executed-check output from the failing pytest run.
3. Confirm the console summary includes an `UnsupportedCapabilityError` message for the incompatible-manifest proof.
4. Confirm `--claude-model` and `--codex-model` override the defaults without source edits.
5. In an environment without API keys, confirm `--mode auto` falls back to mock mode and marks the Evidence Packs accordingly.
