# Quickstart: Workflow E2E Validation

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Run the local end-to-end validation in default mock mode:

   ```bash
   ./scripts/run-e2e.sh
   ```

3. Run the focused integration modules directly:

   ```bash
   uv run pytest tests/integration/test_component_integration.py tests/integration/test_e2e_workflow.py -q
   ```

4. Run the full repository validation locally:

   ```bash
   uv run ruff check .
   uv run pyright spanweave/compiler spanweave/evidence spanweave/git spanweave/memory spanweave/personas spanweave/workflow tests/integration
   uv run pytest tests -q
   ```

5. Opt into real persona execution only when you have provider credentials available:

   ```bash
   export SPANWEAVE_INTEGRATION_REAL_LLM=1
   export OPENAI_API_KEY=...
   export ANTHROPIC_API_KEY=...
   ./scripts/run-e2e.sh
   ```

6. The GitHub Actions workflow mirrors the same gates with mock mode as the default integration path.
