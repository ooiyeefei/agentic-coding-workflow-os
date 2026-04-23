# Agentic Coding Workflow OS — Product Roadmap

> **Working name**: _Atelier_ (placeholder — final naming TBD)
> **Status**: Phase 0 in progress. 21 of 24 original components merged. Architectural reframe underway — tool adapter layer + session continuity replacing direct LLM API approach.
> **Origin**: Distilled from battle-tested workflow on a safety-critical HAZOP/LOPA AI system (TIROS) where wrong outputs could kill people.

---

## Product Sentence

The **shared knowledge substrate** for AI-assisted engineering. Markdown files in git — readable by any agent tool, writable by any agent tool, syncable by git. No new platform to adopt. No switching cost. Decisions persist. Context follows you.

## Vision

### The problem

Developers use **individual** agent tools — Claude Code, Codex, Cursor, ChatGPT, Gemini, Cowork. These are personal and individualistic. No team will agree on one tool, and they shouldn't have to.

But this creates three unsolved problems:

1. **Context dies with the session.** You spend 2 hours building context in Codex. Switch to Claude Code — start from zero. Context compaction deletes your earlier discussion mid-session.
2. **Decisions evaporate.** You and your agent decided to use approach X over Y. Next session, the agent doesn't know. Next teammate, they don't know. The decision exists nowhere but your memory.
3. **Collaboration requires same-tool lock-in.** Old-world: everyone uses Slack/Linear/Notion. New-world: Alice uses Claude Code, Bob uses Codex, Carol uses Cursor. How do they share context without forcing one tool?

### The wrong answer

"Use our new tool that connects all your tools." That's just another platform to adopt — another vendor lock-in, another switching cost. Mesh Code, Conductor, Hyperspell all fall into this trap.

### The right answer

Find the **fundamental shared layer** that ALL agent tools already use, and make THAT the collaboration substrate.

What's universal across every agent tool?
- **Files on disk** — every agent reads and writes files
- **Git** — every coding tool works with git
- **Markdown** — every LLM can read it, every human can read it

The substrate is: **a `.atelier/` directory in your git repo, containing decisions, evidence, context, and rules as markdown files.** Every tool can read them. Git handles sync. No infrastructure. No accounts. No SaaS.

### How it works

```
Alice (Claude Code)                    Bob (Codex)                    Carol (Cursor)
       │                                    │                              │
       │ writes decisions to                │ reads decisions from         │ reads from
       │ .atelier/memory/                   │ .atelier/memory/             │ .atelier/memory/
       │                                    │                              │
       └──────── git push ──── repo ──── git pull ──── git pull ───────────┘

No shared platform. No new tool. Just git.
```

**Session swap with zero context loss:**
```
Day 1: You use Codex (730K token session)
  → Atelier captures decisions + context to .atelier/memory/

Day 2: You switch to Claude Code
  → atelier resume --agent claude-code
  → Claude Code gets a Context Packet built from .atelier/memory/
  → Zero re-explaining. Full continuity.
```

### The core reframe

Atelier is NOT an agent framework. It is NOT a platform. It is the **shared knowledge substrate** for agentic engineering work.

- `.atelier/memory/` = reproducible decisions (typed records: Decision, ReviewFinding, RejectedAlternative)
- `.atelier/runs/` = reproducible delivery (Run Graph with Evidence Packs)
- `.atelier/workflows/` = reproducible process (workflow-as-code YAML)
- `docs/adr/` = reproducible architecture (auto-generated ADRs)
- Git = the sync mechanism, audit trail, and collaboration layer

The competitive moat is not the format (anyone can read markdown). The moat is the **adapter ecosystem** — Atelier knows how to read Claude Code's session JSONL, Codex's transcripts, Cursor's Composer history, and how to format Context Packets for each tool's conventions.

---

## Design Principles (non-negotiable)

1. **Files first, indexes second.** Markdown + YAML frontmatter for every persistent entity. Any DB added later is a rebuildable cache, never source of truth.
2. **CLI is the real product.** Plugins and web UIs are thin surfaces over the same control plane.
3. **Tool-agnostic, not just model-agnostic.** Claude Code, Codex, Cursor, ChatGPT, Cowork, Gemini — any agent tool. Atelier is the middle layer, not a replacement.
4. **Format over platform.** Don't build an app people have to adopt. Build files people already have in their repo. The `.atelier/` directory IS the product. Think RSS, not Facebook.
5. **Zero migration cost.** Switching agent tools preserves all context. No export/import. No data hostage. Files stay in git.
6. **Human-in-the-loop at destructive gates.** Never auto-resolve meaningful merge conflicts. Never auto-push. Never auto-accept council verdicts on significant changes.
7. **Steering without locking.** Ship opinionated defaults. Users override with explicit `reason:`. Deviations logged to audit.
8. **Parallelization as default.** Workflow engine always scans for parallelizable work. Sequential only when dependencies require it.
9. **Dry-run first.** Every destructive action has `--dry-run`. Live execution requires explicit confirmation.
10. **Evidence over vibes.** The Reviewer must paste real command output. Approval without execution evidence is incomplete.
11. **Dogfood all the way down.** The product is built with the product.

---

## Architecture Overview

```
┌────────────────────────────── AGENT TOOLS (user's choice) ──────────────────────────┐
│   Claude Code  │  Codex  │  Cursor  │  ChatGPT  │  Cowork  │  Gemini  │  Any MCP    │
└────────────────────────────────────┬────────────────────────────────────────────────┘
                                     │ reads .atelier/ · writes transcripts
┌────────────────────────────────────▼────────────────────────────────────────────────┐
│                     TOOL ADAPTER LAYER (the bridge)                                 │
│                                                                                     │
│  ┌─────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐│
│  │ Claude Code │ │  Codex   │ │  Cursor  │ │ ChatGPT  │ │  Generic │ │   MCP    ││
│  │  adapter    │ │ adapter  │ │ adapter  │ │ adapter  │ │ adapter  │ │  server  ││
│  └──────┬──────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘│
│         │             │            │             │            │            │       │
│  Each adapter:                                                                     │
│    1. INGEST — read tool's session state → extract decisions → .atelier/memory/    │
│    2. FORMAT — read .atelier/memory/ → generate Context Packet for tool's format   │
│    3. DETECT — auto-detect which tool is running                                   │
└────────────────────────────────────┬────────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────────────────┐
│                          CONTROL PLANE (the product core)                           │
│                                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                     WORKFLOW ENGINE (workflow-as-code)                       │  │
│  │    stage transitions · review gates · MAD escalation · resume               │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  ┌───────────────────┐  ┌──────────────────┐  ┌─────────────────────────────┐     │
│  │ CONTEXT COMPILER  │  │ PERSONA LIBRARY  │  │   SKILLS LIBRARY            │     │
│  │                   │  │                  │  │                             │     │
│  │ priority tiers    │  │ Coder · Reviewer │  │ /speckit.specify + clarify  │     │
│  │ token budgets     │  │ Guide · UAT      │  │ /speckit.plan + tasks       │     │
│  │ provenance        │  │ Debate Panelist  │  │ /speckit.implement          │     │
│  │ dedupe            │  │                  │  │ /rebase-before-pr           │     │
│  │                   │  │ generates prompts│  │ /cleanup-worktree           │     │
│  │                   │  │ FOR agent tools  │  │ /uat-test                   │     │
│  │                   │  │ (not API calls)  │  │ (extensible by users)       │     │
│  └─────────┬─────────┘  └────────┬─────────┘  └──────────────┬──────────────┘     │
│            │                     │                            │                     │
│  ┌─────────▼─────────────────────▼────────────────────────────▼──────────────────┐ │
│  │                    KNOWLEDGE PLANE (cross-cutting)                            │ │
│  │                                                                               │ │
│  │  ┌────────────────────┐          ┌──────────────────────────────────────┐    │ │
│  │  │ RULES              │          │ MEMORY (typed records in markdown)   │    │ │
│  │  │ (what MUST be)     │          │  · Decision                          │    │ │
│  │  │ path-matched       │          │  · Constraint                        │    │ │
│  │  │ precedence         │          │  · RejectedAlternative               │    │ │
│  │  │ override+reason    │          │  · IssueLearning                     │    │ │
│  │  └────────────────────┘          │  · ReviewFinding                     │    │ │
│  │                                   │  · MergeConflictResolution           │    │ │
│  │                                   │  · ReleaseChange                     │    │ │
│  │                                   │  · Observation (Phase 2)             │    │ │
│  │                                   │  · UXTastePreference (Phase 2)       │    │ │
│  │                                   │  → derives ADRs, changelogs          │    │ │
│  │                                   └──────────────────────────────────────┘    │ │
│  └───────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                     │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │ EVIDENCE PACK│  │ GIT HYGIENE      │  │ POLICY ENGINE    │  │ AUXILIARY LLM  │ │
│  │              │  │                  │  │                  │  │                │ │
│  │ JSON+MD      │  │ worktree mgmt    │  │ approval gates   │  │ council votes  │ │
│  │ audit-linked │  │ rebase-analyze   │  │ dry-run defaults │  │ ADR prose      │ │
│  │ replay-ready │  │ force-with-lease │  │ cost caps        │  │ transcript     │ │
│  │              │  │ never auto-resolve│ │ configurable     │  │   extraction   │ │
│  └──────────────┘  └──────────────────┘  └──────────────────┘  └────────────────┘ │
│                                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                 SESSION CONTINUITY                                           │  │
│  │  atelier resume --agent <tool> · atelier prompt --role <role> --agent <tool> │  │
│  │  atelier context --for <tool> · transcript ingestion · session swap          │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                 ORCHESTRATOR                                                 │  │
│  │  issue DAG · worktree planner · session router · audit log (JSONL)           │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────────────────┐
│                 STORAGE (the shared substrate — filesystem-first, git-native)       │
│  .atelier/runs/ · .atelier/memory/ · .atelier/workflows/ · .atelier/audit/         │
│  docs/adr/ · docs/changes/ — all markdown, all git-tracked, all tool-readable      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Key architectural distinction from prior version:**
- **"LLM Abstraction"** is now **"Auxiliary LLM Backend"** — narrow scope, only for council votes, ADR prose synthesis, and transcript extraction. NOT for the main coding workflow.
- **NEW: "Tool Adapter Layer"** — the bridge between Atelier and whatever agent tool the user chooses. Each adapter knows how to ingest transcripts FROM a tool and format Context Packets FOR a tool.
- **NEW: "Session Continuity"** — the ability to resume, swap, and port context across agent tools and sessions.
- **Personas** generate **prompts for agent tools**, not direct LLM API calls. The agent tool (Claude Code, Codex, etc.) is the executor.

---

## Storage Philosophy (Filesystem-First)

Every persistent entity is a markdown file with YAML frontmatter. Directory structure IS the schema. Git is the audit trail primitive. Queries use `rg`, `find`, and frontmatter parsing. No database in the core.

**Why this is the only correct choice for a shared substrate**: files are the lowest common denominator that EVERY agent tool can read. Claude Code reads `.claude/rules/*.md`. Codex reads `AGENTS.md`. Cursor reads `.cursorrules`. ChatGPT users copy-paste from files. Git syncs files across machines and users. No API integration needed. No accounts. No vendor dependency.

Canonical layout:
```
.atelier/
├── runs/<run_id>/
│   ├── run.md                     # frontmatter + summary
│   ├── audit.jsonl                # per-run audit
│   └── stages/<nnn-stage-name>/
│       ├── stage.md
│       ├── packet.md              # Context Packet
│       ├── transcript.jsonl       # agent messages (append-only)
│       ├── evidence.md            # human-readable Evidence Pack
│       ├── evidence.json          # machine-ingestible sidecar
│       ├── decisions/<dec_id>.md
│       └── findings/<find_id>.md
├── memory/
│   ├── decisions/<dec_id>.md
│   ├── review_findings/<find_id>.md
│   ├── rejected_alternatives/<alt_id>.md
│   └── INDEX.md                   # auto-regenerated summary
├── workflows/<name>.yaml          # user-defined workflows (overrides defaults)
├── policy.yaml                    # user-defined policy (overrides defaults)
├── overrides.yaml                 # user's deviations from defaults + reasons
└── audit/YYYY-MM-DD.jsonl         # cross-run daily audit
```

**Integration into each agent tool (zero new tools to install):**

| Agent tool | How it reads `.atelier/` | How Atelier captures from it |
|---|---|---|
| **Claude Code** | `.claude/rules/atelier.md` references `.atelier/memory/`. CLAUDE.md says "read decisions before starting." | Atelier CLI parses `.claude/projects/` session JSONL → extracts decisions. |
| **Codex** | `AGENTS.md` references `.atelier/memory/`. | Atelier CLI parses Codex session logs → extracts decisions. |
| **Cursor** | `.cursorrules` references `.atelier/memory/`. | Atelier CLI parses Composer history → extracts decisions. |
| **ChatGPT / Cowork / Gemini** | `atelier context --for chatgpt` generates paste-ready summary. | `atelier ingest --from transcript.md` for manual transcript capture. |
| **Any MCP tool** | Atelier MCP server exposes `.atelier/` as resources. | MCP tools write to `.atelier/` via Atelier MCP. |

---

## Phases

### Phase 0 — Foundation (MVP)

**Exit criteria**: A real GitHub issue flows end-to-end through a user-defined workflow, producing Evidence Pack + auto-generated ADR + Run Graph on filesystem, invokable from the CLI. Context Packets can be generated for at least Claude Code + Codex. Session continuity works (resume across tools). All components dynamic and configurable.

**Must-ship**:
- Filesystem-first storage (no DB)
- ULID generator + path helpers
- **Tool Adapter Layer** — at least Claude Code + Codex adapters: ingest transcripts, format Context Packets, detect running tool
- **Session Continuity** — `atelier resume --agent <tool>`, `atelier prompt --role <role> --agent <tool>`, `atelier context --for <tool>`
- **Auxiliary LLM Backend** (narrow scope) — Anthropic + OpenAI adapters for council tiebreaker, ADR prose synthesis, transcript decision extraction only. NOT for main workflow.
- Persona Library (Coder, Reviewer) — generates prompts FOR agent tools, NOT direct API calls. Devil's-advocate Reviewer flag (default off).
- Skills Library (extensible — ships with speckit.* + `/rebase-before-pr`, `/cleanup-worktree`, `/uat-test`)
- Context Compiler (priority tiers + token budget + provenance)
- Workflow Engine (workflow-as-code, loads from `.atelier/workflows/*.yaml`, ships with `speckit-loop.yaml`)
- Policy Engine (configurable from `.atelier/policy.yaml`)
- Knowledge Plane with 3 typed record types (Decision, ReviewFinding, RejectedAlternative)
- Evidence Pack (JSON + Markdown)
- Auto-ADR synthesis (MADR 3.0 format)
- Git Hygiene (worktree create, rebase-analyze read-only, cleanup)
- Secret redaction (regex-based)
- Audit log (JSONL)
- Rule precedence (2 levels: core + repo)
- CLI with full command set including `resume`, `prompt`, `context`
- UAT persona
- 3-agent council tiebreaker

**What changed from original Phase 0**: "LLM Abstraction" was the core. Now it's a narrow auxiliary backend. The core is the **Tool Adapter Layer** + **Session Continuity** — the ability to port context across agent tools. Personas no longer call LLM APIs for the main workflow; they generate prompts for external agent tools.

### Phase 1 — Adapter Ecosystem + Multi-Agent Debate + Simulation Mode

- Additional tool adapters: Cursor, ChatGPT, Gemini, Cowork, generic clipboard
- Adapter auto-detection (scan for `.claude/`, Codex env vars, `.cursorrules`, etc.)
- Full MAD (Du 2023) and LLM Council (Karpathy anonymization) protocols
- Convergence detection, round caps, anonymized peer ranking, chairman synthesis
- Escalation at clarify gates, deadlocks, ADR authorship, merge-conflict recommendations
- **Simulation / dry-run mode for workflows**: workflow YAML gains a `simulation:` block declaring `enabled`, `fixture` path (JSONL of recorded agent responses), and `assertion` expressions. When enabled, the Workflow Engine replays fixtures instead of invoking agent tools. Unlocks: (a) testing workflow design without LLM cost, (b) deterministic CI for workflow changes, (c) foundation for Phase 3 meta-improvement. Pattern inspired by observed agent-to-agent eval loops — formalizes "harness of a harness" as a first-class primitive. Fixtures are captured from real runs via `atelier run record <id>`.

### Phase 2 — Parallel Orchestration + Meta-Observation + UX Taste Capture

- Issue dependency DAG analyzer (reads GitHub issues, labels, links)
- Worktree planner (maximum parallelism while respecting deps)
- Concurrent agent sessions across worktrees
- Cross-worktree memory sync
- Session router handling multi-terminal routing
- **Meta-Observation Gates** at stage transitions — captures human feedback as `Observation` memory records
- **UX Taste Capture system** — solves the "human QA is the bottleneck for UX-heavy products" problem:
  - New typed record: `UXTastePreference` (rule, rationale, applies_to_paths, confidence, source: user_rejection / golden_example / codified_rule, linked accepted + rejected examples)
  - New persona: `UXReviewer` — execution-mandatory protocol adapted for UI:
    1. Reads all `.atelier/memory/ux_preferences/` matching the diff's file paths
    2. Captures screenshots of rendered UI via Playwright (or equivalent) through a new `ScreenshotAdapter`
    3. Compares against golden examples
    4. Generates Evidence Pack with specific violations referencing preference record IDs
  - Capture command: `atelier taste capture --run <id> --reject "too cramped, buttons too close"` — uses auxiliary LLM to extract rule + applicable path patterns + link to rejected artifact
  - Over 20-30 captures, agent builds rich corpus of user's taste. Exportable via git. Team-shareable.
  - Pattern: "taste is not unlearnable — it's just undocumented." Captures the rejection reasons before they evaporate.

### Phase 3 — Rules Engine + Memory Namespaces + Replay Harness + Meta-Improvement

- Full rule precedence model: `core < org < repo < workflow/stage < human override`
- Path-matched rule loading
- Memory namespaces: `repo-local` / `user-private` / `org-shared` with opt-in tagging
- Replay harness: rerun old runs against new prompts/workflows/models
- **MemoryBackend interface**: pluggable backend for cross-agent sync. Evaluate memory-bridge, Memorix, MemClaw before building.
- **Meta-Improvement workflow** (extends Replay Harness) — makes the "auto-*" paradigm first-class:
  - Takes an existing completed run + a proposed change (new instruction set, persona prompt, workflow YAML, or model routing) → reruns with the change → compares Evidence Packs, cost, latency, approval counts, and review-finding quality against baseline
  - Eval Monitor persona: judges whether v2 instructions produce better outcomes than v1 — produces a structured verdict Evidence Pack
  - Long-horizon improvement loops: agent modifies instruction set → replay against corpus of past runs → Eval Monitor scores → agent iterates
  - All iterations are Decision records in git — every improvement is auditable, reversible, comparable
  - Solves the problem observed in agent-to-agent eval loops: improvement without durable memory is lossy and un-reproducible. Our files-first substrate makes the iteration graph queryable and portable.
  - CLI: `atelier meta improve --target-run <id> --change persona:coder=v2.md` → produces side-by-side comparison report.

### Phase 4 — Git Hygiene Complete + Event Bus + Observability

- Rebase-before-PR full automation (analyze + suggest; human-approve destructive ops)
- Force-with-lease safety wrapper
- Event bus (webhooks for Slack/Linear/PagerDuty)
- OpenTelemetry integration
- Cost budget enforcement per-run/per-day/per-model
- External context source adapters for Context Compiler (Hyperspell, direct GitHub/Linear/Jira API — opt-in, read-only feeds into packets)

### Phase 5 — IDE Extensions

- VSCode extension (covers Cursor, Windsurf, Void)
- Zed extension
- All are thin clients over the CLI / HTTP daemon

### Phase 6 — Web Dashboard + GitHub App

- Team visibility dashboard (memory search, Evidence Pack archive, cost analytics)
- GitHub App (run Atelier on PRs, post Evidence Packs as PR comments)
- GitLab / Bitbucket adapters

### Phase 7 — Team / Org Scaling

Team value comes from **auto-updated documentation as source of truth** (ADRs, typed decisions in git), NOT from real-time state sharing. Git is the sync mechanism, not a state fabric.

- Auto-updated team knowledge via git (ADRs + Decision records committed, teammates `git pull`)
- Run resumability across users (`atelier run resume <alice-run-id>`)
- Selective memory sharing via git subtree (`.atelier/shared-memory/`, opt-in, human-promoted records only)
- Org-level rule defaults with override inheritance
- Team approval workflows, RBAC, audit compliance exports

### Phase 8+ — Ecosystem

- Evidence Pack open specification (RFC)
- Workflow / persona / skills marketplaces
- Partner integrations (Linear, Notion, Grafana, Datadog, Honeycomb)

---

## Non-Goals (explicitly out of scope)

- **Another platform to adopt.** Don't force users onto a new tool. Be files in git.
- Generic code chat interface — use Cursor/Claude Code for that
- Autonomous no-human-in-loop shipping — our bet is reproducible human-controlled
- Build system / language service / debugger replacement — we orchestrate existing tools
- Cloud-first — local-first with opt-in team/org deployments
- Real-time cross-user state sharing — that's Mesh Code's bet; ours is durable docs in git

## Comparison vs Existing Tools

| Tool | What it is | What Atelier does differently |
|---|---|---|
| **Conductor** | macOS workspace orchestrator for Claude Code + Codex | No context portability between agents, no memory persistence, no session continuity. Atelier = the knowledge layer Conductor lacks. |
| **Mesh Code** | Real-time state sharing across agents + users | Team-first, centralized. Atelier is files-first, git-native, single-user-first. No SaaS dependency. |
| **Mem0 / Cognee / Zep** | Memory layer for LLM API applications | Built for apps calling LLM APIs. Atelier is for humans using agent TOOLS (Claude Code, Codex). Different category. |
| **Hyperspell** | Hosted RAG over 50+ SaaS sources | Cloud API, not files-first. Useful as optional Context Compiler source (Phase 4), not as core. |
| **Cursor / Windsurf** | IDE agent | Session-local memory, no cross-tool portability, no ADR, no review discipline. |
| **Claude Code / Codex CLI** | Single-vendor CLI agent | Vendor-locked session. Context dies with the session. Atelier makes their context portable. |
| **spec-kit** | Spec-driven prompts | No orchestration, no agents, no persistence. Atelier's workflow engine drives speckit as one of many possible workflows. |

## Inspirations

- **GitHub spec-kit** — spec-driven development workflow
- **MADR 3.0** — architecture decision record format
- **Karpathy's LLM Council** — 3-stage ensemble with anonymized peer ranking
- **Du et al. 2023 — Multi-Agent Debate** (ICML 2024)
- **SARIF** — structured finding format as inspiration for Evidence Pack
- **TIROS HAZOP engineering discipline** — execution-mandatory review, data integrity, safety fallback conventions
- **RSS** — format-over-platform philosophy (be the files, not the app)

## License

Apache 2.0. All components open source. See `LICENSE`.
