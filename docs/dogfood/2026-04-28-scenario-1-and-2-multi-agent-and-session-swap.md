---
date: 2026-04-28
scenarios: 1 (session swap, partial) + 2 (multi-agent role split, mostly complete)
operator: claude-code (autonomous, no human paste-back yet)
result: artifact generation works; killer-demo content gap (Bug 3) was real and is now fixed in #70
---

# Dogfood — Multi-Agent Role Split + Session Swap (staged)

> **Status (2026-04-28, post-fix)**: the prediction in this doc that the resume packet would fail the killer-demo question is now **outdated** — PR #70 fixed the underlying content-density bug. The runbook below should now show "PASS" if you re-drive it. Bug 6 (role protocol duplication) remains open as #67.

This doc covers two related scenarios. Scenario 2 (role split) is exercisable solo because it's pure prompt generation. Scenario 1 (session swap) needs a human pasting between two agent sessions — staged here as a runbook.

## Scenario 2 — Multi-Agent Role Split

### What I ran

```bash
uv run spanweave prompt --role coder --agent codex \
  --run run_01KPT1YDEK0F9MYKW4R1VMY7XY > coder_codex.md

uv run spanweave prompt --role reviewer --agent claude-code \
  --run run_01KPT1YDEK0F9MYKW4R1VMY7XY > reviewer_claude.md
```

### What worked

- **Role-specific protocol leads each prompt.** Coder gets "Implementation-focused protocol — Act as the Coder agent... smallest coherent changes". Reviewer gets "Review-focused protocol — Execution is mandatory: inspect the diff and relevant files directly... lead with findings ordered by severity". This is the role differentiation the design promises.
- **Tool framing per role.** Coder-codex uses `# AGENTS.md Context Packet` framing; reviewer-claude-code uses `# CLAUDE.md Context Packet` framing. The orthogonal axes (role × tool) are independent — you can mix any role with any agent.
- **Clean output.** Both prompts are ~80 lines, copy-paste ready, no ANSI escapes or extraneous CLI chrome on stdout.
- **Reviewer protocol explicitly mandates execution.** Matches the project's "Evidence over vibes" principle from the brief — the Reviewer prompt itself says "Execution is mandatory: inspect the diff and relevant files directly, run or request the concrete verification commands".

### What broke

### Bug — Role protocol is duplicated as both leading-block AND a "Prior Decision" (LOW severity, filed as #67)

In the generated prompt:

```
## Implementation-focused protocol     ← top of prompt
Act as the Coder agent. Inspect...

# AGENTS.md Context Packet
...
## Prior Decisions
- Implementation-focused protocol: Act as the Coder agent. Inspect...   ← same content, again
- Persist workflow evidence for 001-specify
...
```

The role protocol shows up twice — once as the leading directive, once injected as a `Decision`. Wasteful tokens; mildly confusing for an agent reading the prompt linearly.

**Suggested fix shape:** filter role-protocol decisions out of the "Prior Decisions" rendering when rendered for the same persona.

### What surprised me

- **`prompt` is functionally a stateless reduction over the run.** It generates fresh output each time from the persisted .spanweave/memory/ + workflow_state. This is the files-first invariant being load-bearing: nothing is "captured by the CLI" — it's all derived from the filesystem.
- **The same role can be repeated across tools.** Nothing stops you from running `prompt --role coder --agent codex` AND `prompt --role coder --agent claude-code` simultaneously and feeding the same context to two different coders. Whether that's a feature or a footgun is unclear.

---

## Scenario 1 — Session Swap (staged for human driver)

This is the killer-demo scenario per the brief. It needs you (human) to paste outputs between two agent terminals.

### Runbook to drive the killer demo

You will need: two terminals (Codex + Claude Code).

**Step 1 — Verify state pre-swap:**

```bash
cd /home/fei/fei/code/hackathon/agentic-coding-workflow-os
uv run spanweave run show run_01KPT1YDEK0F9MYKW4R1VMY7XY
# Expect: 8 stages all completed, status "completed"
```

**Step 2 — Generate fresh packets and open in two terminals:**

```bash
uv run spanweave resume --agent claude-code --run run_01KPT1YDEK0F9MYKW4R1VMY7XY > /tmp/claude_packet.md
uv run spanweave resume --agent codex        --run run_01KPT1YDEK0F9MYKW4R1VMY7XY > /tmp/codex_packet.md
# Paste each into the corresponding agent in a fresh terminal.
```

**Step 3 — Ask both agents the brief's pass-criterion question:**

```
What was decided in specify for issue #24?
```

**Expected outcome (post-#70):** both agents should now answer with the actual specify content — `Allow at most 5 failed attempts per client IP in a rolling 60-second window`, the retry-after rules, and the five acceptance criteria. The resume packet now embeds the per-stage briefings directly.

**Findings to record after you drive it:**

```
- Did Claude Code answer the specify question without re-explaining? [YES/NO]
- Did Codex give the same answer with no quality difference? [YES/NO]
- Which packet "felt better" to the receiving agent? [Claude/Codex/equal]
- Surprising quality gaps between framings? [free text]
```

### Why staged, not driven

Driving this scenario from inside one Claude Code session would need either:
- A second Claude Code session in a sub-shell (not naturally supported)
- The LLM emulating the "fresh agent reading the packet" behavior — which is fake (I already have the run context in my own conversation, so I can't honestly judge whether the packet is sufficient)

The honest answer is: this needs a human + two real terminals. Everything is staged for you to drive in <5 minutes whenever convenient.

---

## Combined verdict

- Scenario 2 plumbing works; one cosmetic dedupe bug remains as #67.
- Scenario 1 still needs human in the loop. Post-#70, the most likely failure mode (resume packet too thin) is no longer present; remaining unknowns are framing quality differences between Claude Code and Codex that only a real swap can reveal.

## Real swap, 2026-05-07
### Claude Code answered: [yes/no, quote of best line]
Here's what the specify stage recorded for issue #24, drawn from the run's stage artifacts. (The skill's
  spec.md output lived in the run worktree at
  /home/fei/fei/code/hackathon/worktrees/run_01KPT1YDEK0F9MYKW4R1VMY7XY, which the 008-cleanup stage
  removed — so the durable record of the decision is the stage packet + evidence pack, not a versioned
  spec.md in specs/.)

  ★ Insight ─────────────────────────────────────
  - This run is a demo-mode speckit-loop: the issue lives at demo/issue.md rather than under specs/NNN-…/,
  so the artifact you'd normally read (specs/<feature>/spec.md) was never written into the main tree — it
  lived in the run's ephemeral worktree.
  - The specify stage in this codebase has two layers of "decision": a process-level approval recorded in
  evidence.md (Reviewer verdict + confidence), and the substantive spec content carried in the packet's
  issue_text + acceptance_gate blocks. After 008-cleanup, the second layer survives only via that packet.
  - The packet's acceptance_gate block is the load-bearing summary downstream stages (plan/tasks/uat)
  consume — it's the canonical "what specify decided" handoff.
  ─────────────────────────────────────────────────

  Process-level decision (from 001-specify/.evidence/current/evidence.md)

  - Verdict: APPROVED
  - Confidence: 95%
  - Reviewer persona: reviewer.integration
  - Findings: none (RED/ORANGE/YELLOW all empty)
  - Outcome: packet judged actionable; next command /speckit.specify; stage cleared to write filesystem
  artifacts for replay.

  Substantive spec (carried in the stage packet's issue text + Clarified Constraints + Acceptance Gate)

  Behavior
  - Cap failed POST /login at 5 per client IP per rolling 60-second window.
  - 6th attempt (and onward, while blocked) → 429 Too Many Requests with Retry-After as an integer seconds
  value, rounded up, never 0 while blocked.
  - Window is rolling (not a fixed-duration ban): IP becomes eligible again the moment the oldest counted
  failure ages out of the last 60 s.
  - While blocked, even a correct password gets 429 for that IP.
  - Successful login resets the IP's failed-attempt bucket if the IP is not already blocked.
  - Happy path preserved post-unblock: 303 See Other + session cookie + access to /notes.
  - Browser flow shows a human-readable wait message instead of silent failure.

  Constraints / scope
  - Identity = raw client IP observed locally; no proxy / X-Forwarded-For handling (out of scope).
  - Storage = process-local in-memory (acceptable demo limitation; multi-instance drift and process-restart
   loss accepted).
  - Generic invalid-login response — must not reveal whether email exists vs. password wrong.

  UAT gate (acceptance criteria 1–5)
  1. Attempts 1–5 from one IP processed normally; 6th in same 60 s → 429 without evaluating credentials.
  2. Further attempts from blocked IP → 429 + browser wait message.
  3. Every 429 carries Retry-After; integer; ≥1 while blocked.
  4. Once <5 failures remain in the trailing 60 s, login flow resumes normally (303 + cookie + /notes).
  5. Reproducible on localhost in ≤6 failed POSTs using demo@atelier.dev from demo/app/.env.example.

  Reviewer attack surface called out
  Off-by-one between the 5th/6th attempt; Retry-After math at the 60 s boundary / under clock skew;
  127.0.0.1 vs ::1 bucketing; per-process counter divergence across instances.

  That's the decision set the downstream stages (clarify → plan → tasks → implement → uat) inherited.

  ### Codex answered:       [yes/no, quote of best line]
   For issue #24, the 001-specify stage decided that the demo app should rate-limit failed POST /login
  attempts by client IP.

  Core decisions from .atelier/runs/run_01KPT1YDEK0F9MYKW4R1VMY7XY/stages/001-specify/packet.md:73:

  - Allow at most 5 failed attempts per client IP in a rolling 60 second window.
  - Attempts 1-5 stay on the normal invalid-login path; the next attempt returns 429 Too Many Requests
    without evaluating credentials.
  - While blocked, every POST /login from that IP gets 429, even with the correct password.
  - Every 429 must include Retry-After, rounded up to an integer, minimum 1 while still blocked.
  - The IP becomes eligible again as soon as fewer than 5 failures remain in the rolling 60-second window.
  - A successful login resets that IP’s failed-attempt bucket only if the IP is not already blocked.
  - Client identity is the app-observed remote IP; proxy-aware headers are out of scope.
  - Storage is process-local in-memory for the demo, accepting restart and multi-instance limitations.
  - UAT must be reproducible locally through the browser and curl in 6 failed submissions or fewer using
    credentials from demo/app/.env.example.

  The acceptance gates are also captured in demo/issue.meta.yaml:43.
  
  - Quality difference:   [free text — framing? hallucination? confidence? brevity?]
  - Surprises:            [anything you didn't expect]