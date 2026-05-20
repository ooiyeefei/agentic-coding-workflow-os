# Hackathon Build Plan — UCWS Singapore 2026

> **Track**: Agent
> **Deadline**: Online screening Jun 3–5; Demo Day Jun 13 Singapore
> **Submission**: Project name + description + screenshots + demo PDF (max 50MB)
> **Repo**: https://github.com/ooiyeefei/agentic-coding-workflow-os (Apache 2.0)

---

## Product sentence (for submission form)

**Spanweave** — the shared memory layer for AI coding teams. Context persists across agent tools (Claude Code ↔ Codex ↔ Cursor). Decisions are typed, timestamped, and git-synced. No new platform. No SaaS. Just files in your repo.

---

## Three demo scenarios (all validated E2E as of 2026-05-20)

### Demo 1 — Cross-tool session swap (single human, multi-agent)

```bash
# Alice works in Codex, generates decisions during a workflow run
# Later, switches to Claude Code:
spanweave resume --agent claude-code --run run_01KPT1YDEK0F9MYKW4R1VMY7XY
# → Claude Code gets a 322-line packet with full specify/clarify/plan briefings
# → Answers "what was decided in specify?" correctly without re-explaining
```

**What judges see**: zero context loss across tools. "No other tool does this."

### Demo 2 — Cross-user resume via git (multi-human, multi-agent)

```bash
# Alice commits .spanweave/memory/ → git push
# Bob clones, runs:
spanweave run list        # sees Alice's run
spanweave resume --agent codex --run run_01KPT1YDEK0F9MYKW4R1VMY7XY
# → Bob gets Alice's full context, typed decisions, temporal ordering
```

**What judges see**: team collaboration through git — no Notion, no Confluence, no SaaS middleware. Agents share memory natively.

### Demo 3 — Temporal decision query (event-sourced engineering memory)

```bash
# Every decision has: timestamp, run_id, stage_id, source, tags, confidence
# Query: "What was decided before the plan stage?"
grep -l "stage_01KPT1YDH\|stage_01KPT1YDJ" .spanweave/memory/decisions/*.md

# Query: "What did we reject and why?"
cat .spanweave/memory/rejected_alternatives/*.md
# → Shows: "Keep workflow validation in memory only"
#    with tradeoffs: "Good because... Bad because..."
```

**What judges see**: decisions are first-class data, not buried in chat history. Greppable, git-synced, queryable by time.

---

## Build plan (what to ship for hackathon)

### Already done (Phase 0 complete) — no new code needed for core demo

| Feature | Status | Lines of code |
|---|---|---|
| CLI with 11 subcommands | ✅ shipped | ~4000 |
| Typed memory records (Decision, ReviewFinding, RejectedAlternative, SkillOutcome) | ✅ shipped | ~200 |
| Context compiler with priority tiers + token budget + provenance | ✅ shipped | ~400 |
| Tool adapters (Claude Code + Codex) with per-tool framing | ✅ shipped | ~500 |
| Session continuity (resume, prompt, context) | ✅ shipped | ~600 |
| Workflow engine (speckit-loop YAML, 8 stages) | ✅ shipped | ~800 |
| Evidence packs + auto-ADR synthesis | ✅ shipped | ~400 |
| Policy engine | ✅ shipped | ~300 |
| Skill feedback loop (derive rules from past failures) | ✅ shipped | ~200 |
| Security best-practice skill + 6 feedback rules | ✅ shipped | ~100 |
| 417 tests (unit + integration), CI green | ✅ shipped | ~3000 |

### To build for hackathon polish (fits Phase 1 roadmap, no plan deviation)

| Task | Why it wows judges | Effort | Priority |
|---|---|---|---|
| **Tool-rules auto-load** | Demo starts with "it just works — open Claude Code, it already knows your last session" | 30 min | P0 |
| **Adapter auto-detection** | `spanweave resume` with no `--agent` flag — auto-detects which tool you're in | 2-3h | P0 |
| **`spanweave query` CLI command** | One-liner temporal queries: `spanweave query "decisions before plan stage"` | 3-4h | P1 |
| **Fix #72** (real Decisions, not auto-stubs) | Demo decisions show actual content, not "Persist workflow evidence" stubs | 1-2h | P1 |
| **Demo video (30-60 sec GIF/MP4)** | Side-by-side split screen: Codex left, Claude Code right, Spanweave terminal center | 2-3h | P0 |
| **Pitch deck (PDF)** | Architecture diagram + competitive table + 3 demo scenarios | 2-3h | P0 |
| **README polish for public** | First impression for judges browsing GitHub | 1h | P0 |

### NOT building (saves for later, not demo-critical)

| Skip | Why |
|---|---|
| Memory namespaces (private/shared) | Mention in pitch as "next"; don't build |
| Cursor / ChatGPT adapters | Breadth without wow |
| MAD / LLM Council | Complex, hard to demo in 5 min |
| Web dashboard | Out of scope for CLI-first |
| MCP server | Auxiliary channel, not primary |
| Conflict resolution | Real-world scaling, not demo |

---

## Timeline (→ Jun 3 screening)

| Week | Deliverable |
|---|---|
| **May 20–23** | Tool-rules auto-load + adapter auto-detection + fix #72. All three are code tasks, parallelizable. |
| **May 23–27** | `spanweave query` CLI + README polish. Drive a fresh E2E demo recording. |
| **May 27–Jun 1** | Pitch deck (PDF). Screenshots (4). Demo video (GIF). Register + submit on UCWS platform. |
| **Jun 1–3** | Buffer for polish. Submission finalized. |
| **Jun 3–5** | Online screening period. Project already submitted. |
| **Jun 13** | Demo Day Singapore (if selected). |

---

## Submission materials spec

### Screenshots (3-5, PNG, max 5MB each)

1. **CLI overview** — `spanweave --help` output in a clean terminal
2. **Cross-tool swap** — side-by-side: Claude Code packet header vs Codex packet header (showing tool-specific framing on identical body content)
3. **`.spanweave/` directory tree** — `tree .spanweave/ -L 3` showing the substrate on disk
4. **Temporal decisions** — a decision record with timestamp, source, tags visible in frontmatter
5. **Resume packet content** — the "Recent Stage Context" section showing rich specify-stage briefing embedded in the packet

### Demo file (PDF, max 50MB)

**Slide deck (8-10 slides):**

1. Title: "Spanweave — Shared memory for AI coding teams"
2. Problem: context dies with the session; decisions evaporate; switching tools = start over
3. Wrong answer: another platform (Mesh Code, Conductor → vendor lock-in)
4. Right answer: files in git, the one thing ALL tools share
5. Architecture diagram: substrate → adapters → tool-specific packets
6. Demo 1: cross-tool swap (screenshot + flow)
7. Demo 2: cross-user resume via git (screenshot + flow)
8. Demo 3: temporal query (screenshot + flow)
9. Competitive landscape: vs Conductor, Mesh Code, Mem0/Cognee/Zep, Sympozium (different layer)
10. What's next: memory namespaces, MCP server, adapter auto-detection, UX taste capture

### GitHub repo (already public, Apache 2.0)

Polish checklist:
- [ ] README leads with the product sentence + the three demo scenarios
- [ ] "Quick start" section: `uv sync && spanweave init --repo . && spanweave run --issue 1`
- [ ] Badges: CI status, license, Python version
- [ ] Remove or move historical docs that confuse first-time visitors (phase0_plan.md, phase0_launch.md → docs/historical/)
- [ ] Ensure `spanweave --version` shows a clean version string

---

## Competitive positioning (for pitch deck)

| Tool | What it is | Why Spanweave is different |
|---|---|---|
| **Conductor** | macOS workspace orchestrator | No context portability, no persistent memory, no cross-tool swap |
| **Mesh Code** | Real-time agent state sharing | Team-first, centralized SaaS. We're files-first, git-native, zero infra. |
| **Mem0 / Cognee / Zep** | Memory layer for LLM API apps | Built for apps calling APIs. We're for humans using agent TOOLS. Different category. |
| **Sympozium** | K8s coordination layer for agent fleets | Solves real-time ops-agent coordination. We solve coding-agent context portability. Complementary layers. |
| **Claude Code / Codex** | Single-vendor CLI agents | Session-locked. Context dies. We make their context portable and persistent. |

---

## Judging angles (what we optimize for)

Based on "NO RULES. JUST CREATE. BREAK THE RULES. CHANGE THE FUTURE" — this hackathon values:

1. **Practicality** — "real usage and impact." Our E2E swap demo is a real validated workflow.
2. **Innovation** — "nobody else does cross-agent context portability." True. Verified.
3. **Technical depth** — 417 tests, 11 CLI commands, typed records, adapter ecosystem pattern, event-sourced decisions.
4. **Open source quality** — Apache 2.0, clean repo, CI green, comprehensive README.

---

## Risk assessment

| Risk | Mitigation |
|---|---|
| Judges don't understand "substrate" (too abstract) | Lead with the demo, not the architecture. "Watch: I switch from Codex to Claude Code, zero context lost." |
| "Why not just use a database?" | Answer: "Because every agent tool reads files. Not every agent tool queries your DB. Files in git = universal read surface + free sync + free audit trail." |
| "How is this different from just copying a text file?" | Answer: "Try copying your 200-line Codex session into Claude Code. Spanweave does it in one command — with tool-specific framing, token budgets, provenance tracking, and typed decisions." |
| Competition from well-funded teams | Our moat: already validated E2E. Most hackathon projects demo a video, not a working product. We have 417 tests. |
