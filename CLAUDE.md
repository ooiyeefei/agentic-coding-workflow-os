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

## Load Spanweave context on session start

Before substantive work on this project, load prior context from
`.spanweave/memory/`. Each record type has its own subdir; load all of them, and
also the matching `shared/` copy (records a teammate promoted for team
visibility):

- `.spanweave/memory/decisions/` and `.spanweave/memory/shared/decisions/` — choices made and the reasoning behind them.
- `.spanweave/memory/findings/` and `.spanweave/memory/shared/findings/` — non-obvious facts discovered about the code or system.
- `.spanweave/memory/reflections/` and `.spanweave/memory/shared/reflections/` — post-hoc lessons about what worked or didn't.
- `.spanweave/memory/rejected_alternatives/` and `.spanweave/memory/shared/rejected_alternatives/` — options considered and ruled out, with the reason (so you don't re-propose them).

This is cross-tool memory: another agent (Claude Code, Codex, Cursor) may have
worked here before you. Build on what's already recorded instead of re-deriving
it.
