# Spanweave Project Rules

## Auto-load context on session start

Before responding to any substantive question about the current project or run,
load prior context from `.spanweave/` — it has two complementary stores:
1. **Decisions** from earlier sessions (in any tool): read `.spanweave/memory/decisions/`,
   plus `.spanweave/memory/shared/decisions/` if it exists (decisions promoted for sharing).
   These are captured by `spanweave extract-latest` and survive across tools and sessions.
2. **Active workflow run**: if `.spanweave/runs/` contains run directories, identify the
   most recently modified one and read its latest stage `packet.md` for what was decided.

This ensures cross-tool context survival — if another agent (Codex, Cursor) worked on this
repo before you, their decisions are captured in `.spanweave/` and you should build on them
instead of re-deriving them.

## Convention files

- This file (`CLAUDE.md`) is auto-read by Claude Code.
- `.claude/rules/*.md` files are also auto-loaded if present.
- `.spanweave/` contains the durable memory substrate (decisions, runs, evidence).
