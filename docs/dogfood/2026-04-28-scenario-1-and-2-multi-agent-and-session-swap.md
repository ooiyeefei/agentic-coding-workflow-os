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
