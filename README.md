# Spanweave

> Shared memory for AI coding teams. Context persists across agent tools. Decisions never die.

[![CI](https://github.com/ooiyeefei/agentic-coding-workflow-os/actions/workflows/ci.yaml/badge.svg)](https://github.com/ooiyeefei/agentic-coding-workflow-os/actions/workflows/ci.yaml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 448+](https://img.shields.io/badge/tests-448%2B_passing-brightgreen.svg)]()

## The Problem

You spend two hours building context in Codex. Switch to Claude Code — start from zero. Decisions you made with one agent vanish when you open another. Every AI coding tool is a silo: context dies with the session, decisions evaporate between tools, and teams using different agents have no shared memory.

## The Solution

Spanweave stores decisions, evidence, and context as **markdown files in your git repo** — the one thing every agent tool already reads. No platform to adopt. No SaaS. No switching cost. A `.spanweave/` directory that any tool can read, git can sync, and humans can grep.

## Quick Demo (30 seconds)

```bash
# Work in Codex, make decisions during a workflow run...
# Later, switch to Claude Code with zero context loss:
spanweave resume --run run_01KPT1YDEK0F9MYKW4R1VMY7XY
# -> Claude Code gets a full context packet: decisions, acceptance criteria, everything.
# -> Answers "what was decided in specify?" correctly without re-explaining.
```

**Team collaboration — no shared platform needed:**

```bash
# Alice commits .spanweave/memory/ -> git push
# Bob clones and picks up where Alice left off:
spanweave resume --run run_01KPT1YDEK0F9MYKW4R1VMY7XY
# -> Bob gets Alice's full context, typed decisions, temporal ordering.
```

## Quick Start

```bash
pip install spanweave                        # or: uv pip install spanweave
ollama pull gemma3:4b                        # local model for auto-extraction (optional)
spanweave init --tool claude-code --repo .   # one-time setup
# Done. Open Claude Code — it auto-loads your last session's context.
```

## Features

- **Cross-tool session swap** — switch between Claude Code, Codex, and Cursor without losing context
- **Typed decisions** — Decision, ReviewFinding, RejectedAlternative records with timestamps, provenance, and tags
- **Context compiler** — priority tiers, token budgets, deduplication, and provenance tracking
- **Auto-extraction** — pulls decisions from session transcripts using a local LLM (no data leaves your machine)
- **Tool-specific framing** — same decisions, formatted for each tool's conventions (CLAUDE.md, AGENTS.md, .cursorrules)
- **Workflow engine** — define multi-stage workflows in YAML with review gates and evidence requirements
- **Team sharing via git** — no Notion, no Confluence, no SaaS middleware; git push/pull is the sync
- **Temporal queries** — decisions are timestamped and stage-linked; grep by time, run, or tag
- **Skill feedback loop** — agents learn from past outcomes and derive concrete rules for future runs
- **Evidence packs** — every review produces structured proof of execution (JSON + Markdown)

## How It Works

```
┌───────────────── YOUR AGENT TOOLS ─────────────────┐
│  Claude Code  |  Codex  |  Cursor  |  Any tool     │
└──────────────────────┬─────────────────────────────┘
                       │ reads/writes
┌──────────────────────▼─────────────────────────────┐
│              TOOL ADAPTER LAYER                      │
│  Each adapter knows how to:                         │
│    1. INGEST session transcripts -> extract decisions│
│    2. FORMAT context packets for the tool's style   │
│    3. DETECT which tool is running                  │
└──────────────────────┬─────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────┐
│            SPANWEAVE CONTROL PLANE                   │
│  Context compiler | Workflow engine | Policy engine  │
│  Typed memory | Evidence packs | Skill feedback     │
└──────────────────────┬─────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────┐
│       .spanweave/ (files in git = the substrate)    │
│  runs/ | memory/decisions/ | memory/findings/       │
│  workflows/ | policy.yaml | audit/                  │
│  All markdown. All git-tracked. All tool-readable.  │
└────────────────────────────────────────────────────┘
```

## Comparison

| Tool | What it does | Spanweave difference |
|------|-------------|---------------------|
| **Conductor** | macOS workspace orchestrator for Claude Code + Codex | No context portability across tools, no persistent memory |
| **Mesh Code** | Real-time state sharing across agents | Team-first, centralized SaaS. Spanweave is files-first, git-native, zero infra |
| **Mem0 / Cognee** | Memory layer for LLM API apps | Built for apps calling APIs. Spanweave is for humans using agent *tools*. Different category |
| **Hindsight** | Session replay for Claude Code | Single-tool, read-only. Spanweave is cross-tool and writes structured decisions |
| **Claude Code / Codex** | Single-vendor CLI agents | Session-locked. Context dies. Spanweave makes their context portable and persistent |

## Supported Tools

| Tool | Status | Integration |
|------|--------|-------------|
| Claude Code | Fully supported | Auto-loads context via CLAUDE.md; extracts from session JSONL |
| Codex | Fully supported | Auto-loads via AGENTS.md; extracts from session logs |
| Cursor | Supported | Reads .cursorrules; generic adapter for ingestion |
| Windsurf | Supported | Generic adapter (same mechanism as Cursor) |
| ChatGPT / Gemini | Paste mode | `spanweave context --for chatgpt` generates paste-ready output |
| Any MCP tool | Planned | MCP server exposing `.spanweave/` as resources |

## CLI Commands

```
spanweave init          # Scaffold .spanweave/ workspace
spanweave run           # Start a workflow run or inspect existing runs
spanweave resume        # Cross-tool session swap (the killer feature)
spanweave prompt        # Generate role-specific prompts for a run
spanweave context       # Generate standalone context for paste into any tool
spanweave extract       # Extract decisions from a transcript
spanweave ingest        # Ingest a transcript into durable memory
spanweave review        # Review pending learnings from auto-extraction
spanweave grep          # Search across .spanweave/ workspace
spanweave skill_feedback # Inspect and apply feedback rules
spanweave cleanup       # Remove finished run worktrees
spanweave daemon        # Background auto-extraction (placeholder)
```

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for setup instructions.

**TL;DR:**
```bash
git clone https://github.com/ooiyeefei/agentic-coding-workflow-os.git
cd agentic-coding-workflow-os
uv sync
uv run pytest              # 448+ tests, should all pass
uv run ruff check .        # linting
```

## License

Apache 2.0 — see [LICENSE](./LICENSE)
