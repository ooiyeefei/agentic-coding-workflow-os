# Continuation Brief — Spanweave (post-hackathon mainline work)

> **Audience**: agents (and humans) picking up Spanweave development from this point onward.
> **Repo**: `/home/fei/fei/code/hackathon/agentic-coding-workflow-os`
> **Default branch**: `main` at commit `229a5b4` (or later — always `git fetch && git pull` first)
> **Open PRs / issues at handoff**: 0 / 0 (clean slate)

This file is a self-contained briefing for the next phase of work. It exists because Spanweave's whole thesis is "context survives across sessions and tools" — so a continuation brief on disk, in markdown, is the right way to dogfood the substrate.

---

## What you are working on

**Spanweave** (working name; code paths still use `atelier/` internally) is a tool-agnostic shared knowledge substrate for AI-assisted engineering. Phase 0 is complete — 26 worktrees merged, plus 6 follow-up PRs absorbing a hackathon experiment without vendor coupling. The product is a CLI + filesystem layer (markdown + YAML frontmatter in git) that any agent tool can read and write.

**Read first** before doing anything else:
- `roadmap.md` — full vision, design principles (especially #1 "files first, indexes second" and #4 "format over platform"), architecture diagram, all phases
- `README.md` — short product overview
- `phase0_plan.md` — record of how we got here
- `docs/proposed_features/` — this directory; future-feature staging area
- `.atelier/defaults/` — opinionated defaults (personas, skills, rules, workflows, feedback rules)
- `atelier/memory/records.py` — typed records (Decision, ReviewFinding, RejectedAlternative, **SkillOutcome**)
- `atelier/learning/feedback_loop.py` — the most recently-added module; demonstrates the "vendor-free, dict-based, pluggable" pattern

**Critical conventions you must follow**:
1. **Files first, indexes second.** Markdown + YAML frontmatter is source of truth. No DB in core. Any backend is a rebuildable cache.
2. **Tool-agnostic**. Zero vendor names (Cognee, Mem0, Memorix, Zep, Hyperspell) in production code, defaults, or tests. Roadmap.md may mention them in competitive-analysis sections only.
3. **Files-first invariant**: every persistence path writes the markdown file first; any backend push happens after, fail-silent.
4. **Steering without locking**: opinionated defaults, users override via `.atelier/policy.yaml` with explicit `reason:`.
5. **Evidence over vibes**: Reviewer agents must paste real command output. Approval without execution evidence is incomplete.
6. **Git identity**: this repo is on `github.com/ooiyeefei`. Always set `git config user.email yeefeiooi@gmail.com && git config user.name ooiyeefei` in any new worktree before committing.
7. **Parallel agents as default**: when independent subtasks exist, dispatch parallel agents; never serialize work that can run concurrently.

---

## Three tasks for this continuation

Order is **CI hygiene → Dogfood → Spanweave rename**, with CI hygiene and dogfood feasible in parallel.

### Task 1 — CI hygiene (small, unblocks everything)

**Why it matters**: GitHub Actions CI has been failing on `main` for two pre-existing issues since the W29 merge. We've been admin-merging PRs to bypass. Future contributors won't have admin access, and the broken CI hides real regressions.

**The two failures** (verify before fixing):

```bash
gh run list --branch main --limit 3 --json status,conclusion,workflowName
gh run view <latest-failing-run-id> --log-failed | head -100
```

You should see:
1. **`typecheck` job** — pyright errors in `atelier/personas/callers.py` flagging `_resolve_run_id` and `_build_agent_response` as private members accessed outside their class. These were inherited from the W29 merge and never fixed.
2. **`integration-tests` job** — `scripts/run-e2e.sh` fails with `fatal: invalid reference: main` when running in a fresh CI checkout. The test setup does `git init -b main` but something downstream tries to reference `main` before any commit exists on it.

**Acceptance**:
- Both jobs green on a fresh PR
- Zero regressions in the unit suite (`uv run pytest -q` should still pass with ~395 tests)
- Fix is minimal — favor making the access public (rename `_resolve_run_id` → `resolve_run_id`) over adding pragmas, unless rename has too much surface area
- The integration fix should make the test repo setup robust without needing CI workarounds — likely needs a dummy initial commit or `git symbolic-ref HEAD refs/heads/main` before `git init`

**Suggested branch**: `acw-ci-hygiene`

**Suggested PR title**: `Fix pre-existing CI failures: typecheck on callers.py + integration e2e setup`

### Task 2 — Dogfood Phase 0 on a real feature

**Why it matters**: Phase 0 is "complete" by tests passing, but we haven't validated the product end-to-end on a real engineering task. The thesis — context survives across agent tools — is unproven until you see it work in the wild on something that matters.

**What "real" means**: a feature you genuinely need shipped, not a synthetic demo. Best candidates:
- A TIROS HAZOP feature (the safety-critical AI project the user has been building — see CLAUDE.md memory under `/home/fei/.claude/projects/-home-fei-fei-code-tiros-hazop-yf-hazop/memory/` if you have access)
- A Spanweave self-improvement (e.g., implement the deferred "Spanweave rename" using Spanweave itself — meta-dogfood)
- An issue you have on any project where you'd actually use a coding agent

**The five highest-signal scenarios** (do at least 2):

1. **Session swap demo** (the killer feature):
   - Start a real run in Codex: `atelier run --issue <real-issue-N> --workflow speckit-loop --repo .`
   - Work through specify → clarify → plan in Codex (paste outputs back via `atelier run resume <run-id> --agent-output-file specify_response.md`)
   - Switch to Claude Code: `atelier resume --agent claude-code --run <run-id>`
   - Paste the generated Context Packet into Claude Code; ask "what was decided in specify?"
   - **Pass**: Claude Code can answer correctly without re-explaining
   - **Fail**: it can't, OR the context packet is missing critical decisions

2. **Multi-agent role split** (Codex Coder + Claude Code Reviewer in parallel):
   ```bash
   atelier prompt --role coder --agent codex --run <id>      # paste into Codex
   atelier prompt --role reviewer --agent claude-code --run <id>  # paste into Claude Code
   ```
   Each gets the right role-specific context. Codex implements; Claude Code reviews using execution-mandatory protocol.

3. **Auto-ADR validation**:
   - After completing a run with 3+ Decisions and 2+ RejectedAlternatives
   - Check `docs/adr/` for the auto-generated ADR
   - Compare against the quality of a hand-written ADR you'd actually keep
   - Flag any specific gaps (formatting, missing context, wrong field names)

4. **Skill self-improvement loop** (the just-shipped feature):
   - Run a skill manually, capture an outcome as a `SkillOutcome` JSON in `.atelier/memory/skill_outcomes/`
   - With deliberately weak feedback (success_score < 0.5, error_type set)
   - Run `atelier skill_feedback derive --entry <path-to-outcome.json>`
   - Verify it produces a meaningful rule from the YAML rule library
   - Optionally apply with `--skill-file <path-to-SKILL.md> --apply`

5. **Resume-after-compaction**:
   - Start a run, work through 4 stages, close all terminals
   - Hours later: `atelier run list` to find the run, `atelier run show <id>`, `atelier run resume <id> --agent claude-code`
   - **Pass**: pick up exactly where you stopped with full context
   - **Fail**: state corruption, missing data, can't resume

**Output**: write findings as a markdown file `docs/dogfood/<YYYY-MM-DD>-<scenario>.md` per scenario. Include:
- What worked
- What broke (be specific — file paths, error messages)
- What surprised you
- Bugs to file as GitHub issues

**Don't fix things while dogfooding**. Capture findings; file issues; fix later. Mixing find-and-fix bias the fixes toward what's annoying-right-now rather than what's most important.

**Suggested branch**: none — dogfood writes happen on `main` directly (they're documentation), or on a `dogfood-<scenario>` branch if you prefer PR review.

### Task 3 — Spanweave rename (do AFTER dogfood)

**Why it matters**: the public-facing name has been "Spanweave" since 2026-04-25, but `roadmap.md` still has `> **Working name**: _Atelier_ (placeholder — final naming TBD)`, README mixes both, and code paths still use `atelier/`. Inconsistency is a credibility cost.

**Why AFTER dogfood**: dogfooding may surface usability issues that change what should be renamed and how. Don't prematurely standardize a name across surfaces you're about to redesign.

**Scope decision** (pick ONE of three increasing-radius options):

#### Option 3a — Narrative rename only (~30 min, recommended start)
- Update `roadmap.md` header: drop "(placeholder — final naming TBD)", change to `> **Name**: Spanweave`
- Update `README.md` to lead with "Spanweave"
- Update `docs/` references to use Spanweave consistently
- Leave Python package, CLI command, env vars, config dir as `atelier`
- Add a one-line note: "The Python package and CLI command are named `atelier` for historical reasons; a separate Phase 1 task will align them."

#### Option 3b — User-facing rename (medium ~2-3h)
- Everything in 3a, plus:
- Rename CLI binding so `spanweave run --issue 42` works as alias to `atelier run --issue 42` (keep both during transition)
- Rename env vars `ATELIER_*` → `SPANWEAVE_*` with backward-compat fallback (read both, prefer new, deprecation warning if old used)
- Update CLAUDE.md / docs / examples to use `spanweave` as primary
- Don't touch Python package internals (still `import atelier...`)

#### Option 3c — Full rename (~1-2 days, breaking change)
- Everything in 3b, plus:
- Rename Python package `atelier/` → `spanweave/`
- Rename `.atelier/` config dir → `.spanweave/` (with one-time migration command and backward-compat read)
- Update all 395+ tests
- Update pyproject.toml entry points
- This is a major refactor — lock down acceptance: full test suite green, all CI jobs green, dogfood scenarios still work

**Recommendation**: do **3a first** (low cost, high signal — updates the most-visible surface). After 3a is in, decide whether 3b is worth based on whether the inconsistency between docs ("Spanweave") and CLI (`atelier`) is annoying enough to justify the risk. **Do not start with 3c** — it's a separate, much bigger project.

**Acceptance for 3a**:
- `grep -ric "atelier" roadmap.md README.md docs/` shows clear distinction: "atelier" remains where it refers to filesystem paths or CLI commands; "Spanweave" is used as the product name
- No conflicting messaging (e.g., README lead-line says "Spanweave is..." but roadmap.md header says "Working name: Atelier")
- The single-line note about the package/CLI rename being deferred is present

**Suggested branch**: `acw-spanweave-narrative-rename` (for 3a)

---

## Order of work + parallelism

**If solo**: Task 1 (CI hygiene) → Task 2 (Dogfood) → Task 3 (Rename, scope 3a). Total: ~4-6 hours of real work.

**If you can dispatch parallel agents** (recommended, matches user's standing rule):
- **Wave 1 (parallel)**:
  - Agent A: Task 1 (CI hygiene). Self-contained.
  - Agent B (you, in main worktree): Task 2 (Dogfood). Manual + iterative.
- **Wave 2 (after both complete)**:
  - Task 3 narrative rename, informed by dogfood findings.

The reason CI hygiene can't be folded into dogfood: it's a code change requiring tests + PR; dogfood is a documentation activity. Different shapes of work, parallelizable cleanly.

---

## Things you should NOT do

- ❌ **Don't add Cognee, Mem0, Memorix, Zep, or Hyperspell as dependencies** unless explicitly approved. The product is tool-agnostic. The MemoryBackend Protocol exists for future opt-in backends but no commitment to any vendor was made.
- ❌ **Don't merge to main without verifying tests pass** — except for pre-existing CI failures you're explicitly fixing. Use `gh pr merge --admin` only as last resort, and document why.
- ❌ **Don't rename `atelier` to `spanweave` in code paths** as part of Task 3 unless you've explicitly chosen scope 3c and have ~1-2 days. 3a (narrative-only) is the recommended starting point.
- ❌ **Don't drop typed-record discipline** — every new piece of memory should be a typed Pydantic model with frontmatter validation, never a free-form dict.
- ❌ **Don't introduce a database** — files-first invariant is non-negotiable. SQLite FTS5 may be added later as a rebuildable index, but never as source of truth.

---

## Things you should know

- The repository contains a memory directory at `/home/fei/.claude/projects/-home-fei-fei-code-hackathon/memory/` (outside the repo) with persistent context from prior sessions. Useful entries:
  - `feedback_git_commit_email_ooiyeefei.md` — explains the git identity convention
  - `feedback_parallel_agents_mandatory.md` — user's strong preference for parallel dispatch
  - `project_competitive_landscape_memory_tools.md` — historical analysis of memory tools
- `.claude/commands/` and `.atelier/defaults/skills/` both have skills available — use them where applicable
- **Date awareness**: file dates rather than guess. `git log` and `date` are authoritative.
- **The cognee-hackathon branch was deleted** — its productized portions live on main as PRs #62/#63/#64. Don't try to rebase against or recover from that branch.

---

## Closing checklist (when you're done with all three tasks)

- [ ] Task 1: CI green, both `typecheck` and `integration-tests` jobs pass on `main`
- [ ] Task 2: at least 2 dogfood scenarios completed, findings documented in `docs/dogfood/`, any bugs filed as GitHub issues
- [ ] Task 3 (if scope 3a): roadmap.md + README.md + docs/ reference Spanweave consistently
- [ ] All open PRs merged or closed deliberately
- [ ] No dangling worktrees (`git worktree list` shows only `main`)
- [ ] No stale local branches (`git branch` shows only `main` and any in-flight feature branches)

When the checklist is clean, this continuation phase is done.
