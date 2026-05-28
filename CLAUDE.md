# Spanweave Project Rules

## Auto-load context on session start

Before responding to any substantive question about the current project, load
prior context from `.spanweave/memory/`:

- `.spanweave/memory/decisions/` — decisions captured from earlier sessions.
- `.spanweave/memory/shared/decisions/` — decisions promoted for team sharing.

These are captured by `spanweave extract-latest` (auto-wired as a Stop hook
when `spanweave init --tool claude-code` ran) and survive across tools and
sessions.

This ensures cross-tool context survival — if another agent (Codex, Cursor)
worked on this repo before you, their decisions are recorded in
`.spanweave/memory/` and you should build on them instead of re-deriving them.

## Convention files

- This file (`CLAUDE.md`) is auto-read by Claude Code.
- `.claude/rules/*.md` files are also auto-loaded if present.
- `.spanweave/memory/` is the durable memory substrate (markdown + YAML
  frontmatter).

## Feature requests → GitHub issues

This is a private GitHub repo. File all feature requests, proposals, and design
directions as **GitHub issues** (`gh issue create`) — not as new markdown files
under `docs/proposed_features/`. Issues are the single tracker for pending work;
the detailed design can live in the issue body. (Existing `docs/proposed_features/`
briefs predate this convention.)
