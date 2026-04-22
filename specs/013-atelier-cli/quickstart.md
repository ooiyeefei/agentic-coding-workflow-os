# Quickstart: Atelier CLI

## Verify the feature

1. Run `python3 -m pytest tests/test_cli.py -q`.
2. Run `atelier --help`.
3. Run `atelier run list --repo . --json`.

## Manual spot checks

1. In a temporary repository, run `atelier init --repo /tmp/atelier-cli-demo`.
2. Start a workflow with `atelier run --issue 42 --repo /tmp/atelier-cli-demo`.
3. List runs in human mode with `atelier run --repo /tmp/atelier-cli-demo list`.
4. List runs in JSON mode with `atelier run --repo /tmp/atelier-cli-demo list --json`.
5. Show one run with `atelier run --repo /tmp/atelier-cli-demo show <run_id>`.
6. If the run is waiting for a completed gate approval, resume it with `atelier run --repo /tmp/atelier-cli-demo resume <run_id> --approve`.
7. Search artifacts with `atelier grep approval --repo /tmp/atelier-cli-demo --json`.
8. Confirm cleanup with `atelier cleanup <run_id> --repo /tmp/atelier-cli-demo --yes`.
9. Check daemon lifecycle with `atelier daemon start --repo /tmp/atelier-cli-demo`, `atelier daemon status --repo /tmp/atelier-cli-demo --json`, and `atelier daemon stop --repo /tmp/atelier-cli-demo`.
