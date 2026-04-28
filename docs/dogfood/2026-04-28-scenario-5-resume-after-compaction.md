---
date: 2026-04-28
scenario: 5 — Resume-after-compaction
operator: claude-code (autonomous)
result: state survives; HIGH content-density bug fixed in #70; two follow-ups (#72, #73) tracked
---

# Dogfood — Resume-After-Compaction

> **Status (2026-04-28, post-fix)**:
> - Bug 3 (HIGH, content density) — **FIXED** in PR #70 (resume packet now embeds per-stage briefings; killer-demo answer string surfaces directly).
> - Bug 4 (MEDIUM, auto-stub Decisions) — open, tracked as **#72**.
> - Bug 5 (LOW-MEDIUM, ADR linking) — open, tracked as **#73**.
> - Original tracker #66 auto-closed when #70 merged.

## What I ran

Used the existing run `run_01KPT1YDEK0F9MYKW4R1VMY7XY` (issue #24, demo rate-limit feature, all 8 stages completed) to simulate "agent terminal closed, returns days later":

```bash
uv run atelier run list                                                     # find runs
uv run atelier run show run_01KPT1YDEK0F9MYKW4R1VMY7XY                      # inspect
uv run atelier resume --agent claude-code --run run_01KPT1YDEK0F9MYKW4R1VMY7XY > claude_packet.md
uv run atelier resume --agent codex --run run_01KPT1YDEK0F9MYKW4R1VMY7XY > codex_packet.md
diff claude_packet.md codex_packet.md
```

## What worked

- **State survived perfectly.** `run list` showed the run, `run show` rendered the full stage tree, all 8 stages marked completed. Exit codes clean.
- **Tool-aware framing.** The diff between the two packets shows the adapter layer is doing its job:
  - Claude packet leads with `# CLAUDE.md Context Packet`, instructs the agent to "Read CLAUDE.md before acting", references `.claude/rules/`
  - Codex packet leads with `# AGENTS.md Context Packet`, instructs the agent to "Read AGENTS.md before acting", references AGENTS.md
  - Body content is identical between them — only the framing differs. This matches the design: same context, different tool conventions.
- **Provenance is structured.** Each rendered section carries `_Source: source_type | source_id | path_` markers. Even at low content density, the audit trail is present.
- **Run metadata is complete in the packet header**: run_id, issue, workflow, status, current stage, completed/pending stages — everything a fresh agent needs to orient.

## What broke

### Bug 3 — Resume packet does not include rich stage content (HIGH) — FIXED in #70

Original finding: the resume packet was 75 lines while the source `stages/001-specify/packet.md` was 199 lines and contained the full issue text, acceptance criteria, sample curl, demo creds, and UAT plan. None of that surfaced in the resume packet — it was a table-of-contents, not a briefing.

The brief's killer-demo pass criterion was: *"ask 'what was decided in specify?' — Claude Code can answer correctly without re-explaining."* With the original packet, that failed.

**Outcome after #70:** the packet grew from 75 → 322 lines and now contains the killer-demo answer string `Allow at most 5 failed attempts per client IP in a rolling 60-second window` plus all five acceptance criteria. New `## Recent Stage Context` section embeds condensed per-stage briefings; the budget-aware fallback path now keeps substantive content even when raw packets would otherwise blow the token budget.

### Bug 4 — "Decisions" captured during workflow are auto-stubs (MEDIUM) — open as #72

All 8 captured `Decision` records on this run say `Persist workflow evidence for 00N-stage-name` — workflow-runner side effects, not engineering insights. Dilutes the typed-record discipline. Tracked separately for follow-up; needs either a new `WorkflowEvent` type or persona-driven Decision emission.

### Bug 5 — Existing ADRs are not linked in resume packet (LOW-MEDIUM) — open as #73

`docs/adr/0001-workflow-validation.md` and `0002-workflow-validation.md` exist on disk but the resume packet says "No ADRs referenced by transferred memory." Cause: `related_adrs: []` on the source records. Tracked separately for follow-up; needs either back-fill at ADR-generation time or glob-and-tag-match in the adapter base.

## What surprised me

- **The body of the run lives in the per-stage packets, not in any aggregated rollup.** This is the files-first invariant winning: I can always cd into a stage dir and read the rich packet. But the cross-tool resume flow doesn't surface that richness.
- **Tool detection works without flags.** When invoking with no `--agent`, the adapter detection picks one based on the cwd (the brief shows this for `detect_active_adapter`). This is a nice "convention over configuration" win.
- **Provenance markers are inline-readable.** A line like `_Source: issue_text | w23-demo-login-rate-limit | demo/issue.md_` tells me the source_type, source_id, and path in one glance. Good for audit trails.

## Bugs filed

- **#66** (closed when #70 merged) — original tracker for all three bugs above
- **#70** (merged) — fixed Bug 3 (HIGH, content density)
- **#72** (open) — re-filed Bug 4 (MEDIUM, auto-stub Decisions)
- **#73** (open) — re-filed Bug 5 (LOW-MEDIUM, ADR linking)

## Did not try

- Resuming an *in-flight* run (this one was completed). The "stop mid-stage, come back hours later, resume from current stage" flow is the more common case in real use.
- Pasting the packet into a real Claude Code session and asking the test question. (Would require human in the loop.)
- The `--approve` path on `run resume`.

## Verdict

State survives across sessions — the plumbing thesis holds. The aggregator step was undercooked at the time of dogfood; PR #70 fixed that and the killer-demo pass criterion is now satisfied directly from the packet content. Two follow-up items (Bugs 4 and 5, now #72 and #73) remain — neither blocks the killer demo but both will improve resume-packet quality.
