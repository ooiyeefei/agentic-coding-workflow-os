#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH='' cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(CDPATH='' cd "$SCRIPT_DIR/.." && pwd)"

load_env_file() {
  local env_file="$1"
  if [[ -f "$env_file" ]]; then
    set -a
    # shellcheck disable=SC1090
    . "$env_file"
    set +a
  fi
}

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install uv and run 'uv sync' before running this script." >&2
  exit 1
fi

cd "$REPO_ROOT"

load_env_file "$REPO_ROOT/.env"
load_env_file "$REPO_ROOT/.env.local"
load_env_file "$REPO_ROOT/demo/app/.env"

: "${SPANWEAVE_INTEGRATION_REAL_LLM:=0}"
export SPANWEAVE_INTEGRATION_REAL_LLM

uv run python scripts/run_e2e.py

if [[ ! -d .spanweave/runs ]]; then
  echo "Expected repo-root .spanweave/runs/ to exist after the E2E workflow run." >&2
  exit 1
fi

find .spanweave/runs -type f | sort

uv run pytest tests/integration/test_component_integration.py tests/integration/test_e2e_workflow.py -q
