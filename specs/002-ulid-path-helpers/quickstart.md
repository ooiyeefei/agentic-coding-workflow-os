# Quickstart: ULID Path Helpers

## Verify the feature

1. Run `pytest tests/test_ulid.py tests/test_paths.py tests/test_fs.py -v --cov=spanweave.util --cov-report=term-missing`.
2. Run `ruff check spanweave/util tests/test_ulid.py tests/test_paths.py tests/test_fs.py`.
3. Run `pyright spanweave/util`.

## Manual spot checks

1. Generate a run ID and confirm it starts with `run_`.
2. Generate 100 run IDs, sort them lexicographically, and confirm the order matches creation order.
3. Build a stage directory from a valid run ID, sequence `1`, and stage name `Specify`, then confirm the path ends with `.spanweave/runs/<run_id>/stages/001-specify`.
4. Create a destination file, simulate a replacement failure during `atomic_write`, and confirm the destination bytes remain unchanged.
