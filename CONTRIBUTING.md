# Contributing to Spanweave

## Quick start for contributors

1. Fork + clone
2. `uv sync` to install deps
3. `uv run pytest` to run tests (should see 448+ passing)
4. Make changes on a feature branch
5. `uv run ruff check .` + `uv run pyright` must pass
6. Open a PR

## Architecture

- `spanweave/` — Python control plane (CLI + library)
- `.spanweave/` — user's workspace (memory, runs, workflows)
- `tests/` — unit + integration tests

## License

Apache 2.0. By contributing, you agree your contributions are under the same license.
