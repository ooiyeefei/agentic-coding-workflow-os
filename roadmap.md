# Spanweave Roadmap

## Vision

Spanweave is a tool-agnostic, git-native shared memory layer for AI coding
agents. It captures engineering decisions ambiently from any coding session via
a local LLM, stores them as markdown under `.spanweave/memory/`, and makes them
readable across tools (Claude Code, Codex, Cursor, Windsurf) by wiring each
tool's convention file (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`,
`.windsurfrules`) with a read-pointer back to that memory. There is no SaaS and
no new platform to adopt — just files in your repo, synced by git, readable by
every agent and every human.

## What works today

- **CLI (8 commands)**: `init`, `extract`, `extract-latest`, `review`,
  `reflect`, `promote`, `grep`, `skill_feedback`.
- **Auto-capture on session end** via a Stop hook (`extract-latest --detach`)
  that runs after each Claude Code session.
- **Cross-tool read-pointers** scaffolded by `spanweave init --tool …` into
  `CLAUDE.md` / `AGENTS.md` / `.cursorrules` / `.windsurfrules`, so a fresh
  session in any supported tool auto-loads prior decisions.
- **Private / shared decision promotion** — `private/` decisions stay
  local-only; `promote` moves them to `shared/` where teammates pick them up on
  git pull. Sharing policy lives in `.spanweave/sharing.yaml`.
- **Local LLM by default** via Ollama (`gemma3:4b` / `qwen2.5:1.5b`) —
  extraction and reflection happen on-device, so transcripts never leave the
  machine.

## Near-term direction (proposed, not yet built)

Tracked in **[GitHub issue #92 — Native-memory harvest + dual-track eval](https://github.com/ooiyeefei/agentic-coding-workflow-os/issues/92)**.

Today's capture is a single Stop-hook pass over the whole transcript — lossy if
the session dies before the hook fires, and we have no quality metric for what
it extracts. The proposed direction narrows Spanweave's job:

1. **Harvest** each agent's *native* memory (Claude Code Auto Memory; Codex
   Memories) into the shared `.spanweave/` layer — Codex sees what Claude
   remembered, and vice versa.
2. **Keep** the existing gemma/qwen extraction as an independent second source.
3. **Compact** native memory + extracted decisions into the consolidated shared
   layer.
4. **Eval = recall-compare** — native memory is a sparse, high-precision "these
   mattered" reference; measure Spanweave's recall against it. No golden test
   set required.

Scope is Claude-first, Codex-next (once its memory-store path is located). See
the issue for honest catches and open questions.

## Longer-term ideas

- **MCP-server `write_decision` tool** — only if convention-instruction
  compliance proves insufficient for getting agents to record their own
  decisions cleanly.
- **Broader tool coverage** — Cursor and Windsurf harvesting, if and when they
  ship native auto-memory.
- **Semantic dedup** — collapse near-duplicate decisions in the shared store.

## Non-goals

- A new platform, SaaS, or vendor lock-in.
- Replacing any agent tool — Spanweave is the memory layer between them.
- Cloud-first or real-time state sharing — git is the sync mechanism.

## License

Apache 2.0 — see [LICENSE](./LICENSE).
