# Spanweave

> Ambient cross-tool memory for AI coding agents. Decisions live as markdown in your git repo — readable by every agent, syncable by git.

[![CI](https://github.com/ooiyeefei/agentic-coding-workflow-os/actions/workflows/ci.yaml/badge.svg)](https://github.com/ooiyeefei/agentic-coding-workflow-os/actions/workflows/ci.yaml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## The Problem

You spend two hours building context in Codex. Switch to Claude Code — start from zero. Decisions you made with one agent vanish when you open another. Every AI coding tool is a silo: context dies with the session, decisions evaporate between tools, and teams using different agents have no shared memory.

## The Solution

Spanweave stores what your coding sessions decide as **plain markdown in your git repo** under `.spanweave/memory/`. Every agent already reads its own convention file (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.windsurfrules`); Spanweave wires those files to auto-load `.spanweave/memory/` on session start — so the next agent (Claude Code, Codex, Cursor, …) picks up where the last one left off.

No platform. No SaaS. No switching cost. Just markdown that any tool can read, git can sync, and humans can grep.

## Install

Spanweave is a Python 3.11+ CLI. Install the `spanweave` command from source:

```bash
# global CLI install (recommended)
uv tool install git+https://github.com/ooiyeefei/agentic-coding-workflow-os.git
# …or with pipx:
pipx install git+https://github.com/ooiyeefei/agentic-coding-workflow-os.git
# …or clone for development:
git clone https://github.com/ooiyeefei/agentic-coding-workflow-os.git
cd agentic-coding-workflow-os && uv sync   # then run: uv run spanweave …
```

**Ollama is optional.** It's only needed for the *local-LLM auto-extraction* path
(`extract` / `extract-latest`), which reads a finished transcript and distils
decisions: `ollama pull gemma4:e4b`. The cross-tool handoff below uses native
memory harvesting and needs **no model at all**.

**Interactive review is optional too.** `spanweave review` accepts records all at
once with `--auto-accept` out of the box. To get the per-record Accept / Edit /
Dismiss UI, install the `interactive` extra (`questionary` + `rich`):

```bash
# if you installed with uv tool:
uv tool install --reinstall "spanweave[interactive] @ git+https://github.com/ooiyeefei/agentic-coding-workflow-os.git"
# if you cloned for development:
uv sync --extra interactive
```

---

## Walkthrough: continue a dead Codex session in Claude Code

> **Scenario:** you were deep in a task with **Codex** and it ran out of credits.
> You want a fresh **Claude Code** session to pick up exactly where Codex left off.

### One-time setup (skip if this repo is already wired)

```bash
cd your-project
spanweave init --tool claude-code --tool codex
```

This scaffolds `.spanweave/`, adds a **read-pointer** to `CLAUDE.md` and
`AGENTS.md` (so each agent loads memory on start), and wires a Claude Code
**SessionEnd hook** (so Claude auto-captures decisions on exit). It's idempotent —
safe to re-run; it won't duplicate anything.

### 1. Harvest what Codex remembered

Codex keeps its own session memory — prose "rollout summaries" under `~/.codex/`.
Pull this repo's into Spanweave:

```bash
spanweave harvest --tool codex
```

- **Scoped to the current repo by default.** Codex stores every project in one
  global store; Spanweave imports only the summaries whose working directory
  matches this repo.
- Add `--since 2026-06-01` to limit to recent sessions, or `--all` to import
  every project's memory.
- **No model required** — harvest just reads files Codex already wrote.

Harvested records land in `.spanweave/memory/pending/`, tagged `source: native-codex`.

### 2. Review and keep

```bash
spanweave review              # interactive: Accept / Edit / Dismiss each record
# …or keep everything in one pass:
spanweave review --auto-accept
```

Accepted records move out of `pending/` into `.spanweave/memory/`. High-confidence
native records land in `shared/<type>/` — which is **git-tracked and auto-loaded**
by the next session. (Interactive Accept/Edit/Dismiss needs the optional
`interactive` extra — `questionary` + `rich`; `--auto-accept` works without it.)

### 3. (Optional) Commit it

```bash
git add .spanweave && git commit -m "carry over Codex session memory"
```

Now the context survives reboots, and teammates inherit it on `git pull`.

### 4. Open Claude Code in the same repo

On startup Claude reads `CLAUDE.md`, which points it at `.spanweave/memory/` — so
it loads what Codex decided. Just continue, e.g.:

> *"Load the Spanweave memory and pick up where the last session left off — what
> were we building, what's done, and what's next?"*

Claude answers from the harvested context and keeps going.

### 5. The loop closes itself

When your Claude session ends, the SessionEnd hook captures Claude's **new**
decisions into `pending/`. Review them, and the *next* agent — Codex, Cursor,
whoever — inherits Claude's work too.

> **It's symmetric.** To go the other way (Claude → Codex), run
> `spanweave harvest --tool claude-code`, review, then open Codex — it reads
> `AGENTS.md` and loads the same memory.

> **Don't see the context in the new session?** Make sure the record is in
> `shared/` (committed + auto-loaded), not `private/` (local-only, gitignored and
> *not* auto-loaded). Run `spanweave promote --all-pending`, or check
> `.spanweave/memory/shared/`.

---

## How It Works

Two ways to **capture**, one way to **recall**.

**Capture — pick either or both:**

- **Harvest native memory** (`spanweave harvest`) — imports what an agent already
  saved itself: Claude Code's typed records (`~/.claude/projects/<repo>/memory/`)
  and Codex's rollout summaries (`~/.codex/`). No model needed. Best for the
  cross-tool handoff above.
- **Auto-extract from transcripts** (`spanweave extract-latest`) — a local LLM
  (Ollama, e.g. `gemma4:e4b`) reads a finished session and extracts decisions,
  findings, and rejected alternatives. Runs automatically for Claude Code via the
  **SessionEnd hook**; run it by hand for other tools.

Both paths stage records to `.spanweave/memory/pending/`.

**Review** (`spanweave review`) — triage pending records (accept / edit / dismiss).
Accepted records route to `shared/<type>/` or `private/<type>/` per
`.spanweave/sharing.yaml`.

**Recall** — every tool's convention file (`CLAUDE.md`, `AGENTS.md`,
`.cursorrules`, `.windsurfrules`) carries a read-pointer to `.spanweave/memory/`,
so a fresh session in any tool loads prior context automatically.

## Where memory lives

```
.spanweave/
├── sharing.yaml            # policy: where confirmed records go, what auto-promotes
└── memory/
    ├── pending/            # just-captured, awaiting review
    ├── shared/<type>/      # confirmed + team-visible — committed to git, auto-loaded
    └── private/<type>/     # confirmed but local-only — gitignored, your machine only
```

`<type>` is `decisions`, `findings`, `reflections`, or `rejected_alternatives`.
The sharing policy decides where confirmed records land; high-confidence and
tagged records auto-promote to `shared/`. Move a private record to shared anytime
with `spanweave promote <id>` (or `spanweave promote --all-pending`).

> Agents auto-load `shared/`. `private/` stays on your machine and is **not**
> auto-shared or git-committed — keep anything you want a handoff (or a teammate)
> to see in `shared/`.

## CLI Commands

```
spanweave init             # Scaffold .spanweave/, wire tool read/capture pointers (--tool)
spanweave harvest          # Import an agent's NATIVE memory (--tool claude-code|codex)
spanweave extract-latest   # Auto-extract decisions from the most recent session (local LLM)
spanweave extract          # Auto-extract from a specific transcript
spanweave review           # Confirm pending records (Accept/Edit/Dismiss; --auto-accept)
spanweave promote          # Move a private record to shared (team-visible via git)
spanweave reflect          # Synthesize higher-order lessons from accumulated decisions
spanweave grep             # Regex search across .spanweave/
spanweave eval             # Compare auto-extraction vs an agent's native memory (recall)
spanweave skill_feedback   # Inspect / apply feedback rules derived from outcomes
```

Add `--repo <path>` to target a repo other than the current directory, and
`-h/--help` to any command for full options.

## Supported Tools

| Tool         | Loads context on start (read) | Capture this session's decisions (write)            |
|--------------|-------------------------------|-----------------------------------------------------|
| Claude Code  | `CLAUDE.md`                   | Automatic (SessionEnd hook) · or `harvest` native memory |
| Codex        | `AGENTS.md`                   | `harvest` native memory · or `extract-latest`       |
| Cursor       | `.cursorrules`                | `extract-latest`                                    |
| Windsurf     | `.windsurfrules`              | `extract-latest`                                    |

`harvest` supports the two agents with their own durable memory (Claude Code,
Codex). Any tool can be fed via `extract-latest`, and any tool reads memory back
through its convention file.

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
