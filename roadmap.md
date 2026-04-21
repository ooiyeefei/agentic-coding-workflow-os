# Agentic Coding Workflow OS — Product Roadmap

> **Working name**: _Atelier_ (placeholder — final naming TBD)
> **Status**: Phase 0 build in progress. 16 of 24 components merged to main.
> **Origin**: Distilled from battle-tested workflow on a safety-critical HAZOP/LOPA AI system (TIROS) where wrong outputs could kill people.

---

## Product Sentence

A **reproducibility system** for AI-assisted software engineering. Every decision traceable. Every review replayable. Every context reconstructable. LLM-agnostic by design. Files-first by philosophy.

## Vision

Coding agents don't lack capability — they lack **workflow, discipline, and memory**. This product provides all three as an opinionated-but-extensible control plane that turns vibe coding into production engineering.

**The core reframe**: this is not an agent framework. It is a reproducibility system for agentic engineering work.

- Packets become reproducible context
- Evidence becomes reproducible proof
- Memory becomes reproducible decisions
- Workflows become reproducible delivery

## Design Principles (non-negotiable)

1. **Files first, indexes second.** Markdown + YAML frontmatter for every persistent entity. Any DB added later is a rebuildable cache, never source of truth.
2. **CLI is the real product.** Plugins and web UIs are thin surfaces over the same control plane.
3. **Agent-agnostic.** Claude, Codex, Qwen, DeepSeek, local models — anything that implements tool use via a capability manifest.
4. **Human-in-the-loop at destructive gates.** Never auto-resolve meaningful merge conflicts. Never auto-push. Never auto-accept council verdicts on significant changes.
5. **Steering without locking.** Ship opinionated defaults. Users override with explicit `reason:`. Deviations logged to audit.
6. **Parallelization as default.** Workflow engine always scans for parallelizable work. Sequential only when dependencies require it.
7. **Dry-run first.** Every destructive action has `--dry-run`. Live execution requires explicit confirmation.
8. **Dogfood all the way down.** The product is built with the product.
9. **Evidence over vibes.** The Reviewer must paste real command output. Approval without execution evidence is incomplete.
10. **MAD at gates only.** Multi-Agent Debate is expensive. Reserve for disagreement escalation, not routine work.

## Architecture Overview

```
┌───────────────────────── CLIENTS (thin surfaces) ──────────────────────────┐
│   CLI (Phase 0)  │  VSCode ext  │  Web dashboard  │  GitHub App            │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │ HTTP/SSE · Subprocess
┌──────────────────────────────────▼─────────────────────────────────────────┐
│                          CONTROL PLANE (the product)                       │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                     WORKFLOW ENGINE (workflow-as-code)               │ │
│  │    stage transitions · review gates · MAD escalation · resume        │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌────────────────┐  ┌──────────────────┐  ┌─────────────────────────┐   │
│  │ CONTEXT        │  │ PERSONA LIBRARY  │  │   SKILLS LIBRARY        │   │
│  │ COMPILER       │  │                  │  │                         │   │
│  │                │  │ Coder · Reviewer │  │  /speckit.specify       │   │
│  │ priority tiers │  │ Guide · UAT      │  │  /speckit.clarify       │   │
│  │ token budgets  │  │ Debate Panelist  │  │  /speckit.plan          │   │
│  │ provenance     │  │                  │  │  /speckit.tasks         │   │
│  │ dedupe         │  │ capability-gated │  │  /speckit.implement     │   │
│  │                │  │ LLM-agnostic     │  │  /rebase-before-pr      │   │
│  │                │  │                  │  │  /cleanup-worktree      │   │
│  │                │  │                  │  │  /uat-test              │   │
│  └────────┬───────┘  └────────┬─────────┘  └────────────┬────────────┘   │
│           │                   │                          │                 │
│  ┌────────▼───────────────────▼──────────────────────────▼─────────────┐  │
│  │                    KNOWLEDGE PLANE (cross-cutting)                  │  │
│  │                                                                     │  │
│  │  ┌─────────────────┐          ┌─────────────────────────────────┐  │  │
│  │  │ RULES           │          │ MEMORY (typed records)          │  │  │
│  │  │ (what MUST be)  │          │  · Decision                     │  │  │
│  │  │ path-matched    │          │  · Constraint                   │  │  │
│  │  │ precedence      │          │  · RejectedAlternative          │  │  │
│  │  │ override+reason │          │  · IssueLearning                │  │  │
│  │  └─────────────────┘          │  · ReviewFinding                │  │  │
│  │                                │  · MergeConflictResolution      │  │  │
│  │                                │  · ReleaseChange                │  │  │
│  │                                │  → derives ADRs, changelogs     │  │  │
│  │                                └─────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌────────────────┐  ┌──────────────────────┐  ┌────────────────────────┐ │
│  │ EVIDENCE PACK  │  │ GIT HYGIENE          │  │ LLM ABSTRACTION        │ │
│  │                │  │                      │  │                        │ │
│  │ JSON primary   │  │ worktree lifecycle   │  │ Claude · Codex · Qwen  │ │
│  │ Markdown view  │  │ rebase-analyze-only  │  │ DeepSeek · local       │ │
│  │ audit-linked   │  │ force-with-lease     │  │                        │ │
│  │                │  │ cleanup              │  │ persona → model map    │ │
│  │ replay-ready   │  │ never auto-resolve   │  │ capability manifest    │ │
│  │                │  │ all dry-run default  │  │ fallback chains        │ │
│  │                │  │                      │  │ cost tracking          │ │
│  └────────────────┘  └──────────────────────┘  └────────────────────────┘ │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │           POLICY ENGINE (separate from workflow)                   │   │
│  │  approval gates · dry-run defaults · cost caps · override rules    │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │           ORCHESTRATOR (the conductor)                             │   │
│  │  issue DAG · worktree planner · session router · audit log         │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────────┐
│                 STORAGE (filesystem-first, git-native)                     │
│  .atelier/runs/<run_id>/stages/<stage_id>/{packet,evidence,transcript}.md  │
│  .atelier/memory/{decisions,findings,rejected_alternatives}/*.md           │
│  .atelier/audit/YYYY-MM-DD.jsonl (append-only)                             │
│  docs/adr/*.md · docs/changes/*.md (user-visible, committed)               │
└────────────────────────────────────────────────────────────────────────────┘
```

## Storage Philosophy (Filesystem-First)

Every persistent entity is a markdown file with YAML frontmatter. Directory structure IS the schema. Git is the audit trail primitive. Queries use `rg`, `find`, and frontmatter parsing. No database in the core; SQLite FTS5 may be added later as a rebuildable index for >10k record scale.

**Why**: LLMs are trained on files, not SQL. Your existing `.claude/rules/*.md` and `docs/adr/*.md` pattern already proves this works. Files give you version control, diff, review, blame, and portability for free.

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
├── overrides.yaml                 # user's deviations from defaults + reasons
└── audit/YYYY-MM-DD.jsonl         # cross-run daily audit
```

Identifiers are ULIDs throughout (`run_01HX...`, `stage_01HX...`, `packet_01HX...`, etc.) to enable time-ordered lexicographic sort without separate timestamp columns.

---

## Phases

### Phase 0 — Foundation (MVP)

**Exit criteria**: A real GitHub issue flows end-to-end through a user-defined workflow (default: specify → clarify → plan → tasks → implement → review → UAT → rebase-analyze → cleanup), producing Evidence Pack + auto-generated ADR + Run Graph on filesystem, invokable from the CLI. All components dynamic and configurable — no hardcoded workflows, no hardcoded policies.

**Must-ship**:
- Filesystem-first storage (no DB)
- ULID generator + path helpers
- LLM Abstraction (Anthropic + OpenAI) with capability manifest
- Persona Library (Coder, Reviewer) with execution-mandatory protocol
- **Devil's-advocate Reviewer flag** (`devil_advocate_mode: true`, default `false`): when enabled, Reviewer always produces an explicit "reasons to reject" section even when the verdict is APPROVE. Low cost, high signal — makes implicit concerns visible. Opt-in per persona config.
- Skills Library (extensible — ships with speckit.* + `/rebase-before-pr`, `/cleanup-worktree`, `/uat-test`; users add their own)
- Context Compiler (priority tiers + token budget + provenance)
- **Workflow Engine (workflow-as-code)**: loads workflow definitions from `.atelier/workflows/*.yaml`. Ships with `speckit-loop.yaml` as default. Users define custom workflows for their project. NOT a hardcoded pipeline.
- **Policy Engine (configurable)**: loads policy from `.atelier/policy.yaml`. Ships with sensible defaults (human-approval at destructive gates, dry-run for git ops, configurable cost caps). NOT hardcoded.
- Knowledge Plane with 3 record types (Decision, ReviewFinding, RejectedAlternative)
- Evidence Pack (JSON + Markdown)
- Auto-ADR synthesis (MADR 3.0 format)
- Git Hygiene (worktree create, rebase-analyze read-only, cleanup)
- Secret redaction (regex-based)
- Audit log (JSONL)
- Rule precedence (2 levels: core + repo)
- CLI (primary and only client surface in Phase 0)
- UAT persona (wraps existing `ccc/skills/uat-testing`)
- 3-agent council tiebreaker for Coder↔Reviewer escalation

**Deferred to later phases** (documented, not built).

### Phase 1 — Multi-Agent Debate

Full MAD (Du 2023) and LLM Council (Karpathy anonymization) protocols. Escalation gates:
- Clarify gate: 3-member council on complex clarifications
- Coder↔Reviewer deadlock after 2 rounds → council tiebreaker
- ADR authorship for significant decisions → council drafts, human edits
- Merge-conflict resolution recommendations (analyze + suggest, never auto-resolve)

Convergence detection, round caps, anonymized peer ranking, chairman synthesis.

### Phase 2 — Parallel Orchestration

- Issue dependency DAG analyzer (reads GitHub issues, labels, links)
- Worktree planner (maximum parallelism while respecting deps)
- Concurrent agent sessions across worktrees
- Cross-worktree memory sync (strategic decisions to main repo, tactical to worktree — automates the manual rule from TIROS CLAUDE.md)
- Session router handling multi-terminal routing
- **Meta-Observation Gate** — configurable checkpoint type the Workflow Engine can inject at stage transitions, before destructive ops, and after review verdicts. Pauses the run to ask the human: *"Anything about the previous stage that should inform the next one?"*, *"Noticed anything I should learn for future runs?"*, *"Any deviation from what you expected?"* Responses become first-class `Observation` memory records, queryable across runs. Over many runs, recurring observations surface as candidate new defaults for `.atelier/overrides.yaml`. Converts the tacit "I'll mention it next time" human habit into explicit capture.

### Phase 3 — Rules Engine + Memory Namespaces + Replay Harness + Competitive Integration

- Full rule precedence model: `core < org < repo < workflow/stage < human override` with audit trail
- Path-matched rule loading (per `paths:` frontmatter pattern)
- Memory namespaces: `repo-local` / `user-private` / `org-shared` with explicit opt-in tagging
- Replay harness: rerun old runs against new prompts/workflows/models, compare outcome + cost + latency + approval
- Regression detection for prompt/workflow changes
- **MemoryBackend interface**: pluggable backend for cross-agent sync. Default = `FilesBackend` (local `.atelier/memory/`). Optional = `MemoryBridgeBackend` wrapping memory-bridge or similar for Claude↔Codex state sync. Adopt existing plumbing; build application layer on top.
- **Build vs adopt benchmark**: first task of this phase is evaluating memory-bridge, Memorix, MemClaw against Atelier's typed-record + persona-slicing requirements. Don't reinvent plumbing that already works.

### Phase 4 — Git Hygiene Complete + Event Bus + Observability

- Rebase-before-PR full automation (analyze + suggest; still human-approve destructive ops)
- Force-with-lease safety wrapper
- Worktree cleanup lifecycle automation
- Event bus (internal pub-sub; external webhooks for Slack/Linear/PagerDuty)
- OpenTelemetry integration (spans for every agent action, tool call, gate)
- Cost budget enforcement with per-run/per-day/per-model caps

### Phase 5 — IDE Extensions

- VSCode extension (shares backend; covers Cursor, Windsurf, Void by extension)
- Zed extension
- JetBrains extensibility intentionally excluded — not in scope as of 2026-04

### Phase 6 — Web Dashboard + GitHub App

- Web dashboard for team visibility: Memory search, Evidence Pack archive, cost analytics, Run Graph explorer
- GitHub App: run Atelier on PRs, post Evidence Pack as PR comment, block merge on missing approvals
- GitLab / Bitbucket adapters

### Phase 7 — Team / Org Scaling

Team value comes from **auto-updated documentation as source of truth** (ADRs, architecture docs, typed decisions in git), NOT from real-time state sharing between users. Git is the sync mechanism, not a state fabric. Mesh Code-style live cross-user push is explicitly out of scope.

- **Auto-updated team knowledge**: every Atelier run auto-generates ADRs + Decision records committed to git. Teammates pull the branch and get full context. No Slack, no "hey what did you decide about X?" — read the ADR.
- **Run resumability across users**: Bob runs `atelier run resume <alice-run-id>` — Context Compiler rebuilds the packet from Alice's Run Graph + Evidence Packs + Decisions. Zero context loss, zero manual handoff.
- **Selective memory sharing via git subtree**: `.atelier/shared-memory/` as opt-in git subtree from a team-wide repo. Only explicitly human-promoted records appear. Not automatic sync — curated knowledge base using the same typed-record format.
- Org-level rule defaults with override inheritance
- Team approval workflows (multi-reviewer, tiered approval)
- Role-based access (who can override which policies)
- Audit compliance exports (SOC 2 / ISO 27001 evidence)

### Phase 8+ — Ecosystem

- **Evidence Pack open specification** (like SARIF for static analyzers). Publish RFC. Other tools can produce/consume.
- Workflow marketplace (community-authored workflows for common patterns)
- Persona marketplace (community-authored personas for specialized domains — security, ML, frontend, safety-critical)
- Skills marketplace
- Partner integrations (Linear, Notion, Grafana, Datadog, Honeycomb)

---

## Non-Goals (explicitly out of scope)

- Generic code chat interface — use Cursor/Claude Code for that
- Autonomous no-human-in-loop shipping — that's Devin's bet; ours is reproducible human-controlled
- Locked-in agent framework — we are agnostic, not yet-another-framework
- Build system / language service / debugger replacement — we orchestrate existing tools
- Cloud-first — local-first with opt-in team/org deployments

## Comparison vs Existing Tools

| Tool | Shape | Gaps Atelier fills |
|---|---|---|
| Cursor / Windsurf | Session-level IDE agent | No discipline, no ADR, no MAD, session-local memory |
| Aider | Single-agent CLI | No workflow, no review gates, no memory layer |
| GitHub Copilot Workspace | Closed, agent-first | No LLM flexibility, no review discipline, no audit |
| Cognition Devin | Closed, autonomous | No human-in-loop gates, no rule enforcement, no OSS |
| Cline / RooCode / Continue | Open IDE agent | No workflow framework, no ADR, single-agent |
| spec-kit | Spec-driven prompts only | No orchestration, no agents, no persistence |
| Claude Code / Codex CLI | Single-LLM CLI | Vendor-locked, no workflow, no reproducibility layer |
| **Atelier** | **Reproducibility system + control plane + agnostic** | — |

## Inspirations

- **GitHub spec-kit** — spec-driven development workflow
- **MADR 3.0** — architecture decision record format
- **Karpathy's LLM Council** — 3-stage ensemble with anonymized peer ranking
- **Du et al. 2023 — Multi-Agent Debate** (ICML 2024)
- **SARIF** — structured finding format as inspiration for Evidence Pack
- **aidefense-framework** — pluggable adversarial attack batteries for Reviewer
- **TIROS HAZOP engineering discipline** — execution-mandatory review, data integrity, safety fallback conventions, Producer→Consumer tracing

## License

Apache 2.0. All components open source. See `LICENSE`.
