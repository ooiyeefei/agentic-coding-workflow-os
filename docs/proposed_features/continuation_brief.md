# Continuation Brief — Spanweave (Phase 0 → Phase 1)

> **Audience**: agents (and humans) picking up Spanweave development from this point.
> **Repo**: `/home/fei/fei/code/hackathon/agentic-coding-workflow-os`
> **Default branch**: `main` at commit `f0c1067` (or later — always `git fetch && git pull` first)
> **Open PRs / issues at handoff**: 0 open PRs / 3 open issues (#67, #72, #73 — all non-blocking follow-ups)
> **This file replaces a predecessor brief at the same path** — `git log docs/proposed_features/continuation_brief.md` shows the history.

This brief is the entry point for a fresh session. Read it end-to-end before doing anything else.

---

## Where we are

**Phase 0 is complete.** Plus a wave of post-Phase-0 polish, dogfood validation, and the Spanweave rename. The product thesis is now empirically validated: cross-tool context survival works in the wild (real Codex + Claude Code swap, both passed the killer-demo criterion).

### What you're working on

**Spanweave** is a tool-agnostic shared knowledge substrate for AI-assisted engineering. The substrate is `.spanweave/` directory in your git repo (markdown + YAML frontmatter, typed records, audit JSONL). Per-tool adapters generate ephemeral packets from that substrate, framed for each tool's conventions (CLAUDE.md, AGENTS.md, .cursorrules, etc.).

**Read these in order before acting:**
- `roadmap.md` — full vision, design principles (especially #1 "files first, indexes second" and #4 "format over platform"), Phase 0–8 overview
- `README.md` — short product overview
- `docs/historical/phase0_plan.md` — historical record of how Phase 0 shipped
- `docs/dogfood/2026-04-28-*.md` — the three dogfood findings docs (scenarios 4, 5, and the cross-tool swap)
- `docs/proposed_features/2026-05-07-spanweave-security-architecture-brief.md` — security harness design (committed but not yet implemented)
- `docs/proposed_features/2026-05-07-security-best-practice-brief.md` — companion to the architecture brief
- `spanweave/learning/feedback_loop.py` and `spanweave/session/resume.py` — the most recently-improved modules; demonstrate the "vendor-free, dict-based, pluggable" pattern

---

## Critical conventions (non-negotiable)

1. **Files first, indexes second.** Markdown + YAML frontmatter is the source of truth. No DB in core. Any backend is a rebuildable cache, never a source of truth.
2. **Tool-agnostic.** Zero vendor names (Cognee, Mem0, Memorix, Zep, Hyperspell, etc.) in production code, defaults, or tests. `roadmap.md` may mention them in competitive-analysis sections only.
3. **Files-first invariant.** Every persistence path writes the markdown file first; any backend push happens after, fail-silent.
4. **Steering without locking.** Opinionated defaults, users override via `.spanweave/policy.yaml` with explicit `reason:`.
5. **Evidence over vibes.** Reviewer agents must paste real command output. Approval without execution evidence is incomplete.
6. **Git identity.** This repo is on `github.com/ooiyeefei`. In any new worktree, run `git config user.email yeefeiooi@gmail.com && git config user.name ooiyeefei` before committing.
7. **Parallel agents as default.** When independent subtasks exist, dispatch parallel agents; never serialize work that can run concurrently.
8. **Use project-local `tmp/`, not `/tmp/`.** Ephemeral artifacts go under `<project-root>/tmp/` (already gitignored). Reserve `/tmp/` for things that genuinely shouldn't survive a reboot.
9. **Naming is final.** Package = `spanweave`, CLI = `spanweave`, config dir = `.spanweave/`, env vars = `SPANWEAVE_*`. No backward-compat shim with `atelier`. The clean-cut rename was intentional and is settled.
10. **Verify at the level the bug manifests.** Don't trust workflow-level CI conclusions when investigating PR-branch failures — drill into job-level results. The previous continuation brief author was misled by green-on-main / red-on-PR; don't repeat that.

---

## What's already done since the predecessor brief (4c7e7c4 → f0c1067)

| Concern | PR / commit | Result |
|---|---|---|
| Dogfood scenarios 4, 5, partial 1+2 | commit `456f542` | 3 findings docs in `docs/dogfood/`; 3 issues filed (#65, #66, #67) |
| Spanweave narrative rename (scope 3a) | PR #68 | docs aligned; CLI/package still `atelier` at the time |
| Skill feedback loop: cumulative rule application | PR #69 | Fixed #65 (HIGH + LOW); per-rule dedupe replaces marker-presence check |
| Resume packet content density | PR #70 | Fixed #66 HIGH bug; new `## Recent Stage Context` section embeds per-stage briefings; killer-demo answer now reachable directly |
| Integration-tests CI failure on PR branches | PR #71 | Fixed the predecessor brief's actual Task 1 — `ensure_main_ref` helper in conftest creates `main` ref on CI checkouts of non-main branches |
| Spanweave full rename (scope 3c, clean cut) | PR #74 | Code paths aligned: `atelier/` → `spanweave/`, `.atelier/` → `.spanweave/`, `ATELIER_*` → `SPANWEAVE_*`. No backward-compat shim. |
| Security best-practice harness | commit `878e94e` | New skill + 6 feedback rules + 2 design briefs. Not yet integrated into a workflow stage. |
| Real cross-tool swap (manual, human-driven) | commit `f0c1067` | Both Claude Code and Codex passed the brief's killer-demo criterion with concrete content from the regenerated resume packet. **Thesis empirically validated.** |

### Decisions ratified during this period

- **Substrate vs packet.** `.spanweave/` is the source of truth (markdown). The packet is a generated view, regenerated on demand. Adapters add tool-specific framing (CLAUDE.md vs AGENTS.md operating instructions) without changing body content.
- **MCP server is queued for Phase 1, not built now.** The packet pattern is the universal API; MCP is an additional channel for MCP-aware tools. Most agent tools today still treat paste as primary.
- **Autosave UX path: tool-rules auto-load.** Add an instruction to `CLAUDE.md` and `AGENTS.md` that says "on session start, read the latest `.spanweave/runs/<latest>/packet.md` if it exists." Both Claude Code and Codex auto-read these files. Smallest viable cross-tool handoff. Daemon/watcher patterns are deferred to Phase 4.
- **Rename: clean cut.** No backward-compat read of `.atelier/`, no migration command. Existing repos start fresh on `.spanweave/`.

### Open issues at handoff

| # | Title | Severity | Status |
|---|---|---|---|
| #67 | Role protocol is duplicated in coder/reviewer prompt output | LOW | open — easy fix, filter role-protocol decisions out of "Prior Decisions" rendering |
| #72 | Auto-stub Decisions dilute typed-record discipline (resume packet) | MEDIUM | open — needs a workflow-runner refactor to either reclassify auto-stubs as a new `WorkflowEvent` type or have personas emit one real Decision per substantive stage |
| #73 | ADRs on disk are not linked into resume packet | LOW-MED | open — needs back-fill at ADR-generation time, or glob `docs/adr/` and surface ADRs by tag/issue match |

---

## Tasks for the next wave (priority order)

The work splits into three streams. Do Wave 1 first — small and unblocks Wave 2. Wave 3 is Phase 1 proper.

### Wave 1 — Quick wins (parallelizable, ~2-4h total)

1. **Tool-rules auto-load** — add to `CLAUDE.md` (create if missing) and `AGENTS.md` an instruction like *"Before responding to any substantive question about the current run, read `.spanweave/runs/<latest>/packet.md` if it exists. The 'latest' run is the most recently modified directory under `.spanweave/runs/`."* This wires the **coder+reviewer same-folder** and **credit-exhaust → swap-tool** UX flows directly using existing tool conventions, no new code. ~30 min.

2. **MCP server entry in `roadmap.md` Phase 1.** Spec-only, not implementation. Document: read-only MCP resources first (`packet`, `runs`, `decisions`), then write surface (`record_decision`, `attach_evidence`). Note that MCP is auxiliary — most agent tools still treat paste as primary, so the packet pattern remains the load-bearing surface. ~30 min.

3. **Fix #72 (MEDIUM).** Auto-stub Decisions like "Persist workflow evidence for 001-specify" pollute the typed-record discipline. Two viable shapes (described in the issue): introduce a `WorkflowEvent` type that the workflow runner emits instead of `Decision`, OR prompt personas to emit one real Decision per substantive stage. Pick one (probably option 1 — mechanical, no persona-protocol changes). ~1-2h with a dispatched agent.

**Dispatch pattern**: 1 and 2 can be done by you in main; 3 should be a parallel agent in an isolated worktree.

### Wave 2 — Phase 1 starters (~4-6h each, pick one to ship)

| Candidate | What | Why now |
|---|---|---|
| `announce_and_proceed` gate type | Third gate alongside `auto`/`review`/`approval`. Workflow YAML gains `interrupt_window_seconds` + `on_interrupt: halt\|redirect\|rollback`. Orchestrator emits `plan_announced` audit event, waits the window, then dispatches. Humans interrupt via `POST /runs/<id>/interrupt`. | Speed-vs-safety trade-off many users want; well-spec'd in `roadmap.md` Phase 1 |
| Prompt pattern library | `.spanweave/defaults/prompt_patterns/` with markdown files (frontmatter declares scope). Initial seeded patterns: `parallel_dispatch_warning.md`, `insight_separation.md`, `trust_but_verify_announcement.md`. Personas opt in via `patterns:` array in their frontmatter; loader concatenates pattern bodies. | Scales prompt discipline as composable, version-controlled markdown — extends the files-first thesis from typed records to prompt craft |

### Wave 3 — Phase 1 bigger (~1-2 days each)

| Candidate | Notes |
|---|---|
| Cursor adapter | Reads `.cursorrules`, parses Composer history. Templates already exist for Claude Code / Codex adapters in `spanweave/adapters/` — follow the same shape |
| Generic clipboard adapter | For ChatGPT, Gemini, Cowork — agents that have no local CLI integration. `spanweave context --for chatgpt` already produces paste-ready output; this would make the round-trip work |
| Adapter auto-detection | Scan for `.claude/`, `AGENTS.md`, `.cursorrules`, env vars; pick the right adapter without `--agent` flag |
| Full MAD + LLM Council | Du 2023 protocol + Karpathy anonymized peer ranking. Convergence detection, round caps, chairman synthesis. Escalation triggered by Coder↔Reviewer deadlock, complex clarifications, ADR authorship |
| Simulation / dry-run mode | Workflow YAML gains `simulation:` block with fixture JSONL + assertion expressions. Replays fixtures instead of invoking real agent tools. Captures via `spanweave run record <id>` |

### Security track (parallel to all of the above)

- Read `docs/proposed_features/2026-05-07-spanweave-security-architecture-brief.md` for design
- The skill (`spanweave/defaults/skills/security-best-practice.md`) and 6 feedback rules already shipped on `f0c1067` — but they're not yet wired into any workflow stage
- Next step: add a workflow stage definition that invokes the `security-best-practice` skill before `speckit.implement` for high-risk features

### Lower-priority polish (any time, dispatchable)

- **#67** (LOW) — filter role-protocol decisions out of "Prior Decisions" rendering when rendered for the same persona. ~30 min.
- **#73** (LOW-MED) — back-fill `related_adrs` at ADR generation time, or glob-and-tag-match. ~1-2h.

---

## Things you should NOT do

- **Don't bring back `atelier/` paths.** The clean-cut rename is settled. No alias, no symlink, no shim.
- **Don't add vendor names.** Cognee, Mem0, Memorix, Zep, Hyperspell — none in production code, defaults, or tests. The `MemoryBackend` Protocol exists for future opt-in backends but no commitment to any vendor.
- **Don't merge to main with red CI.** PR #71 fixed the integration-tests-on-PR-branches pattern; CI should now be reliable. Use `gh pr merge --admin` only for genuinely pre-existing CI failures you're explicitly fixing, and document why.
- **Don't introduce a database.** Files-first invariant is non-negotiable. SQLite FTS5 may be added later as a rebuildable index, never as source of truth.
- **Don't drop typed-record discipline.** Every new piece of memory should be a typed Pydantic model with frontmatter validation, never a free-form dict.
- **Don't write to `/tmp/` for project artifacts.** Use `<project-root>/tmp/` (gitignored). Saved feedback memory at `~/.claude/projects/-home-fei-fei-code-hackathon-agentic-coding-workflow-os/memory/feedback_use_project_local_tmp.md` documents this.
- **Don't dismiss the predecessor brief's CI Task 1 a second time.** It was real, hidden behind workflow-level success on main. PR #71 fixed it. If a similar pattern shows up, drill to job-level conclusions.
- **Don't implement Wave 1 tasks without confirming current state.** Tasks 1 (tool-rules auto-load) and 2 (MCP roadmap entry) have explicit user buy-in from the prior session, but check that they haven't been silently completed by another session before starting.

---

## Things you should know

- **Auto-memory directory** at `/home/fei/.claude/projects/-home-fei-fei-code-hackathon-agentic-coding-workflow-os/memory/` (outside the repo). Currently contains `feedback_use_project_local_tmp.md` (the project-local-tmp rule).
- **Parent-dir memory** at `/home/fei/.claude/projects/-home-fei-fei-code-hackathon/memory/` has cross-project context (git identity convention, parallel-agent preference, competitive landscape notes).
- **Agent worktrees** that survive a fresh-clone are at `.claude/worktrees/agent-*` — currently none exist (cleaned up at handoff). The `.claude/worktrees/` dir itself may persist as gitignored.
- **The cognee-hackathon branch was deleted** months ago — its productized portions live on main as PRs #62/#63/#64. Don't rebase against or recover from that branch.
- **CI is green on main** as of this brief. The latest PRs (#69, #70, #71, #74) all merged with green job-level CI.
- **The dogfood run** at `.spanweave/runs/run_01KPT1YDEK0F9MYKW4R1VMY7XY/` is preserved as a permanent fixture for swap testing. Don't `spanweave cleanup` it.

---

## Closing checklist (verify before declaring done)

When wrapping up your session, the closing state should be:

- CI green on `main` (`gh pr checks` on the most recent merged PR; verify all 4 jobs pass)
- No open PRs OR all open PRs are explicitly described as in-flight
- No dangling worktrees (`git worktree list` shows only `main`)
- No stale local branches (`git branch` shows only `main` plus any in-flight feature branches)
- Working tree clean (no uncommitted modifications, no untracked files except gitignored)
- Issues filed for any new bugs found (don't rely on memory; file as GitHub issues)
- Dogfood findings (if any new dogfooding done) committed to `docs/dogfood/<YYYY-MM-DD>-<scenario>.md`
- This continuation brief updated if you changed the conventions, decisions, or roadmap shape

---

## How to start the next session

Open a fresh Claude Code (or Codex, or Cursor) session in this repo. Paste the prompt below or invoke any equivalent.

The brief is self-contained on purpose. The next agent won't have your conversation history — context compaction will erase most of what we discussed. This file repeats the critical invariants up front so even a new agent without memory of the prior session has the discipline pre-loaded.
