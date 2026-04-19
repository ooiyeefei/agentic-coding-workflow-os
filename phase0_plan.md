# Phase 0 Execution Plan — Hackathon Slice

> **No time frames** per user instruction.
> **Goal**: Maximum parallelism — every task packaged as a worktree-ready unit with explicit inputs, outputs, deps, and acceptance criteria.
>
> **Operational companion**: [`phase0_launch.md`](./phase0_launch.md) contains paste-ready git worktree commands + coder/reviewer prompts for all 26 worktrees. Open that file when you're ready to start work; this file is the design spec.

## Scope Summary

Ship a demoable, end-to-end slice of Atelier that proves the reproducibility thesis on a curated repo, invokable from CLI and JetBrains plugin.

**Thesis demonstrated in demo**: One GitHub issue → spec → review (with execution evidence) → plan → tasks → implement → UAT → ADR auto-synthesized → rebase analyzed → cleanup. All persisted as files. Replayable. Reviewer-attacked. Human-approved at destructive gates.

## The Demo Scenario (12 beats)

1. User opens JetBrains plugin → clicks "New run from issue #123"
2. Plugin calls CLI daemon → orchestrator creates `.atelier/runs/<ulid>/` + worktree from main
3. Context Compiler assembles Packet v1 for Coder (issue + rules + sample docs + objective + exact commands)
4. Coder runs `/speckit.specify` → produces draft spec → writes to worktree
5. Reviewer attacks spec (execution-mandatory protocol) → produces Evidence Pack v1 (JSON + Markdown)
6. If Reviewer rejects 2× with no resolution → **Phase 1 peek**: "Escalating to Council" visual + 3-agent tiebreaker
7. Coder advances through `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement` (serial)
8. Each stage produces Evidence Pack; each disagreement logs a Decision + RejectedAlternative memory record
9. UAT stage runs `ccc/skills/uat-testing` against a real local demo app
10. Auto-ADR synthesis reads transcripts + decisions → writes `docs/adr/NNNN-<topic>.md` in MADR 3.0 format
11. `/rebase-before-pr` analyzes: runs `git fetch origin`, computes rebase conflicts, reports findings, **never auto-resolves**
12. `/cleanup-worktree` (with confirmation) — Run Graph remains committed for replay

Plugin shows, through the run:
- Run Graph tree (stages, evidence, decisions)
- Evidence Pack rendered live (webview)
- ADR preview after synthesis
- Rebase report
- Cost tracker

---

## Must-Ship Components (Phase 0 final)

| Component | Owner | Primary File(s) |
|---|---|---|
| Repo scaffolding (pyproject, tooling, dir structure) | Lane A | `pyproject.toml`, `atelier/__init__.py`, dir layout |
| ULID generator + path helpers | Lane A | `atelier/util/ulid.py`, `atelier/util/paths.py` |
| LLM Abstraction (Anthropic + OpenAI) + capability manifest | Lane A | `atelier/llm/*.py`, `atelier/llm/models/*.yaml` |
| Persona Library (Coder, Reviewer) + `devil_advocate_mode` flag (default off) | Lane B | `atelier/personas/*.py`, `.atelier/defaults/personas/*.md` |
| Skills Library (imports + additions) | Lane B | `.atelier/defaults/skills/*.md` |
| Context Compiler | Lane A | `atelier/compiler/*.py` |
| Knowledge Plane record schemas + file I/O | Lane B | `atelier/memory/*.py` |
| Evidence Pack generator | Lane B | `atelier/evidence/*.py`, `atelier/evidence/templates/*.j2` |
| Auto-ADR synthesis | Lane B | `atelier/adr/*.py`, `atelier/adr/templates/madr.j2` |
| Run Graph file tree ops | Lane A | `atelier/rungraph/*.py` |
| Workflow Engine (speckit loop) | Lane A | `atelier/workflow/*.py` |
| Policy Engine | Lane A | `atelier/policy/*.py` |
| Git Hygiene (worktree, rebase-analyze, cleanup) | Lane C | `atelier/git/*.py` |
| Secret redaction | Lane C | `atelier/security/redaction.py` |
| Audit log (JSONL) | Lane C | `atelier/audit/*.py` |
| UAT persona + integration | Lane C | `atelier/personas/uat.py`, `.atelier/defaults/personas/uat.md` |
| CLI | Lane A | `atelier/cli/*.py` |
| HTTP daemon + SSE | Lane A | `atelier/daemon/*.py` |
| JetBrains plugin scaffold | Lane D | `plugin-jetbrains/*` |
| Plugin tool window + JCEF webview + SSE client | Lane D | `plugin-jetbrains/src/main/kotlin/*` |
| **Phase 1 peek**: 3-agent tiebreaker | Lane B (late) | `atelier/council/*.py` |
| Curated demo target app | Lane E | `demo/app/*` |
| Curated demo issue | Lane E | `demo/issue.md` |
| End-to-end dogfood run + warm-cache | Lane E | `demo/warm-cache/*` |
| Pitch deck + demo script | Lane E | `demo/pitch.md`, `demo/script.md` |

## Deferred (documented, not built)

- Parallel worktree orchestration (Phase 2)
- Full MAD / LLM Council (Phase 1 except tiebreaker)
- Memory namespaces (repo-local only in Phase 0)
- Replay/Eval Harness (Phase 3)
- VSCode extension (Phase 5)
- Web dashboard (Phase 6)
- Event bus, OpenTelemetry (Phase 4)
- Org defaults, workflow-level policy (Phase 4)
- Full rule precedence (2 levels in Phase 0, 5 levels in Phase 3)
- Model capability dynamic discovery (hardcoded YAML in Phase 0)
- Workflow YAML validator + dynamic loader (hardcoded Python workflow in Phase 0)

---

## Parallel Worktree DAG

### Dependency diagram

```
                     W01 (repo scaffolding)
                           │
                ┌──────────┼──────────┬────────────┬──────────────┐
                │          │          │            │              │
              W02        W03        W04          W05            W22
        (LLM abstr.) (ULID+paths) (personas)  (skills)   (demo target app)
                │          │          │            │              │
                │          └────┬─────┼────┬───────┘              │
                │               │     │    │                      │
                │              W06   W07  W08                     W23
                │             (memory)(compiler)(evidence)   (demo issue)
                │               │     │    │
                │               └─┬───┼────┘
                │                 │   │
                │                W09 W10
                │          (run graph) (redaction)
                │                 │   │
                │                W13 W14
                │            (audit) (auto-ADR)
                │                 │
                │                W11
                │         (workflow engine)
                │                 │
                │                W12
                │          (policy engine)
                │                 │
                │                W15
                │              (CLI)
                │                 │
                │                W16
                │          (HTTP daemon + SSE)
                │                 │
                │        ┌────────┴────────┐
                │       W17               W18
                │    (plugin scaffold)  (UAT persona)
                │        │
                │       W20
                │  (plugin UI webview)
                │
              W19 (LLM swappability test)    W21 (3-agent tiebreaker, Phase 1 peek)
                                             W24 (E2E dogfood + warm cache)
                                             W25 (pitch deck + demo script)
              W26 (Git Hygiene)
```

### Suggested Parallel Lanes

**Lane A — Control Plane (Python async)**
`W01 → W02 → W03 → W07 → W09 → W11 → W12 → W15 → W16`
One strong Python engineer. Owns orchestration, workflow, LLM abstraction, context compiler, CLI, daemon.

**Lane B — Personas, Memory, Evidence**
`W04 → W05 → W06 → W08 → W14 → (W21 if time)`
One engineer with prompt-craft + Python. Owns the IP that makes Atelier different — Reviewer execution-mandatory protocol, Evidence Pack templates, auto-ADR synthesis, Phase 1 council tiebreaker.

**Lane C — Git, UAT, Security**
`W10 → W13 → W26 → W18`
One engineer comfortable with git internals + subprocess orchestration. Owns git hygiene, audit log, secret redaction, UAT wiring.

**Lane D — JetBrains Plugin**
`W17 → W20`
One engineer with Kotlin + frontend. Starts as soon as W16 API spec is frozen (interfaces defined even before implementation). Owns plugin scaffold, tool window, webview, SSE consumer.

**Lane E — Product / Demo**
`W22 → W23 → W19 → W24 → W25`
One generalist. Curates demo repo + demo issue, validates dogfood runs, builds warm-cache, writes pitch script, records fallback video.

### Cross-Lane Integration Points

- **Saturday 11am equivalent milestone**: Lane A publishes HTTP API contract (OpenAPI spec or Python Protocol). All lanes freeze to this interface by EOD Day 1.
- **Evidence Pack schema** (JSON): Lanes B + D agree on Evidence Pack JSON structure so plugin webview knows what to render.
- **Context Packet format** (Markdown): Lane A + Lane B agree on packet.md structure early.
- **LLM capability manifest format**: Lane A publishes; Lane B consumes when declaring persona requirements.

---

## Worktree Details

Each worktree below is independently checkoutable. `depends` lists the worktrees whose outputs must exist first. Recommend creating a git worktree per W## for true isolation.

### W01 — Repo scaffolding

- **Depends**: none (foundation)
- **Owns**: `pyproject.toml`, `atelier/__init__.py`, top-level dir structure, `.python-version`, Makefile
- **Scope**: Python 3.11+ project, uv-managed deps, ruff + pyright configured. Define package layout (`atelier/cli`, `atelier/llm`, `atelier/workflow`, etc.).
- **Acceptance**: `uv sync` works, `python -m atelier --help` prints placeholder help, ruff + pyright pass on empty package
- **Output**: installable package skeleton
- **Handoff**: All other W## can `from atelier import ...` once this lands
- **Blocks**: Everything

### W02 — LLM Abstraction + Capability Manifest

- **Depends**: W01
- **Owns**: `atelier/llm/adapter.py`, `atelier/llm/anthropic.py`, `atelier/llm/openai.py`, `atelier/llm/capabilities.py`, `.atelier/defaults/models/*.yaml`
- **Scope**: abstract `LLMAdapter` with `generate(messages, tools, capabilities) -> Response`. Anthropic + OpenAI implementations. YAML capability manifests for claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5, gpt-5 (or codex), gpt-4o-mini. Persona-requires vs model-offers matching function.
- **Acceptance**: Unit test calls Anthropic and OpenAI with mock, validates response shape. Capability matcher rejects route if persona requires `tool_use` and model offers `tool_use: false`.
- **Output**: Pluggable LLM backend layer
- **Handoff**: Lane B uses this for persona LLM calls
- **Blocks**: W04, W07, W11, W21

### W03 — ULID Generator + Path Helpers

- **Depends**: W01
- **Owns**: `atelier/util/ulid.py`, `atelier/util/paths.py`
- **Scope**: ULID generation (use `python-ulid`), path helpers for `.atelier/runs/<run_id>/stages/<nnn-name>/`, safe mkdir, atomic writes (tmpfile + rename)
- **Acceptance**: ULIDs are lex-sortable; paths generated correctly for a fake run+stage; atomic write survives simulated interrupt
- **Output**: ID + FS utilities used everywhere
- **Blocks**: W09, W13, W11

### W04 — Persona Library

- **Depends**: W01, W02 (partial — consumes LLM adapter)
- **Owns**: `atelier/personas/base.py`, `atelier/personas/coder.py`, `atelier/personas/reviewer.py`, `.atelier/defaults/personas/coder.md`, `.atelier/defaults/personas/reviewer.md`
- **Scope**: `Persona` class with system prompt loader, capability requirements, LLM adapter binding. Reviewer persona prompt implements execution-mandatory protocol (transplant from TIROS AGENTS.md, generalized). Coder persona prompt is the /speckit.* driver.
- **Acceptance**: `coder.respond(packet)` returns a draft; `reviewer.review(diff, tests)` returns a structured Evidence Pack draft with verdict + confidence + findings
- **Output**: Two working personas, loadable by name
- **Blocks**: W11, W18, W21

### W05 — Skills Library

- **Depends**: W01
- **Owns**: `.atelier/defaults/skills/speckit.specify.md`, `.atelier/defaults/skills/speckit.clarify.md`, `.atelier/defaults/skills/speckit.plan.md`, `.atelier/defaults/skills/speckit.tasks.md`, `.atelier/defaults/skills/speckit.implement.md`, `.atelier/defaults/skills/rebase-before-pr.md`, `.atelier/defaults/skills/cleanup-worktree.md`, `.atelier/defaults/skills/uat-test.md`
- **Scope**: Import speckit.* verbatim from user's existing `.claude/commands/`. Author rebase-before-pr.md (encode user's exact instructions: git add . → commit → fetch → rebase origin/main → analyze conflicts without deciding → report → force-with-lease push). Author cleanup-worktree.md. Stub uat-test.md that calls ccc/skills/uat-testing.
- **Acceptance**: Each skill file has YAML frontmatter with `inputs`, `expected_artifacts`, `success_checks`, `next_transition`. Skill loader reads and validates.
- **Output**: Complete skill catalog Phase 0 needs
- **Blocks**: W11

### W06 — Knowledge Plane (typed records)

- **Depends**: W01, W03
- **Owns**: `atelier/memory/records.py`, `atelier/memory/writer.py`, `atelier/memory/reader.py`
- **Scope**: Pydantic schemas for `Decision`, `ReviewFinding`, `RejectedAlternative`. Writer serializes to markdown with YAML frontmatter. Reader parses any `.atelier/memory/**/*.md` back to typed record. Deterministic filename = `<type>_<ulid>.md`.
- **Acceptance**: Round-trip test: `record → write → read → record` preserves all fields. Frontmatter is valid YAML, body is clean markdown.
- **Output**: Memory record persistence layer
- **Blocks**: W14, W11

### W07 — Context Compiler

- **Depends**: W01, W02, W03
- **Owns**: `atelier/compiler/compiler.py`, `atelier/compiler/sources.py`
- **Scope**: Assemble Context Packets from prioritized sources. Inputs: issue text, repo rules (`CLAUDE.md`, `.claude/rules/*.md`), relevant ADRs, sample docs, current worktree path, exact objective, exact commands, acceptance gate. Priority tiers (must/should/nice). Token budget enforcement (simple `len*4/3` estimator for Phase 0). Dedup identical blocks. Each block tagged with provenance tuple `(source_type, source_id, path)`. Output: `packet.md`.
- **Acceptance**: Given fixture inputs, compiler produces deterministic packet.md under a fake 8k-token budget, nice-to-have tier gets dropped first. Provenance block at end lists all sources.
- **Output**: Deterministic packet generation
- **Blocks**: W11

### W08 — Evidence Pack Generator

- **Depends**: W01, W03
- **Owns**: `atelier/evidence/schema.py`, `atelier/evidence/generator.py`, `atelier/evidence/templates/evidence.md.j2`
- **Scope**: Pydantic schema for EvidencePack (verdict, confidence, findings list with severity, execution section with real command outputs, audit-chain linked IDs). Jinja2 template renders Markdown from JSON. Both written side-by-side.
- **Acceptance**: EvidencePack(verdict="REJECTED", findings=[...]) produces valid JSON and human-readable Markdown; Markdown references ULIDs for traceback.
- **Output**: Dual-format Evidence Pack writer
- **Blocks**: W04 (reviewer writes evidence via this)

### W09 — Run Graph File Tree Ops

- **Depends**: W01, W03
- **Owns**: `atelier/rungraph/tree.py`, `atelier/rungraph/cursor.py`
- **Scope**: Create runs/<ulid>/, create stages/<nnn-name>/, write stage.md with frontmatter, write completion markers for idempotency. `cursor` tracks "next stage to execute" for resume semantics. Lock file per run to prevent concurrent writes.
- **Acceptance**: Start run, create 3 stages, complete 2, restart process, resume correctly picks up stage 3. Lock prevents second writer.
- **Output**: Durable run lineage as directory tree
- **Blocks**: W11, W13

### W10 — Secret Redaction

- **Depends**: W01
- **Owns**: `atelier/security/redaction.py`
- **Scope**: Regex-based redactor for: `.env` line patterns, known env var names (`API_KEY`, `TOKEN`, `SECRET`, `PASSWORD`, `Bearer <x>`), common service prefixes (`sk-`, `pk_`, `ghp_`, `xoxb-`). Entropy heuristic for unknown high-entropy strings optional. Applied before any write-to-file.
- **Acceptance**: Fixture with `OPENAI_API_KEY=sk-abc123...` redacts to `OPENAI_API_KEY=<REDACTED>`. Safe strings pass through.
- **Output**: Reusable redaction function
- **Blocks**: W13 (audit log), W08 (evidence)

### W11 — Workflow Engine

- **Depends**: W04, W05, W06, W07, W08, W09
- **Owns**: `atelier/workflow/engine.py`, `atelier/workflow/stages.py`, `atelier/workflow/transitions.py`
- **Scope**: Python class `Workflow` with hardcoded speckit loop: specify → clarify → plan → tasks → implement → (optional UAT) → rebase-analyze → cleanup. Each stage is a function that: runs persona with packet, writes Evidence Pack, checks gate, transitions or loops. Resume-aware via W09 cursor.
- **Acceptance**: Start workflow on fixture issue, advance through at least specify → review, handle Reviewer rejection with one Coder retry, confirm all files written to .atelier/runs/<ulid>/.
- **Output**: Executable workflow
- **Blocks**: W15, W16

### W12 — Policy Engine

- **Depends**: W01
- **Owns**: `atelier/policy/engine.py`, `atelier/policy/defaults.py`
- **Scope**: Policy primitives: `human_approval_required`, `dry_run_default`, `cost_cap_per_run`. Hardcoded in Phase 0: approval at rebase-before-pr, dry-run for all git ops, $5/run cap. Policy checks called by W11 before destructive ops and before LLM calls.
- **Acceptance**: Rebase-before-pr halts + prompts for human approval. Cost exceeding cap halts + alerts.
- **Output**: Policy enforcement layer
- **Blocks**: W11

### W13 — Audit Log

- **Depends**: W01, W03, W10
- **Owns**: `atelier/audit/writer.py`
- **Scope**: Append-only JSONL writer for per-run `.atelier/runs/<id>/audit.jsonl` and daily `.atelier/audit/YYYY-MM-DD.jsonl`. Events: llm_call, tool_call, gate_entered, decision_logged, override_applied. Apply redaction (W10) before write.
- **Acceptance**: 1000 concurrent writes produce no corruption. Every line valid JSON. Secrets redacted.
- **Output**: Reliable audit trail
- **Blocks**: (called by many, blocks nothing)

### W14 — Auto-ADR Synthesis

- **Depends**: W01, W03, W06
- **Owns**: `atelier/adr/synthesis.py`, `atelier/adr/templates/madr.md.j2`
- **Scope**: Read all Decision + RejectedAlternative records for a completed run. Render MADR 3.0 format: Context, Decision, Consequences, Alternatives Considered. Write to `docs/adr/NNNN-<slug>.md`, auto-numbering.
- **Acceptance**: Fixture with 3 Decisions + 2 RejectedAlternatives produces a well-formed MADR 3.0 ADR ready for human review.
- **Output**: Auto-generated ADRs
- **Blocks**: (called by W11 at run completion)

### W15 — CLI

- **Depends**: W11
- **Owns**: `atelier/cli/main.py`, `atelier/cli/commands/*.py`
- **Scope**: Click or Typer-based CLI. Commands: `init`, `run --issue <N>`, `run resume <run_id>`, `run show <run_id>`, `run list`, `cleanup <run_id>`, `daemon start|stop|status`, `grep <pattern>`.
- **Acceptance**: `atelier run --issue 42 --repo path/to/demo` initiates a workflow, writes to filesystem, prints Run ID.
- **Output**: Primary user interface
- **Blocks**: W16

### W16 — HTTP Daemon + SSE

- **Depends**: W15
- **Owns**: `atelier/daemon/server.py`, `atelier/daemon/routes.py`
- **Scope**: FastAPI app exposing: `POST /runs` (start), `GET /runs/<id>` (status), `GET /runs/<id>/events` (SSE stream of audit events), `POST /runs/<id>/approve` (gate approvals). Same process as CLI but daemon mode.
- **Acceptance**: Plugin subscribes to SSE, receives events in real-time as workflow advances.
- **Output**: API for plugin consumption
- **Blocks**: W17, W20

### W17 — JetBrains Plugin Scaffold

- **Depends**: W16 (API contract frozen; implementation can lag)
- **Owns**: `plugin-jetbrains/build.gradle.kts`, `plugin-jetbrains/src/main/resources/META-INF/plugin.xml`, `plugin-jetbrains/src/main/kotlin/com/atelier/*.kt`
- **Scope**: IntelliJ Platform Plugin Template (start from official template). Register tool window, declare dependencies, set up Gradle intellij-platform plugin. Kotlin HTTP client for W16 daemon.
- **Acceptance**: `./gradlew runIde` launches IDEA with Atelier tool window visible (empty shell).
- **Output**: Pluggable IDE surface
- **Blocks**: W20

### W18 — UAT Persona Integration

- **Depends**: W04
- **Owns**: `atelier/personas/uat.py`, `.atelier/defaults/personas/uat.md`
- **Scope**: UAT persona launches user's existing `ccc/skills/uat-testing` as subprocess. Feeds test account creds from `env.local`. Captures test report, parses to EvidencePack findings.
- **Acceptance**: Demo app has a login flow; UAT persona runs skill against it, produces structured Evidence Pack section "UAT: 3/3 passed".
- **Output**: UAT stage implementation
- **Blocks**: (slotted into W11 workflow before cleanup)

### W19 — LLM Swappability Test

- **Depends**: W02, W04
- **Owns**: `demo/swap-demo.md`, test script
- **Scope**: Demo scenario where Reviewer is Claude, then swap to Codex (or Qwen). Runs same review twice, shows Evidence Packs side-by-side. Proves LLM-agnosticism is real, not claimed.
- **Acceptance**: Both runs produce valid Evidence Packs (may differ in findings, that's fine). Capability manifest correctly rejects routes to insufficient models.
- **Output**: Demo beat that proves swappability
- **Blocks**: (standalone demo asset)

### W20 — Plugin Tool Window + JCEF Webview + SSE

- **Depends**: W17, W08 (evidence pack format)
- **Owns**: `plugin-jetbrains/src/main/kotlin/com/atelier/toolwindow/*.kt`, `plugin-jetbrains/src/main/resources/web/*`
- **Scope**: Tool window with 3 tabs: Run Graph (tree view), Evidence Pack (JCEF webview rendering evidence.md), ADR (preview + open-in-editor). SSE client streams events, updates UI live. Run Graph tree hydrated from filesystem on load.
- **Acceptance**: Click "New run", live events flow in, Evidence Pack renders, ADR preview shows after synthesis.
- **Output**: Visible IDE product
- **Blocks**: (end of Lane D)

### W21 — Phase 1 Peek: 3-Agent Tiebreaker

- **Depends**: W02, W04
- **Owns**: `atelier/council/tiebreaker.py`
- **Scope**: Minimal 3-agent council. Triggered when Coder↔Reviewer deadlock 2x. Protocol: send Coder's position + Reviewer's position + full context to 3 different models. Each votes VERDICT_COMPATIBLE_WITH_{CODER,REVIEWER,NEITHER}. Majority wins; ties go to human.
- **Acceptance**: Fixture deadlock scenario → 3 council calls → majority verdict → Evidence Pack records tiebreaker outcome.
- **Output**: Visible Phase 1 capability in demo
- **Blocks**: (standalone feature toggled in demo)

### W22 — Demo Target App

- **Depends**: none (parallel with everything)
- **Owns**: `demo/app/*`
- **Scope**: Minimal Next.js or FastAPI app with: 1 auth flow, 1 CRUD endpoint, existing tests. Something whose issue-to-shipped-code demo makes sense.
- **Acceptance**: App runs locally, login works, tests pass, there is an obvious "feature to add" that becomes our demo issue.
- **Output**: Curated demo codebase
- **Blocks**: W24

### W23 — Demo Issue

- **Depends**: W22
- **Owns**: `demo/issue.md` (+ filed as GitHub issue once repo exists)
- **Scope**: Write the demo issue. Should be specific, testable, adversarially-reviewable (Reviewer must find something legitimate to attack), UAT-able. Example: "Add rate limiting to /api/login endpoint — max 5 attempts per minute per IP. Must return 429 with Retry-After header."
- **Acceptance**: Issue is concrete; acceptance criteria are testable; UAT can validate via real login attempts.
- **Output**: Demo driver input
- **Blocks**: W24

### W24 — E2E Dogfood + Warm Cache

- **Depends**: W11, W15, W22, W23
- **Owns**: `demo/warm-cache/*`, `demo/dogfood.md`
- **Scope**: Run the full Phase 0 workflow against demo app + demo issue end-to-end. Capture every stage's output. Pre-populate `.atelier/runs/<cached-id>/` as warm-cache fallback. Validate plugin + CLI both work.
- **Acceptance**: Full run completes. Warm cache can be replayed if live run hiccups during demo.
- **Output**: Rehearsed, de-risked demo
- **Blocks**: W25

### W25 — Pitch Deck + Demo Script + Fallback Video

- **Depends**: W24
- **Owns**: `demo/pitch.md`, `demo/script.md`, `demo/fallback.mp4`
- **Scope**: Pitch deck (5 slides max): problem, solution, demo, moat, ask. Demo script (beat-by-beat, ≤90s live). Fallback video of the successful dogfood run.
- **Acceptance**: Rehearsed 5+ times. Fallback video plays if everything else fails.
- **Output**: Hackathon presentation assets

### W26 — Git Hygiene Module

- **Depends**: W01, W03, W13
- **Owns**: `atelier/git/worktree.py`, `atelier/git/rebase_analyzer.py`, `atelier/git/cleanup.py`
- **Scope**: Worktree create from main with naming convention `worktrees/<run_id>/`. Rebase analyzer: `git fetch`, `git rebase --dry-run` equivalent (use `git merge-tree` for conflict simulation without state mutation). Structured conflict report (files, hunks, suggested resolutions — NEVER applied). Cleanup: `git worktree remove` with confirmation.
- **Acceptance**: On a conflicted branch, rebase-analyzer reports N conflicts with file:line precision and suggestions. Zero state mutation.
- **Output**: Safe git automation
- **Blocks**: W18 (integrated into workflow at rebase-before-pr stage)

---

## Integration Contracts (freeze early)

| Contract | Owner | Consumers |
|---|---|---|
| HTTP API (POST /runs, GET /runs/<id>, SSE /events, POST /approve) | Lane A | Lane D (plugin) |
| Evidence Pack JSON schema | Lane B | Lane D (plugin webview), Lane A (audit) |
| Context Packet markdown structure | Lane A + Lane B | Lane B (personas consume) |
| Persona capability declaration format | Lane A | Lane B (personas declare) |
| Skill frontmatter schema | Lane B | Lane A (workflow engine loads) |
| LLM adapter interface | Lane A | Lane B (personas call) |

**Freeze deadline**: end of first integration block. After freeze, changes require cross-lane sign-off.

---

## Warm-Cache / Fallback Plan

| Stage | Warm cache | Fallback trigger |
|---|---|---|
| Workflow start | pre-generated run directory | live daemon fails > 5s |
| Evidence Pack generation | pre-rendered example | LLM API rate limit or timeout |
| Auto-ADR synthesis | pre-generated ADR file | LLM fails |
| Plugin UI | cached static render of last successful run | daemon connection failure |
| Whole demo | pre-recorded video | catastrophic failure |

Fallback narration: never admit "it failed." Narrate over cached output as if live. Use present tense. Rehearse this.

---

## Demo Script (draft, 90s)

**[0:00-0:10]** Hook. "When you let an AI coding agent loose on your codebase, you're trusting that tomorrow you can explain what it did and why. Today you can't. Atelier fixes that."

**[0:10-0:25]** Setup. Show JetBrains IDE with demo repo. "Here's a real issue: add rate limiting to /api/login. I click run. Atelier starts."

**[0:25-0:55]** The core loop. Tool window lights up. Coder writes spec. Reviewer attacks with real command output. Reviewer finds an edge case Coder missed — show the Evidence Pack with red finding + pasted pytest failure. Coder fixes. Reviewer approves. Green.

**[0:55-1:15]** UAT + ADR. UAT persona runs against live app — show 5 rate-limit attempts on a browser. Auto-generated ADR appears — judges see real MADR 3.0 format.

**[1:15-1:30]** The reproducibility moment. Show `.atelier/runs/<id>/` directory. "Every packet, every transcript, every decision — on disk. Replayable. Swap Claude for Codex and run it again. Same workflow. Different brain. That's Atelier."

**[1:30 stretch]** Rebase analysis. "And when you're ready to merge, Atelier never decides for you. It reports the exact conflicts and commands — you stay in control of destructive operations."

---

## What's Explicitly NOT in Phase 0 (reference)

See `roadmap.md` Phase 1+. Short list:
- Parallel worktree orchestration
- Full MAD / Council protocols (only tiebreaker)
- Memory namespaces
- Replay harness
- VSCode
- Web dashboard
- Event bus
- OTel
