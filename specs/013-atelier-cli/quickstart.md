# Quickstart: Spanweave CLI

## Verify the feature

1. Run `python3 -m pytest tests/test_cli.py -q`.
2. Run `spanweave --help`.
3. Run `spanweave run list --repo . --json`.

## Manual spot checks

1. In a temporary repository, run `spanweave init --repo /tmp/spanweave-cli-demo`.
2. Start a workflow with `spanweave run --issue 42 --repo /tmp/spanweave-cli-demo`.
3. List runs in human mode with `spanweave run --repo /tmp/spanweave-cli-demo list`.
4. List runs in JSON mode with `spanweave run --repo /tmp/spanweave-cli-demo list --json`.
5. Show one run with `spanweave run --repo /tmp/spanweave-cli-demo show <run_id>`.
6. If the run is waiting for a completed gate approval, resume it with `spanweave run --repo /tmp/spanweave-cli-demo resume <run_id> --approve`.
7. Search artifacts with `spanweave grep approval --repo /tmp/spanweave-cli-demo --json`.
8. Confirm cleanup with `spanweave cleanup <run_id> --repo /tmp/spanweave-cli-demo --yes`.
9. Check daemon lifecycle with `spanweave daemon start --repo /tmp/spanweave-cli-demo`, `spanweave daemon status --repo /tmp/spanweave-cli-demo --json`, and `spanweave daemon stop --repo /tmp/spanweave-cli-demo`.
