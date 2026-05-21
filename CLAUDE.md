# Spanweave Project Rules

## Auto-load context on session start

Before responding to any substantive question about the current project or run:
1. Check if `.spanweave/runs/` exists and contains any run directories.
2. If yes, identify the most recently modified run directory.
3. Read that run's most recent stage `packet.md` for context about what was decided.

This ensures cross-tool context survival — if another agent (Codex, Cursor) worked on this repo before you, their decisions are captured in `.spanweave/` and you should use them.

## Convention files

- This file (`CLAUDE.md`) is auto-read by Claude Code.
- `.claude/rules/*.md` files are also auto-loaded if present.
- `.spanweave/` contains the durable memory substrate (decisions, runs, evidence).
