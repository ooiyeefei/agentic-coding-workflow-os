---
date: 2026-04-28
scenario: 5 — Resume-after-compaction
operator: claude-code (autonomous)
result: state survives, but the resume packet has weak content density
---

# Dogfood — Resume-After-Compaction

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

### BUG #3 — Resume packet does not include rich stage content (HIGH severity)

The brief's killer-demo pass criterion is: *"ask 'what was decided in specify?' — Claude Code can answer correctly without re-explaining."*

With the current resume packet, Claude Code **cannot** answer this. The resume packet is 75 lines. The original specify-stage packet (`stages/001-specify/packet.md`) is **199 lines** and contains:

- Full issue text (rate-limit thresholds, retry-after math, security considerations)
- Acceptance criteria (5 numbered gates)
- Sample curl requests
- Demo credentials
- UAT plan
- 7 source-types in the provenance table

None of that is in the resume packet. The resume packet only surfaces:
- 8 vapid stub "decisions" (see Bug #4 below)
- 1 single-line rejected alternative
- 0 ADRs (see Bug #5 below)
- A 2-row provenance table

**Test the brief's pass criterion**: pretend I am a fresh Claude Code session. Question: "What was the rate-limit threshold decided in specify?" — answer must be "5 attempts per 60-second rolling window per IP." From the resume packet alone, I can't answer; I'd have to read the stage packets directly. The resume packet is a *table of contents*, not a *briefing*.

**Suggested fix shape:** Resume packet should embed (or link to) the most recent N stage `packet.md` summaries. Most useful is probably specify + clarify + plan summaries plus all open findings.

### BUG #4 — "Decisions" captured during workflow are auto-stubs, not real decisions (MEDIUM severity)

All 8 captured `Decision` records on this run say:

```
Persist workflow evidence for 001-specify
Persist workflow evidence for 002-clarify
...
```

These are auto-emitted by the workflow runner as side effects of stage completion, not real engineering decisions. Compare with the *intended* type of `Decision` (per `atelier/memory/records.py`): a typed record with `body`, `tags`, `confidence`, `source`, `related_issues`, `related_adrs` — all the affordances of a real ADR-grade insight.

When a fresh agent reads the resume packet's "Prior Decisions" section, it learns nothing about WHY anything was done. This dilutes the value of the typed-record discipline.

**Suggested fix shape:** Either (a) auto-stubs should not be classified as `Decision` (use a separate `WorkflowEvent` type), or (b) personas should be prompted to emit one real `Decision` per substantive stage (specify, clarify, plan).

### BUG #5 — Existing ADRs are not linked in resume packet (LOW-MEDIUM severity)

`docs/adr/0001-workflow-validation.md` and `docs/adr/0002-workflow-validation.md` exist on disk. The resume packet says:

```
## Relevant ADRs
- No ADRs referenced by transferred memory.
```

The link is broken because no memory record has `related_adrs` populated. Specifically, the rejected alternative at `.atelier/memory/rejected_alternatives/rejected_alternative_01KPT1YDQ62BGERZ4XVS30YZCB.md` has `related_adrs: []` despite the rejected alternative *being the input that produced* the workflow-validation ADRs.

**Suggested fix shape:** ADR generation should back-fill `related_adrs` on the source records. Or the resume packet should glob `docs/adr/` and surface ADRs that touch any tag/issue mentioned in the run.

## What surprised me

- **The body of the run lives in the per-stage packets, not in any aggregated rollup.** This is the files-first invariant winning: I can always cd into a stage dir and read the rich packet. But the cross-tool resume flow doesn't surface that richness.
- **Tool detection works without flags.** When invoking with no `--agent`, the adapter detection picks one based on the cwd (the brief shows this for `detect_active_adapter`). This is a nice "convention over configuration" win.
- **Provenance markers are inline-readable.** A line like `_Source: issue_text | w23-demo-login-rate-limit | demo/issue.md_` tells me the source_type, source_id, and path in one glance. Good for audit trails.

## Bugs filed

- **#66** — all three bugs above filed together: HIGH (resume packet content density), MEDIUM (auto-stub Decisions dilute typed-record), LOW-MEDIUM (ADRs not linked)

## Did not try

- Resuming an *in-flight* run (this one was completed). The "stop mid-stage, come back hours later, resume from current stage" flow is the more common case in real use.
- Pasting the packet into a real Claude Code session and asking the test question. (Would require human in the loop.)
- The `--approve` path on `run resume`.

## Verdict

State survives across sessions — the plumbing thesis holds. But the *value* delivered by the resume packet is less than what's in the per-stage packets. The aggregator step is undercooked. Fixing Bug #3 alone would lift the killer-demo pass rate from "fails" to "succeeds".
