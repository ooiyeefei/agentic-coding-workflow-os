# agentic-coding-workflow-os Development Guidelines

## Project Structure

```text
spanweave/   # CLI + library (Python package)
tests/       # unit tests
```

## Commands

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run pyright spanweave/
```

## Code Style

Python 3.11+. Standard conventions; ruff + pyright in strict mode govern the bar.

<!-- MANUAL ADDITIONS START -->

## Auto-load context on session start

Before responding to any substantive question about this project, load prior
context from `.spanweave/memory/`:

- `.spanweave/memory/decisions/` — decisions captured from earlier sessions.
- `.spanweave/memory/shared/decisions/` — decisions promoted for team sharing.

These are captured by `spanweave extract-latest` and survive across tools and
sessions. If another agent (Claude Code, Cursor) worked on this repo before you,
their decisions are recorded here and you should build on them instead of
re-deriving them.

## Capture decisions on session end

Codex has no native session-end hook, so before ending your session run:

```bash
spanweave extract-latest --repo .
```

This stages this session's decisions into `.spanweave/memory/pending/` for
review with `spanweave review`. (Claude Code does this automatically via a Stop
hook.)

<!-- MANUAL ADDITIONS END -->
