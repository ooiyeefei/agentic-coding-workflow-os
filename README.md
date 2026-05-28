# Spanweave

> Ambient cross-tool memory for AI coding agents. Decisions live as markdown in your git repo — readable by every agent, syncable by git.

[![CI](https://github.com/ooiyeefei/agentic-coding-workflow-os/actions/workflows/ci.yaml/badge.svg)](https://github.com/ooiyeefei/agentic-coding-workflow-os/actions/workflows/ci.yaml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## The Problem

You spend two hours building context in Codex. Switch to Claude Code — start from zero. Decisions you made with one agent vanish when you open another. Every AI coding tool is a silo: context dies with the session, decisions evaporate between tools, and teams using different agents have no shared memory.

## The Solution

Spanweave captures decisions from each coding session via a local LLM (Ollama gemma/qwen) and stores them as **markdown files in your git repo** under `.spanweave/memory/`. Every agent tool already reads its convention file (CLAUDE.md, AGENTS.md, .cursorrules) — Spanweave wires those files to auto-load `.spanweave/memory/` on session start, so the next agent (Claude Code, Codex, Cursor) picks up where the last one left off.

No platform. No SaaS. No switching cost. Just markdown that any tool can read, git can sync, and humans can grep.

## Quick Start

```bash
pip install spanweave                          # or: uv pip install spanweave
ollama pull gemma4:e4b                         # local model for auto-extraction
spanweave init --tool claude-code --repo .     # one-time setup
# Done. Open Claude Code — it auto-loads decisions on start,
# and the Stop hook captures new ones when the session ends.
```

For Codex / Cursor / Windsurf, swap `--tool claude-code` for `--tool codex`, `--tool cursor`, or `--tool windsurf` (you can pass `--tool` multiple times to wire several).

## How It Works

1. **Capture.** When a coding session ends, Spanweave reads the transcript and asks a local LLM to extract decisions, findings, and rejected alternatives. Each is written as a markdown file with YAML frontmatter under `.spanweave/memory/pending/`.
2. **Review.** Run `spanweave review` to triage what was extracted — accept, edit, or dismiss. Accepted decisions land in `private/` or `shared/` per your `.spanweave/sharing.yaml` policy.
3. **Reflect.** `spanweave reflect` synthesizes higher-order lessons from your accumulated decisions using a thinking-mode local model.
4. **Promote.** `spanweave promote <id>` (or `--all-pending`) moves private decisions to `shared/` so teammates pick them up on git pull.
5. **Auto-load.** Every supported tool's convention file (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.windsurfrules`) carries a read-pointer to `.spanweave/memory/` so a fresh session loads prior context natively.

## CLI Commands

```
spanweave init             # Scaffold .spanweave/, optionally wire tool hooks (--tool)
spanweave extract          # Extract decisions from a specific transcript
spanweave extract-latest   # Extract from the most recent session (Stop-hook target)
spanweave review           # Interactively confirm pending learnings
spanweave reflect          # Synthesize lessons from accumulated decisions
spanweave promote          # Move a private decision to shared (team-visible via git)
spanweave grep             # Regex search across .spanweave/
spanweave skill_feedback   # Inspect and apply derived feedback rules
```

## Supported Tools

| Tool         | Read (load context)        | Write (capture)              |
|--------------|----------------------------|------------------------------|
| Claude Code  | CLAUDE.md                  | Automatic via Stop hook      |
| Codex        | AGENTS.md                  | Manual (run `extract-latest`) |
| Cursor       | .cursorrules               | Manual (run `extract-latest`) |
| Windsurf     | .windsurfrules             | Manual (run `extract-latest`) |

## Contributing

```bash
git clone https://github.com/ooiyeefei/agentic-coding-workflow-os.git
cd agentic-coding-workflow-os
uv sync
uv run pytest              # unit tests
uv run ruff check .        # lint
uv run pyright spanweave/  # type-check
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for more.

## License

Apache 2.0 — see [LICENSE](./LICENSE)
