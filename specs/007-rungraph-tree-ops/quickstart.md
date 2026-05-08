# Quickstart: Run Graph Tree Ops

## Verify the feature

1. Run `uv run pytest tests/test_rungraph.py -v`.
2. Run `uv run ruff check spanweave/rungraph tests/test_rungraph.py`.
3. Run `uv run pyright spanweave/rungraph`.

## Manual spot checks

1. Create a run and confirm `.spanweave/runs/<run_id>/run.md`, `audit.jsonl`, `stages/`, and `.lock` exist.
2. Create three stages and confirm their directory names are `001-specify`, `002-clarify`, and `003-implement`.
3. Mark only the first two stages complete and confirm `next_stage_to_execute(run_id)` returns `003-implement`.
4. Leave a stage partially populated without `.complete` and confirm resume still selects that stage.
5. Hold a run lock in one process and confirm a second process blocks until the first exits or releases it.
